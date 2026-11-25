import os
import re
import sqlite3
import lxml.html
import pandas as pd
from sanction_parser import parse_sanction, norm_text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw_html")
CROSSWALK_DB_PATH = os.path.join(BASE_DIR, "data", "kzosn_crosswalk.sqlite")
DB_PATH = os.path.join(BASE_DIR, "kzocn_kk_ukraine.db")
EXCEL_PATH = os.path.join(BASE_DIR, "KZOCN_Database_2001_2026.xlsx")

EDITIONS_META = [
    ("2001_09_01", "2001-09-01", "Перша редакція (набрання чинності 01.09.2001)"),
]
for y in range(2001, 2026):
    EDITIONS_META.append((str(y), f"{y}-12-31", f"Редакція станом на 31.12.{y}"))
EDITIONS_META.append(("current", "2026-11-14", "Актуальна редакція (2026)"))


def article_to_code(art_str: str) -> int:
    """
    Converts article number string like '109' -> 1090, '110-2' -> 1102, '258-5' -> 2585
    matching the convention in In_Context-2++.xlsx.
    """
    if "-" in art_str:
        base, sub = art_str.split("-", 1)
        return int(base) * 10 + int(sub)
    return int(art_str) * 10


def extract_edition_parts(html_path: str, edition_id: str, snapshot_date: str):
    with open(html_path, "r", encoding="utf-8") as f:
        doc = lxml.html.fromstring(f.read())

    blocks = doc.xpath("//pre | //p")
    special = False
    cur_sec = ""
    cur_art = ""
    cur_art_title = ""
    cur_part = None
    unnumbered_count = 0
    cur_disp = []
    in_note = False
    records = []

    for b in blocks:
        t = re.sub(r"\s+", " ", b.text_content()).strip()
        if not t:
            continue
        # Remove legislative change annotations in {...} or (...)
        t_clean = re.sub(r"\{[^}]*\}", "", t)
        t_clean = re.sub(
            r"\(\s*(?:Статт[яюі]|Частин[ауі]|Абзац|Кодекс|Розділ)\b.*?\)\s*$",
            "",
            t_clean,
            flags=re.I,
        ).strip()
        if not t_clean or t_clean.startswith("{"):
            continue

        if not special:
            if t_clean.upper() == "ОСОБЛИВА ЧАСТИНА":
                special = True
            continue

        if re.match(r"^ПРИКІНЦЕВІ ТА ПЕРЕХІДНІ ПОЛОЖЕННЯ", t_clean, re.I):
            break

        # Section header
        m_sec = re.match(r"^Р\s*о\s*з\s*д\s*і\s*л\s+([IVXLCDM]+)\b", t_clean, re.I)
        if m_sec:
            cur_sec = m_sec.group(1).upper()
            in_note = False
            continue

        # Article header
        m_art = re.match(r"^Стаття\s+(\d+(?:-\d+)?)\.\s*(.*)$", t_clean)
        if m_art:
            cur_art = m_art.group(1)
            cur_art_title = norm_text(m_art.group(2))
            cur_part = None
            unnumbered_count = 0
            cur_disp = []
            in_note = False
            if re.search(
                r"\b(виключено|втратила чинність|визнано неконституційною|виключена)",
                cur_art_title,
                re.I,
            ):
                cur_art = ""
            continue

        if not cur_art:
            continue

        if re.match(r"^Примітк[аи]\.", t_clean):
            in_note = True
            continue
        if in_note:
            continue

        # Sanction paragraph
        if re.match(r"^[-–—\s]*кара(?:ється|ються)\b", t_clean, re.I):
            if cur_part is not None:
                part_num = cur_part
            else:
                unnumbered_count += 1
                part_num = unnumbered_count
            disp_text = norm_text(" ".join(cur_disp))
            sanc_text = norm_text(re.sub(r"^[-–—\s]+", "", t_clean))

            # Skip if disposition indicates part was excluded
            if re.search(r"\b(виключено|втратила чинність)", disp_text, re.I) and len(disp_text) < 80:
                cur_disp = []
                continue

            parsed = parse_sanction(sanc_text, edition_id)
            art_code = article_to_code(cur_art)
            short_label = f"ст. {cur_art} ч. {part_num}"

            rec = {
                "edition_id": edition_id,
                "snapshot_date": snapshot_date,
                "section_roman": cur_sec,
                "article_str": cur_art,
                "article_code": art_code,
                "part_num": part_num,
                "short_label": short_label,
                "article_title": cur_art_title,
                "disposition_text": disp_text,
                "sanction_text": sanc_text,
            }
            rec.update(parsed)
            records.append(rec)
            cur_disp = []
            continue

        # Numbered part start
        m_part = re.match(r"^(\d+)\.\s+(.*)$", t_clean)
        if m_part:
            cur_part = int(m_part.group(1))
            cur_disp = [m_part.group(2)]
        else:
            cur_disp.append(t_clean)

    return records


