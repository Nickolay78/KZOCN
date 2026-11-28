import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUN_DB = os.path.join(BASE_DIR, "imports", "punishments_ua_2013_2025", "punishments_ua.sqlite")
WEB_DIR = os.path.join(BASE_DIR, "web")
OUT_JS = os.path.join(WEB_DIR, "punishments_data.js")

ROMAN_ORDER = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
]

METRICS_META = [
    # Totals / aggregates
    {"id": "RELEASED", "group": "summary", "name": "Звільнено від покарання (разом)", "short": "Звільнено", "color": "#f59e0b",
     "note": "Сума відомих категорій звільнення (PROB + RELAMN + RELOTHR). Об'єднання категорій звіту ДСА."},
    {"id": "PUNISHED", "group": "summary", "name": "Основні покарання (разом, без звільнень)", "short": "Осн. покарання", "color": "#ec4899",
     "note": "Основні покарання за видами (без категорій звільнення). Не доводить фактичне виконання покарання."},
    {"id": "CONVIC", "group": "summary", "name": "Усі засуджені особи (CONVIC)", "short": "Усі засуджені", "color": "#a855f7",
     "note": "Загальна кількість засуджених осіб за формою № 6 ДСА (звільнені + основні покарання)."},

    # Release categories
    {"id": "PROB", "group": "release", "name": "Звільнено з випробуванням (PROB)", "short": "Випробування", "color": "#fbbf24",
     "note": "Звільнення від відбування покарання з випробуванням (ст. 75, 104 КК). Входить до категорії звільнень."},
    {"id": "RELAMN", "group": "release", "name": "Звільнено за амністією (RELAMN)", "short": "Амністія", "color": "#fde047",
     "note": "Звільнення від покарання на підставі закону про амністію."},
    {"id": "RELOTHR", "group": "release", "name": "Звільнено з інших підстав (RELOTHR)", "short": "Інші звільнення", "color": "#fcd34d",
     "note": "Звільнення від покарання з інших законних підстав (давність, хвороба тощо)."},

    # Main punishment types (Art. 51)
    {"id": "LIFEIMP", "group": "main", "name": "Довічне позбавлення волі", "short": "Довічне", "color": "#ef4444",
     "note": "Основне покарання за видами (без категорій звільнення)."},
    {"id": "IMP", "group": "main", "name": "Позбавлення волі на певний строк", "short": "Позб. волі", "color": "#f97316",
     "note": "Основне покарання за видами (без категорій звільнення). Блок x3 у 2018–2025 рр."},
    {"id": "DISBAT", "group": "main", "name": "Тримання в дисциплінарному батальйоні", "short": "Дисбат", "color": "#a78bfa",
     "note": "Основне покарання за видами (для військовослужбовців)."},
    {"id": "RESTOL", "group": "main", "name": "Обмеження волі", "short": "Обмеж. волі", "color": "#eab308",
     "note": "Основне покарання за видами (без категорій звільнення)."},
    {"id": "PROBAN", "group": "main", "name": "Пробаційний нагляд (лише з 2025 р.)", "short": "Пробація", "color": "#14b8a6",
     "availableFrom": 2025,
     "note": "Окрема колонка PROBAN з'явилася у формі № 6 лише у 2025 р. (у 2013–2024 недоступна — NULL, не 0; у 2024 р. відображалась у складі PNOTHR)."},
    {"id": "ARREST", "group": "main", "name": "Арешт", "short": "Арешт", "color": "#f472b6",
     "note": "Основне покарання за видами (без категорій звільнення)."},
    {"id": "SRVRSTR", "group": "main", "name": "Службові обмеження для військовослужбовців", "short": "Служб. обмеж.", "color": "#94a3b8",
     "note": "Основне покарання за видами (для військовослужбовців)."},
    {"id": "CORRW", "group": "main", "name": "Виправні роботи", "short": "Випр. роботи", "color": "#60a5fa",
     "note": "Основне покарання за видами (без категорій звільнення)."},
    {"id": "PUBLW", "group": "main", "name": "Громадські роботи", "short": "Гром. роботи", "color": "#4ade80",
     "note": "Основне покарання за видами (без категорій звільнення)."},
    {"id": "DEPR", "group": "main", "name": "Позбавлення права обіймати посади (основне)", "short": "Позб. права", "color": "#c084fc",
     "note": "Основне покарання за видами (додаткове позбавлення права не додається)."},
    {"id": "FINE", "group": "main", "name": "Штраф", "short": "Штраф", "color": "#38bdf8",
     "note": "Основне покарання за видами (додатковий штраф не додається)."},
    {"id": "PNOTHR", "group": "main", "name": "Інші види основного покарання", "short": "Інші осн.", "color": "#818cf8",
     "note": "Основне покарання за видами. У 2024 р. включало пробаційний нагляд (не розкладається припущеннями)."},
]

