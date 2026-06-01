from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.kanji import KanjiCard, KanjiComponent
from app.schemas.search import DictEntry
from app.services.search.normalize import NormalizedQuery

# Kangxi radical number → representative character
KANGXI: dict[int, str] = {
    1: "一",
    2: "丨",
    3: "丶",
    4: "丿",
    5: "乙",
    6: "亅",
    7: "二",
    8: "亠",
    9: "人",
    10: "儿",
    11: "入",
    12: "八",
    13: "冂",
    14: "冖",
    15: "冫",
    16: "几",
    17: "凵",
    18: "刀",
    19: "力",
    20: "勹",
    21: "匕",
    22: "匚",
    23: "匸",
    24: "十",
    25: "卜",
    26: "卩",
    27: "厂",
    28: "厶",
    29: "又",
    30: "口",
    31: "囗",
    32: "土",
    33: "士",
    34: "夂",
    35: "夊",
    36: "夕",
    37: "大",
    38: "女",
    39: "子",
    40: "宀",
    41: "寸",
    42: "小",
    43: "尢",
    44: "尸",
    45: "屮",
    46: "山",
    47: "巛",
    48: "工",
    49: "己",
    50: "巾",
    51: "干",
    52: "幺",
    53: "广",
    54: "廴",
    55: "廾",
    56: "弋",
    57: "弓",
    58: "彐",
    59: "彡",
    60: "彳",
    61: "心",
    62: "戈",
    63: "戸",
    64: "手",
    65: "支",
    66: "攴",
    67: "文",
    68: "斗",
    69: "斤",
    70: "方",
    71: "无",
    72: "日",
    73: "曰",
    74: "月",
    75: "木",
    76: "欠",
    77: "止",
    78: "歹",
    79: "殳",
    80: "毋",
    81: "比",
    82: "毛",
    83: "氏",
    84: "气",
    85: "水",
    86: "火",
    87: "爪",
    88: "父",
    89: "爻",
    90: "爿",
    91: "片",
    92: "牙",
    93: "牛",
    94: "犬",
    95: "玄",
    96: "玉",
    97: "瓜",
    98: "瓦",
    99: "甘",
    100: "生",
    101: "用",
    102: "田",
    103: "疋",
    104: "疒",
    105: "癶",
    106: "白",
    107: "皮",
    108: "皿",
    109: "目",
    110: "矛",
    111: "矢",
    112: "石",
    113: "示",
    114: "禸",
    115: "禾",
    116: "穴",
    117: "立",
    118: "竹",
    119: "米",
    120: "糸",
    121: "缶",
    122: "网",
    123: "羊",
    124: "羽",
    125: "老",
    126: "而",
    127: "耒",
    128: "耳",
    129: "聿",
    130: "肉",
    131: "臣",
    132: "自",
    133: "至",
    134: "臼",
    135: "舌",
    136: "舛",
    137: "舟",
    138: "艮",
    139: "色",
    140: "艸",
    141: "虍",
    142: "虫",
    143: "血",
    144: "行",
    145: "衣",
    146: "西",
    147: "見",
    148: "角",
    149: "言",
    150: "谷",
    151: "豆",
    152: "豕",
    153: "豸",
    154: "貝",
    155: "赤",
    156: "走",
    157: "足",
    158: "身",
    159: "車",
    160: "辛",
    161: "辰",
    162: "辵",
    163: "邑",
    164: "酉",
    165: "釆",
    166: "里",
    167: "金",
    168: "長",
    169: "門",
    170: "阜",
    171: "隶",
    172: "隹",
    173: "雨",
    174: "青",
    175: "非",
    176: "面",
    177: "革",
    178: "韋",
    179: "韭",
    180: "音",
    181: "頁",
    182: "風",
    183: "飛",
    184: "食",
    185: "首",
    186: "香",
    187: "馬",
    188: "骨",
    189: "高",
    190: "髟",
    191: "鬥",
    192: "鬯",
    193: "鬲",
    194: "鬼",
    195: "魚",
    196: "鳥",
    197: "鹵",
    198: "鹿",
    199: "麥",
    200: "麻",
    201: "黃",
    202: "黍",
    203: "黑",
    204: "黹",
    205: "黽",
    206: "鼎",
    207: "鼓",
    208: "鼠",
    209: "鼻",
    210: "齊",
    211: "齒",
    212: "龍",
    213: "龜",
    214: "龠",
}