def make_lexicographic_key(rec: dict):
    """
    Variant 1 (from most severe to least severe with inversion of alternatives):
    1) Severity group AS (4 > 3 > 2 > 1)
    2) Sequence of present main punishments [P_1, P_2, ...] from most severe to least severe
    3) Additional punishments at the very end: (AL, AM, AN, AO, AP, AQ, AR)
    """
    as_val = int(rec["AS"])
    main_specs = [
        (11, "S", "S"),
        (10, "T", "U"),
        (9, "V", "W"),
        (8, "X", "Y"),
        (7, "Z", "AA"),
        (6, "PN_MAX", "PN_MIN"),
        (5, "AB", "AC"),
        (4, "AD", "AE"),
        (3, "AF", "AG"),
        (2, "AH", "AI"),
        (1, "AJ", "AK"),
    ]
    present_mains = []
    for sev, cmax, cmin in main_specs:
        vmax = float(rec.get(cmax, 0.0) or 0.0)
        vmin = float(rec.get(cmin, 0.0) or 0.0)
        if vmax > 0.0 or vmin > 0.0:
            present_mains.append((sev, vmax, vmin))

    padded = list(present_mains) + [(12, 0.0, 0.0)] * (11 - len(present_mains))
    add_cols = ("AL", "AM", "AN", "AO", "AP", "AQ", "AR")
    add_vals = tuple(float(rec.get(c, 0.0) or 0.0) for c in add_cols)
    return (as_val, tuple(padded), add_vals)


def compute_edition_kzosn(records: list):
    """
    Computes N_max, N_i (dense rank, 1 = most severe), and Index KZOSN for all records in an edition.
    """
    unique_keys = sorted({make_lexicographic_key(r) for r in records}, reverse=True)
    n_max = len(unique_keys)
    key_to_rank = {k: idx + 1 for idx, k in enumerate(unique_keys)}

    for r in records:
        k = make_lexicographic_key(r)
        n_i = key_to_rank[k]
        idx_kzosn = ((n_max - n_i + 1) / n_max) * 100.0 if n_max > 0 else 0.0
        r["rank_n_i"] = n_i
        r["n_max"] = n_max
        r["index_kzosn"] = round(idx_kzosn, 6)

    return records, n_max


