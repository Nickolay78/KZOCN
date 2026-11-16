import re

NUM_WORDS = {
    "одного": 1, "однієї": 1, "один": 1, "одну": 1, "одному": 1,
    "півтора": 1.5,
    "двох": 2, "два": 2, "дві": 2,
    "трьох": 3, "три": 3,
    "чотирьох": 4, "чотири": 4,
    "п'яти": 5, "п'ять": 5,
    "шести": 6, "шість": 6, "шістьох": 6,
    "семи": 7, "сім": 7, "сімох": 7,
    "восьми": 8, "вісім": 8, "вісьмох": 8,
    "дев'яти": 9, "дев'ять": 9,
    "десяти": 10, "десять": 10, "десятьох": 10,
    "одинадцяти": 11, "одинадцять": 11,
    "дванадцяти": 12, "дванадцять": 12,
    "тринадцяти": 13, "тринадцять": 13,
    "чотирнадцяти": 14, "чотирнадцять": 14,
    "п'ятнадцяти": 15, "п'ятнадцять": 15,
    "шістнадцяти": 16, "сімнадцяти": 17, "вісімнадцяти": 18, "дев'ятнадцяти": 19,
    "двадцяти": 20, "двадцять": 20,
    "тридцяти": 30, "тридцять": 30,
    "сорока": 40, "сорок": 40,
    "п'ятдесяти": 50, "п'ятдесят": 50,
    "шістдесяти": 60, "шістдесят": 60,
    "сімдесяти": 70, "сімдесят": 70,
    "вісімдесяти": 80, "вісімдесят": 80,
    "дев'яноста": 90, "дев'яносто": 90,
    "ста": 100, "сто": 100,
    "двохсот": 200, "двісті": 200,
    "трьохсот": 300, "триста": 300,
    "чотирьохсот": 400, "чотириста": 400,
    "п'ятисот": 500, "п'ятсот": 500,
    "шестисот": 600, "шістсот": 600,
    "семисот": 700, "сімсот": 700,
    "восьмисот": 800, "вісімсот": 800,
    "дев'ятисот": 900, "дев'ятсот": 900,
}