VALID_MATCH_STATUSES = ("exact", "normalized_single_sanction", "corrected_246_part")


def main():
    conn = sqlite3.connect("file:" + PUN_DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    years = [str(r[0]) for r in cur.execute("SELECT DISTINCT year FROM source_rows ORDER BY year")]

    # Preload balances keyed by row_id
    balances = {}
    for r in cur.execute("SELECT row_id, convicted, released_known_sum, punished_known_sum FROM balances"):
        balances[r["row_id"]] = (r["convicted"], r["released_known_sum"], r["punished_known_sum"])

    # Preload all non-null metrics keyed by row_id
    row_metrics = {}
    for r in cur.execute("SELECT row_id, metric, value FROM metrics WHERE value IS NOT NULL"):
        rid = r["row_id"]
        if rid not in row_metrics:
            row_metrics[rid] = {}
        row_metrics[rid][r["metric"]] = int(r["value"])

    def pack_row(rid, year_int):
        bal = balances.get(rid)
        if not bal or bal[0] is None:
            return None
        conv, rel, pun = bal
        d = {}
        if conv is not None:
            d["CONVIC"] = int(conv)
        if rel is not None and rel > 0:
            d["RELEASED"] = int(rel)
        if pun is not None and pun > 0:
            d["PUNISHED"] = int(pun)
        for m, v in row_metrics.get(rid, {}).items():
            if m == "CONVIC":
                continue
            if m == "PROBAN" and year_int < 2025:
                continue
            if v > 0:
                d[m] = v
        return d

    # 1. Overall national totals (kind = 'overall_total')
    overall = {}
    for r in cur.execute("SELECT id, year FROM source_rows WHERE kind='overall_total' ORDER BY year"):
        yr = str(r["year"])
        packed = pack_row(r["id"], r["year"])
        if packed is not None:
            overall[yr] = packed

    # 2. Chapter totals (kind = 'chapter_total')
    chapters = {yr: {} for yr in years}
    for r in cur.execute("SELECT id, year, chapter FROM source_rows WHERE kind='chapter_total' ORDER BY year, source_row"):
        yr = str(r["year"])
        ch = r["chapter"]
        packed = pack_row(r["id"], r["year"])
        if packed is not None and ch in ROMAN_ORDER:
            chapters[yr][ch] = packed

    # 3. Article-part level matched to KZOSN norms (norm_id = 'YYYY:art:part')
    by_year = {yr: {} for yr in years}
    matched_count = 0
    for r in cur.execute(f"""
        SELECT sr.id, sr.year, kl.norm_id, kl.match_status
        FROM source_rows sr
        JOIN kzosn_links kl ON kl.row_id = sr.id
        WHERE sr.kind = 'article'
          AND kl.match_status IN ({",".join("?" for _ in VALID_MATCH_STATUSES)})
          AND kl.norm_id IS NOT NULL
    """, VALID_MATCH_STATUSES):
        packed = pack_row(r["id"], r["year"])
        if not packed:
            continue
        parts = r["norm_id"].split(":")
        if len(parts) != 3:
            continue
        yr = str(r["year"])
        norm_key = f"{parts[1]}|{parts[2]}"
        # If multiple source rows map to same norm_key (rare), sum known values safely
        if norm_key not in by_year[yr]:
            by_year[yr][norm_key] = packed
            matched_count += 1
        else:
            existing = by_year[yr][norm_key]
            for k, v in packed.items():
                existing[k] = existing.get(k, 0) + v

    conn.close()

    payload = {
        "years": years,
        "metrics": METRICS_META,
        "overall": overall,
        "chapters": chapters,
        "byYear": by_year,
    }

    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write("window.KZOSN_PUN_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    print(f"Exported {OUT_JS} ({os.path.getsize(OUT_JS):,} bytes), matched active article-parts: {matched_count}")


if __name__ == "__main__":
    main()