def _has_japanese(value: str) -> bool:
    return any("぀" <= c <= "鿿" for c in value)


async def search_jmdict(
    query: str,
    session: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    def_lang: str = "ru",
) -> tuple[list[DictEntry], int]:
    """Forward-search JMdict by JP surface/reading or EN/RU gloss prefix; returns (entries, n)."""
    if _has_japanese(query):
        where = "(:val = ANY(kanji_forms)) OR (:val = ANY(reading_forms))"
    else:
        where = """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(senses) s,
                 jsonb_array_elements_text(
                     CASE WHEN jsonb_array_length(s -> 'ru') > 0 THEN s -> 'ru' ELSE s -> 'en' END
                 ) g
            WHERE lower(g) LIKE lower(:val) || '%'
        )"""

    rows = (
        (
            await session.execute(
                text(
                    f"""
                SELECT entry_id, kanji_forms, reading_forms, senses, jlpt_level, common
                FROM jmdict_entries
                WHERE {where}
                ORDER BY common DESC, jlpt_level ASC NULLS LAST
                LIMIT :lim OFFSET :off
                """
                ),
                {"val": query, "lim": limit, "off": offset},
            )
        )
        .mappings()
        .all()
    )

    total_count: int = (
        await session.execute(
            text(f"SELECT COUNT(*) FROM jmdict_entries WHERE {where}"),
            {"val": query},
        )
    ).scalar_one()

    results: list[DictEntry] = []
    for row in rows:
        senses = row["senses"] or []
        pos: str | None = None
        all_ru: list[str] = []
        all_en: list[str] = []
        for sense in senses:
            if not pos and sense.get("pos"):
                pos = sense["pos"][0]
            all_ru.extend(sense.get("ru") or [])
            all_en.extend(sense.get("en") or [])
        defs = (
            (all_en if all_en else all_ru) if def_lang == "en" else (all_ru if all_ru else all_en)
        )

        results.append(
            DictEntry(
                id=str(row["entry_id"]),
                lang="jp",
                headword=row["kanji_forms"][0] if row["kanji_forms"] else None,
                reading=row["reading_forms"][0] if row["reading_forms"] else None,
                definitions=defs,
                part_of_speech=pos,
                jlpt_level=row["jlpt_level"],
                is_common=bool(row["common"]),
            )
        )
    return results, total_count