def norm_text(s: str) -> str:
    s = s.replace("’", "'").replace("ʼ", "'").replace("`", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_uk_number(phrase: str):
    phrase = norm_text(phrase.lower())
    phrase = re.sub(r"(тисяч[іау]?)", r" \1 ", phrase)
    tokens = re.findall(r"[а-яіїєґ']+|\d+(?:[.,]\d+)?", phrase)
    if not tokens:
        return None

    total = 0.0
    current = 0.0
    matched_any = False

    for tok in tokens:
        if re.match(r"^\d+(?:[.,]\d+)?$", tok):
            current += float(tok.replace(",", "."))
            matched_any = True
        elif tok in NUM_WORDS:
            current += NUM_WORDS[tok]
            matched_any = True
        elif tok in ("тисячі", "тисяч", "тисяча", "тисячу"):
            if current == 0:
                current = 1.0
            total += current * 1000.0
            current = 0.0
            matched_any = True
        elif tok in ("мільйона", "мільйонів", "мільйон"):
            if current == 0:
                current = 1.0
            total += current * 1_000_000.0
            current = 0.0
            matched_any = True

    if not matched_any:
        return None
    return total + current


def extract_bounds(clause: str, default_min: float, target_unit: str = "years", prev_bounds=None):
    """
    Extract (max_val, min_val, explicit_min) from a single punishment clause.
    prev_bounds is (prev_max, prev_explicit_min_or_None).
    """
    cl = norm_text(clause.lower())

    if re.search(r"на\s+т(?:ой|акий)\s+(?:самий|же)\s+строк", cl) and prev_bounds is not None:
        pmax, p_exp_min = prev_bounds
        vmin = max(p_exp_min, default_min) if p_exp_min is not None else default_min
        return (pmax, vmin, p_exp_min)

    # 1. "від A до B"
    m_vid_do = re.search(
        r"від\s+([а-яіїєґ'\s\d]+?)\s+до\s+([а-яіїєґ'\s\d]+?)(?:\s+(років|року|рік|місяців|місяця|місяць|годин|години|неоподатковуваних|мінімумів)|$|,|;|\bабо\b|\bчи\b|\bз\b|\bіз\b|\bзі\b|\bта\b)",
        cl
    )
    if m_vid_do:
        raw_min = m_vid_do.group(1).strip()
        raw_max = m_vid_do.group(2).strip()
        end_unit = (m_vid_do.group(3) or "").strip()

        min_unit = end_unit
        if "місяц" in raw_min:
            min_unit = "місяців"
            raw_min = re.sub(r"\bмісяц\w*", "", raw_min).strip()
        elif "рок" in raw_min or "рік" in raw_min:
            min_unit = "років"
            raw_min = re.sub(r"\b(?:рок\w*|рік)", "", raw_min).strip()

        vmin = parse_uk_number(raw_min)
        vmax = parse_uk_number(raw_max)
        if vmin is not None and vmax is not None:
            if target_unit == "years":
                if "місяц" in min_unit:
                    vmin = round(vmin / 12.0, 4)
                if "місяц" in end_unit:
                    vmax = round(vmax / 12.0, 4)
            elif target_unit == "months":
                if "рок" in min_unit or "рік" in min_unit:
                    vmin = vmin * 12.0
                if "рок" in end_unit or "рік" in end_unit:
                    vmax = vmax * 12.0
            elif target_unit == "nmdg":
                if "тисяч" in raw_max and "тисяч" not in m_vid_do.group(1) and vmin < 100:
                    vmin *= 1000.0
            return (vmax, vmin, vmin)

    # 2. "до B"
    m_do = re.search(
        r"\bдо\s+([а-яіїєґ'\s\d]+?)(?:\s+(років|року|рік|місяців|місяця|місяць|годин|години|неоподатковуваних|мінімумів)|$|,|;|\bабо\b|\bчи\b|\bз\b|\bіз\b|\bзі\b|\bта\b)",
        cl
    )
    if m_do:
        raw_max = m_do.group(1).strip()
        end_unit = (m_do.group(2) or "").strip()
        vmax = parse_uk_number(raw_max)
        if vmax is not None:
            if target_unit == "years" and "місяц" in end_unit:
                vmax = round(vmax / 12.0, 4)
            elif target_unit == "months" and ("рок" in end_unit or "рік" in end_unit):
                vmax = vmax * 12.0
            return (vmax, default_min, None)

    # 3. Fixed value
    m_fixed = re.search(
        r"(?:на\s+строк|у\s+розмірі|в\s+розмірі|штрафом)\s+([а-яіїєґ'\s\d]+?)\s+(років|року|рік|місяців|місяця|місяць|годин|години|неоподатковуваних|мінімумів)",
        cl
    )
    if m_fixed:
        raw_val = m_fixed.group(1).strip()
        end_unit = m_fixed.group(2).strip()
        val = parse_uk_number(raw_val)
        if val is not None:
            if target_unit == "years" and "місяц" in end_unit:
                val = round(val / 12.0, 4)
            elif target_unit == "months" and ("рок" in end_unit or "рік" in end_unit):
                val = val * 12.0
            vmin = default_min if target_unit == "nmdg" else val
            return (val, vmin, vmin)

    return None


def parse_sanction(sanction_text: str, edition_id: str = "2020") -> dict:
    s = norm_text(sanction_text)
    s_low = s.lower()

    res = {
        "S": 0.0,
        "T": 0.0, "U": 0.0,
        "V": 0.0, "W": 0.0,
        "X": 0.0, "Y": 0.0,
        "Z": 0.0, "AA": 0.0,
        "PN_MAX": 0.0, "PN_MIN": 0.0,
        "AB": 0.0, "AC": 0.0,
        "AD": 0.0, "AE": 0.0,
        "AF": 0.0, "AG": 0.0,
        "AH": 0.0, "AI": 0.0,
        "AJ": 0.0, "AK": 0.0,
        "AL": 0.0,
        "AM": 0.0, "AN": 0.0, "AO": 0.0,
        "AP": 0.0, "AQ": 0.0, "AR": 0.0,
        "AS": 1,
    }

    # 1a. Confiscation of property (AL)
    m_conf = re.search(
        r"(?:з|із|та)\s+конфіскацією\s+майна(?:\s+(?:або|чи)\s+без\s+такої|\s+у\s+випадку)?",
        s_low
    )
    if m_conf:
        conf_str = m_conf.group(0)
        is_opt = ("без такої" in conf_str) or ("у випадку" in conf_str)
        if edition_id in ("2001", "2001_09_01"):
            res["AL"] = 1.0
        else:
            res["AL"] = 1.0 if is_opt else 2.0

    # Protect "обіймати певні посади або/чи займатися певною діяльністю" and "або/чи без такого/такої"
    s_prot = re.sub(r"(посади\s+)(?:або|чи)(\s+займатися)", r"\1_OR_\2", s_low)
    s_prot = re.sub(r"(?:або|чи)(\s+без\s+так(?:ого|ої))", r"_OR_\1", s_prot)

    # 1b. Additional deprivation of right (AM, AN, AO)
    m_add_right = re.search(
        r"(?:з|із)\s+позбавленням\s+права\s+обіймати\s+певні\s+посади[^.;]*?(?=(?:,\s*)?\b(?:або|чи)\b|(?:,\s*)?(?:з|із|зі|та\s+з|та\s+зі)\s+(?:штрафом|конфіскацією)|\.|;|$)",
        s_prot
    )
    if m_add_right:
        ar_str = m_add_right.group(0).replace("_OR_", "або")
        is_opt = bool(re.search(r"без\s+такого", ar_str))
        if edition_id in ("2001", "2001_09_01"):
            res["AM"] = 0.0
        else:
            res["AM"] = 1.0 if is_opt else 2.0
        b = extract_bounds(ar_str, default_min=1.0, target_unit="years")
        if b:
            res["AN"], res["AO"] = b[0], b[1]
        else:
            res["AN"], res["AO"] = 3.0, 1.0

    # 1c. Additional fine (AP, AQ, AR)
    m_add_fine = re.search(
        r"(?:з|зі|із)\s+штрафом\s+[^.;]*?(?=(?:,\s*)?\b(?:або|чи)\b|(?:,\s*)?(?:з|із|та\s+з)\s+(?:позбавленням|конфіскацією)|\.|;|$)",
        s_prot
    )
    if m_add_fine:
        af_str = m_add_fine.group(0).replace("_OR_", "або")
        is_opt = bool(re.search(r"без\s+такого", af_str))
        if edition_id in ("2001", "2001_09_01"):
            res["AP"] = 0.0
        else:
            res["AP"] = 1.0 if is_opt else 2.0
        b = extract_bounds(af_str, default_min=30.0, target_unit="nmdg")
        if b:
            res["AQ"], res["AR"] = b[0], b[1]

    # Remove additional punishments from s_prot
    main_part = s_prot
    if m_add_right:
        main_part = main_part.replace(m_add_right.group(0), " ")
    if m_add_fine:
        main_part = main_part.replace(m_add_fine.group(0), " ")
    main_part = re.sub(r"(?:,\s*)?(?:та\s+)?(?:з|із)\s+конфіскацією.*$", "", main_part)

    clauses = re.split(r"\b(?:або|чи)\b", main_part)
    prev_term_bounds = None

    for raw_cl in clauses:
        cl = raw_cl.replace("_OR_", "або").strip()
        if not cl:
            continue

        if "довічним позбавленням волі" in cl or "довічне позбавлення волі" in cl:
            res["S"] = 1.0
            continue

        if "позбавленням волі" in cl or "позбавлення волі" in cl:
            b = extract_bounds(cl, default_min=1.0, target_unit="years", prev_bounds=prev_term_bounds)
            if b:
                res["T"], res["U"] = b[0], b[1]
                prev_term_bounds = (b[0], b[2])
            continue

        if "дисциплінарному батальйоні" in cl or "дисциплінарного батальйону" in cl:
            b = extract_bounds(cl, default_min=0.5, target_unit="years", prev_bounds=prev_term_bounds)
            if b:
                res["V"], res["W"] = b[0], b[1]
                prev_term_bounds = (b[0], b[2])
            continue

        if "обмеженням волі" in cl or "обмеження волі" in cl:
            b = extract_bounds(cl, default_min=1.0, target_unit="years", prev_bounds=prev_term_bounds)
            if b:
                res["X"], res["Y"] = b[0], b[1]
                prev_term_bounds = (b[0], b[2])
            continue

        if "пробаційним наглядом" in cl or "пробаційний нагляд" in cl:
            b = extract_bounds(cl, default_min=1.0, target_unit="years", prev_bounds=prev_term_bounds)
            if b:
                res["PN_MAX"], res["PN_MIN"] = b[0], b[1]
                prev_term_bounds = (b[0], b[2])
            continue

        if "арештом" in cl or "арешт" in cl:
            b = extract_bounds(cl, default_min=1.0, target_unit="months", prev_bounds=None)
            if b:
                res["Z"], res["AA"] = b[0], b[1]
            continue

        if "службовим обмеженням" in cl or "службовими обмеженнями" in cl or "службове обмеження" in cl:
            b = extract_bounds(cl, default_min=0.5, target_unit="years", prev_bounds=prev_term_bounds)
            if b:
                res["AB"], res["AC"] = b[0], b[1]
                prev_term_bounds = (b[0], b[2])
            continue

        if "виправними роботами" in cl or "виправні роботи" in cl:
            b = extract_bounds(cl, default_min=0.5, target_unit="years", prev_bounds=prev_term_bounds)
            if b:
                res["AD"], res["AE"] = b[0], b[1]
                prev_term_bounds = (b[0], b[2])
            continue

        if "громадськими роботами" in cl or "громадські роботи" in cl:
            b = extract_bounds(cl, default_min=60.0, target_unit="hours", prev_bounds=None)
            if b:
                res["AF"], res["AG"] = b[0], b[1]
            continue

        if "позбавленням права" in cl or "позбавлення права" in cl:
            b = extract_bounds(cl, default_min=2.0, target_unit="years", prev_bounds=prev_term_bounds)
            if b:
                res["AH"], res["AI"] = b[0], b[1]
                prev_term_bounds = (b[0], b[2])
            continue

        if "штрафом" in cl or "штраф" in cl:
            b = extract_bounds(cl, default_min=30.0, target_unit="nmdg", prev_bounds=None)
            if b:
                res["AJ"], res["AK"] = b[0], b[1]
            else:
                res["AJ"], res["AK"] = 30.0, 30.0
            continue

    res["AS"] = compute_severity(res, edition_id)
    return res


def compute_severity(res: dict, edition_id: str) -> int:
    s = res["S"]
    t = res["T"]
    aj = res["AJ"]

    if edition_id in ("2001", "2001_09_01"):
        year = 2001
    elif edition_id == "current":
        year = 2026
    else:
        year = int(edition_id[:4])

    if year <= 2011:
        if s > 0 or t > 10:
            return 4
        if t > 5:
            return 3
        if t > 2:
            return 2
        return 1
    elif year <= 2019:
        if s > 0 or t > 0:
            if s > 0 or t > 10:
                return 4
            if t > 5:
                return 3
            if t > 2:
                return 2
            return 1
        else:
            if aj > 25000:
                return 4
            if aj > 10000:
                return 3
            if aj > 3000:
                return 2
            return 1
    else:
        if s > 0 or t > 0:
            if s > 0 or t > 10:
                return 4
            if t > 5:
                return 3
            return 2
        else:
            if aj > 25000:
                return 4
            if aj > 10000:
                return 3
            if aj > 3000:
                return 2
            return 1
