import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "kzocn_kk_ukraine.db")
WEB_DIR = os.path.join(BASE_DIR, "web")
os.makedirs(WEB_DIR, exist_ok=True)

SECTION_TITLES = {
    "I": "Розділ I. Злочини проти основ національної безпеки України",
    "II": "Розділ II. Кримінальні правопорушення проти життя та здоров'я особи",
    "III": "Розділ III. Кримінальні правопорушення проти волі, честі та гідності особи",
    "IV": "Розділ IV. Кримінальні правопорушення проти статевої свободи та статевої недоторканості особи",
    "V": "Розділ V. Кримінальні правопорушення проти виборчих, трудових та інших особистих прав і свобод людини і громадянина",
    "VI": "Розділ VI. Кримінальні правопорушення проти власності",
    "VII": "Розділ VII. Кримінальні правопорушення у сфері господарської діяльності",
    "VIII": "Розділ VIII. Кримінальні правопорушення проти довкілля",
    "IX": "Розділ IX. Кримінальні правопорушення проти громадської безпеки",
    "X": "Розділ X. Кримінальні правопорушення проти безпеки виробництва",
    "XI": "Розділ XI. Кримінальні правопорушення проти безпеки руху та експлуатації транспорту",
    "XII": "Розділ XII. Кримінальні правопорушення проти громадського порядку та моральності",
    "XIII": "Розділ XIII. Кримінальні правопорушення у сфері обігу наркотичних засобів, психотропних речовин, їх аналогів або прекурсорів та інші проти здоров'я населення",
    "XIV": "Розділ XIV. Кримінальні правопорушення у сфері охорони державної таємниці, недоторканності державних кордонів, забезпечення призову та мобілізації",
    "XV": "Розділ XV. Кримінальні правопорушення проти авторитету органів державної влади, органів місцевого самоврядування, об'єднань громадян та кримінальні правопорушення проти журналістів",
    "XVI": "Розділ XVI. Кримінальні правопорушення у сфері використання електронно-обчислювальних машин (комп'ютерів), систем та комп'ютерних мереж і мереж електрозв'язку",
    "XVII": "Розділ XVII. Кримінальні правопорушення у сфері службової діяльності та професійної діяльності, пов'язаної з наданням публічних послуг",
    "XVIII": "Розділ XVIII. Кримінальні правопорушення проти правосуддя",
    "XIX": "Розділ XIX. Кримінальні правопорушення проти встановленого порядку несення військової служби (військові кримінальні правопорушення)",
    "XX": "Розділ XX. Кримінальні правопорушення проти миру, безпеки людства та міжнародного правопорядку",
}

ROMAN_ORDER = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"
]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM editions")
    editions = [dict(r) for r in cur.fetchall()]

    # Fetch all part records including parsed punishment vector columns S..AR
    vec_cols = [
        "S", "T", "U", "V", "W", "X", "Y", "Z", "AA", "PN_MAX", "PN_MIN",
        "AB", "AC", "AD", "AE", "AF", "AG", "AH", "AI", "AJ", "AK",
        "AL", "AM", "AN", "AO", "AP", "AQ", "AR"
    ]
    cur.execute(f"""
        SELECT
            edition_id, section_roman, article_str, article_code, part_num,
            short_label, article_title, disposition_text, sanction_text,
            rank_n_i, n_max, index_kzosn, [AS] as severity,
            convic_count, convic_rank, convic_n_max, index_convic, convic_match_status,
            {", ".join(vec_cols)}
        FROM article_parts_kzosn
        ORDER BY article_code, part_num
    """)
    rows = cur.fetchall()

    # Deduplicate strings and punishment vectors into lookup tables to keep data.js compact and fast
    titles_map = {}
    titles_list = []
    sanc_map = {}
    sanc_list = []
    disp_map = {}
    disp_list = []
    vec_map = {}
    vec_list = []

    def get_id(text, mp, lst):
        if text not in mp:
            mp[text] = len(lst)
            lst.append(text)
        return mp[text]

    by_edition = {e["edition_id"]: [] for e in editions}
    history_by_norm = {}

    for r in rows:
        ed = r["edition_id"]
        norm_key = f"{r['article_str']}|{r['part_num']}"
        tid = get_id(r["article_title"], titles_map, titles_list)
        sid = get_id(r["sanction_text"], sanc_map, sanc_list)
        disp_short = r["disposition_text"][:350] + ("..." if len(r["disposition_text"]) > 350 else "")
        did = get_id(disp_short, disp_map, disp_list)

        convic_cnt = int(r["convic_count"]) if r["convic_count"] is not None else None
        idx_convic = round(float(r["index_convic"] or 0.0), 2)
        c_rank = int(r["convic_rank"]) if r["convic_rank"] is not None else None
        c_nmax = int(r["convic_n_max"]) if r["convic_n_max"] is not None else None

        vec_tuple = tuple(round(float(r[c] or 0.0), 4) for c in vec_cols)
        if vec_tuple not in vec_map:
            vec_map[vec_tuple] = len(vec_list)
            vec_list.append(list(vec_tuple))
        vid = vec_map[vec_tuple]

        item = [
            r["section_roman"],           # 0: section
            r["article_str"],             # 1: article_str
            r["article_code"],            # 2: article_code
            r["part_num"],                # 3: part_num
            r["short_label"],             # 4: short_label
            round(r["index_kzosn"], 2),   # 5: index_kzosn
            r["rank_n_i"],                # 6: rank_n_i
            r["n_max"],                   # 7: n_max
            r["severity"],                # 8: severity (1..4)
            tid,                          # 9: title_id
            did,                          # 10: disp_id
            sid,                          # 11: sanc_id
            convic_cnt,                   # 12: convic_count (number of convicted persons or null)
            idx_convic,                   # 13: index_convic (0..100)
            c_rank,                       # 14: convic_rank (M_i)
            c_nmax,                       # 15: convic_n_max (M_max)
            vid,                          # 16: vec_id (punishment vector S..AR index)
        ]
        by_edition[ed].append(item)

        if norm_key not in history_by_norm:
            history_by_norm[norm_key] = {
                "section": r["section_roman"],
                "article": r["article_str"],
                "part": r["part_num"],
                "label": r["short_label"],
                "title_id": tid,
                "series": {}
            }
        history_by_norm[norm_key]["title_id"] = tid
        history_by_norm[norm_key]["series"][ed] = [
            round(r["index_kzosn"], 2),   # 0: index_kzosn
            r["rank_n_i"],                # 1: rank_n_i
            r["n_max"],                   # 2: n_max
            r["severity"],                # 3: severity
            sid,                          # 4: sanc_id
            did,                          # 5: disp_id
            convic_cnt,                   # 6: convic_count
            idx_convic,                   # 7: index_convic
            c_rank,                       # 8: convic_rank
            c_nmax,                       # 9: convic_n_max
        ]

    payload = {
        "editions": editions,
        "sections": [{"id": rom, "num": idx + 1, "title": SECTION_TITLES[rom]} for idx, rom in enumerate(ROMAN_ORDER)],
        "vecCols": vec_cols,
        "vectors": vec_list,
        "titles": titles_list,
        "sanctions": sanc_list,
        "dispositions": disp_list,
        "byEdition": by_edition,
        "history": history_by_norm,
    }

    js_path = os.path.join(WEB_DIR, "data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.KZOCN_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    print(f"Exported web bundle to {js_path} ({os.path.getsize(js_path):,} bytes)")


if __name__ == "__main__":
    main()