async def search_jmdict_reverse(
    normalized: NormalizedQuery,
    session: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    def_lang: str = "ru",
) -> tuple[list[DictEntry], int]:
    """Reverse-search JMdict by a normalized EN/RU keyword; returns (entries, total_count)."""
    col = "senses_glosses_ru" if normalized.script == "ru" else "senses_glosses_en"
    params = {
        "text": normalized.text,
        "lim": limit,
        "off": offset,
    }

    # Skips leading "1) ", "(...) ", "[...] " markers when matching at line start,
    # so "мужчина" is treated as a primary meaning of "1) мужчина; ..." but not
    # of "оннагата (мужчина-актёр...)".
    primary_prefix = r"(?:\d+\)\s*|\([^)]*\)\s*|\[[^\]]*\]\s*)*"

    # Rank 0: gloss line equals text (exact match)
    # Rank 1: gloss line starts with text after optional numbering/marker prefix (primary meaning)
    # Rank 2: text appears as a complete word elsewhere
    where = (
        f"{col} ~* ('(?:^|\\n)' || :text || '(?:\\n|$)')"
        f" OR {col} ~* ('(?:^|\\n){primary_prefix}' || :text || '(?:\\W|$)')"
        f" OR {col} ~* ('\\m' || :text || '\\M')"
    )
    rank_expr = (
        f"CASE"
        f" WHEN {col} ~* ('(?:^|\\n)' || :text || '(?:\\n|$)') THEN 0"
        f" WHEN {col} ~* ('(?:^|\\n){primary_prefix}' || :text || '(?:\\W|$)') THEN 1"
        f" WHEN {col} ~* ('\\m' || :text || '\\M') THEN 2"
        f" ELSE 3"
        f" END"
    )

    rows = (
        (
            await session.execute(
                text(
                    f"""
                SELECT entry_id, kanji_forms, reading_forms, senses, jlpt_level, common,
                       {rank_expr} AS rank
                FROM jmdict_entries
                WHERE {where}
                ORDER BY rank ASC, common DESC, jlpt_level ASC NULLS LAST
                LIMIT :lim OFFSET :off
                """
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    total_count: int = (
        await session.execute(
            text(f"SELECT COUNT(*) FROM jmdict_entries WHERE {where}"),
            {"text": normalized.text},
        )
    ).scalar_one()

    results: list[DictEntry] = []
    for row in rows:
        senses = row["senses"] or []
        pos: str | None = None
        all_ru: list[str] = []
        all_en: list[str] = []
        for sense in senses:
            if not pos and sense.get("pos"):
                pos = sense["pos"][0]
            all_ru.extend(sense.get("ru") or [])
            all_en.extend(sense.get("en") or [])
        defs = (
            (all_en if all_en else all_ru) if def_lang == "en" else (all_ru if all_ru else all_en)
        )

        results.append(
            DictEntry(
                id=str(row["entry_id"]),
                lang="jp",
                headword=row["kanji_forms"][0] if row["kanji_forms"] else None,
                reading=row["reading_forms"][0] if row["reading_forms"] else None,
                definitions=defs,
                part_of_speech=pos,
                jlpt_level=row["jlpt_level"],
                is_common=bool(row["common"]),
            )
        )
    return results, total_count


async def _resolve_components(chars: list[str], session: AsyncSession) -> list[KanjiComponent]:
    """Look up each composite part's own meanings from kanjidic_entries.

    Components are KRADFILE radical characters; most exist as standalone kanji
    entries (so they have meanings), a handful of katakana-shaped shapes do not.
    Order is preserved; unknown components are returned with empty meanings.
    """
    if not chars:
        return []

    rows = (
        (
            await session.execute(
                text(
                    """
                SELECT character, meanings_en, meanings_ru
                FROM kanjidic_entries
                WHERE character = ANY(:chars)
                """
                ),
                {"chars": chars},
            )
        )
        .mappings()
        .all()
    )
    by_char = {r["character"]: r for r in rows}

    components: list[KanjiComponent] = []
    for ch in chars:
        r = by_char.get(ch)
        c_ru = (r["meanings_ru"] if r else None) or []
        c_en = (r["meanings_en"] if r else None) or []
        components.append(
            KanjiComponent(
                character=ch,
                meanings=c_ru if c_ru else c_en,
                meanings_ru=c_ru,
                meanings_en=c_en,
            )
        )
    return components


async def get_kanji_detail(char: str, session: AsyncSession) -> KanjiCard | None:
    """Build the KanjiCard (readings, radicals, components) for one kanji, or None if absent."""
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT character, stroke_count, jlpt_level,
                       on_readings, kun_readings, meanings_en, meanings_ru,
                       radical_number, components
                FROM kanjidic_entries
                WHERE character = :c
                """
                ),
                {"c": char},
            )
        )
        .mappings()
        .first()
    )

    if row is None:
        return None

    radical_char = KANGXI.get(row["radical_number"] or 0, "")
    radicals = [radical_char] if radical_char else []
    components = await _resolve_components(list(row["components"] or []), session)
    jlpt = f"N{row['jlpt_level']}" if row["jlpt_level"] else None
    meanings_ru = row["meanings_ru"] or []
    meanings_en = row["meanings_en"] or []

    return KanjiCard(
        character=char,
        stroke_count=row["stroke_count"],
        radicals=radicals,
        components=components,
        on_readings=row["on_readings"] or [],
        kun_readings=row["kun_readings"] or [],
        meanings=meanings_ru if meanings_ru else meanings_en,
        meanings_ru=meanings_ru,
        meanings_en=meanings_en,
        jlpt_level=jlpt,
    )