def load_convic_crosswalk():
    """
    Loads matched CONVIC counts per norm_id ('year:article:part') from data/kzosn_crosswalk.sqlite.
    """
    if not os.path.exists(CROSSWALK_DB_PATH):
        print(f"Warning: {CROSSWALK_DB_PATH} not found, skipping CONVIC integration.")
        return {}
    uri = "file:" + CROSSWALK_DB_PATH.replace("\\", "/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT norm_id, value, value_status, match_status
        FROM observations
        WHERE norm_id IS NOT NULL
    """).fetchall()
    conn.close()

    convic_map = {}
    for norm_id, val, val_status, match_status in rows:
        convic_map[norm_id] = {
            "convic_count": int(val) if val is not None else None,
            "convic_value_status": val_status,
            "convic_match_status": match_status,
        }
    return convic_map


def compute_edition_convic_index(records: list, edition_id: str, convic_map: dict):
    """
    Attaches CONVIC count and computes the Contextual Conviction Index (I_CONVIC):
      I_i^{CONVIC} = ((M_max - M_i + 1) / M_max) * 100
    where M_max is the number of unique positive CONVIC values in the edition,
    and M_i (1..M_max) is the dense rank from largest CONVIC (M_i = 1 -> 100.0)
    to smallest positive CONVIC (M_i = M_max -> 100 / M_max).
    Norms with no convictions (None or 0) receive index_convic = 0.0.
    """
    has_stats = edition_id.isdigit() and 2013 <= int(edition_id) <= 2025
    pos_values = set()

    for r in records:
        uid = f"{edition_id}:{r['article_str']}:{r['part_num']}"
        info = convic_map.get(uid) if has_stats else None
        val = info["convic_count"] if info else None
        r["convic_count"] = val
        r["convic_match_status"] = info["convic_match_status"] if info else None
        if val is not None and val > 0:
            pos_values.add(val)

    sorted_pos = sorted(pos_values, reverse=True)
    m_max = len(sorted_pos)
    val_to_rank = {v: idx + 1 for idx, v in enumerate(sorted_pos)}

    for r in records:
        val = r["convic_count"]
        if val is not None and val > 0 and m_max > 0:
            m_i = val_to_rank[val]
            idx_convic = ((m_max - m_i + 1) / m_max) * 100.0
            r["convic_rank"] = m_i
            r["convic_n_max"] = m_max
            r["index_convic"] = round(idx_convic, 6)
        else:
            r["convic_rank"] = None
            r["convic_n_max"] = m_max if has_stats else None
            r["index_convic"] = 0.0

    total_convic = sum(r["convic_count"] for r in records if r["convic_count"] is not None)
    active_parts = sum(1 for r in records if (r["convic_count"] or 0) > 0)
    return m_max, total_convic, active_parts


def main():
    all_records = []
    edition_summaries = []
    convic_map = load_convic_crosswalk()

    print("Parsing and computing KZOSN & CONVIC indices across all 27 editions...")
    for ed_id, snap_date, desc in EDITIONS_META:
        html_path = os.path.join(RAW_DIR, f"kk_{ed_id}.html")
        recs = extract_edition_parts(html_path, ed_id, snap_date)
        recs, n_max = compute_edition_kzosn(recs)
        convic_m_max, total_convic, active_convic_parts = compute_edition_convic_index(recs, ed_id, convic_map)
        all_records.extend(recs)

        avg_idx = sum(r["index_kzosn"] for r in recs) / len(recs) if recs else 0
        sev_counts = {s: sum(1 for r in recs if r["AS"] == s) for s in (1, 2, 3, 4)}
        edition_summaries.append({
            "edition_id": ed_id,
            "snapshot_date": snap_date,
            "description": desc,
            "total_parts": len(recs),
            "unique_sanctions_n_max": n_max,
            "avg_index_kzosn": round(avg_idx, 4),
            "sev_1_count": sev_counts[1],
            "sev_2_count": sev_counts[2],
            "sev_3_count": sev_counts[3],
            "sev_4_count": sev_counts[4],
            "convic_unique_m_max": convic_m_max if convic_m_max > 0 else None,
            "convic_active_parts": active_convic_parts if convic_m_max > 0 else None,
            "convic_total_persons": total_convic if convic_m_max > 0 else None,
        })
        print(
            f"  [{ed_id:10s}] parts={len(recs):4d} | N_max={n_max:3d} | avg_KZOSN={avg_idx:6.2f} | "
            f"CONVIC_sum={total_convic:7d} (M_max={convic_m_max:3d})"
        )

    df_all = pd.DataFrame(all_records)
    df_ed = pd.DataFrame(edition_summaries)

    # Create pivot table: rows = (section_roman, article_code, article_str, part_num, short_label), columns = edition_id
    ed_order = [e[0] for e in EDITIONS_META]
    df_pivot = df_all.pivot_table(
        index=["section_roman", "article_code", "article_str", "part_num", "short_label"],
        columns="edition_id",
        values="index_kzosn",
        aggfunc="first",
    ).reset_index()
    meta_cols = ["section_roman", "article_code", "article_str", "part_num", "short_label"]
    df_pivot = df_pivot[meta_cols + [c for c in ed_order if c in df_pivot.columns]]
    df_pivot = df_pivot.sort_values(["article_code", "part_num"]).reset_index(drop=True)

    # Save to SQLite database
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    df_ed.to_sql("editions", conn, index=False)
    df_all.to_sql("article_parts_kzosn", conn, index=False)
    df_pivot.to_sql("kzosn_pivot_by_year", conn, index=False)

    # Create useful indexes in SQLite
    cur = conn.cursor()
    cur.execute("CREATE INDEX idx_parts_ed ON article_parts_kzosn(edition_id)")
    cur.execute("CREATE INDEX idx_parts_art ON article_parts_kzosn(article_code, part_num)")
    cur.execute("CREATE INDEX idx_parts_short ON article_parts_kzosn(short_label)")
    conn.commit()
    conn.close()
    print(f"\nSaved SQLite database to: {DB_PATH}")

    # Save to Excel workbook
    print(f"Writing Excel workbook to: {EXCEL_PATH}...")
    with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl") as writer:
        df_ed.to_excel(writer, sheet_name="Статистика_редакцій", index=False)
        df_pivot.to_excel(writer, sheet_name="Динаміка_КЗОСН_2001_2026", index=False)
        df_curr = df_all[df_all["edition_id"] == "current"].copy()
        df_curr.to_excel(writer, sheet_name="Актуальна_редакція_2026", index=False)
        df_all.to_excel(writer, sheet_name="База_усі_редакції", index=False)

    print("Done!")


if __name__ == "__main__":
    main()
