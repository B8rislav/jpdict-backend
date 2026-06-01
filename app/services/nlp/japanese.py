from __future__ import annotations

from sudachipy import dictionary, tokenizer

# JLPT level lookup by dictionary form.
# Populated with a starter set; Phase 5 (JMdict import) will extend this via DB.
# Level key: 5=N5 (easiest) … 1=N1 (hardest)
_JLPT: dict[str, int] = {
    # N5
    "私": 5,
    "学生": 5,
    "先生": 5,
    "学校": 5,
    "日本": 5,
    "日本語": 5,
    "英語": 5,
    "食べる": 5,
    "飲む": 5,
    "行く": 5,
    "来る": 5,
    "する": 5,
    "いる": 5,
    "ある": 5,
    "見る": 5,
    "聞く": 5,
    "話す": 5,
    "読む": 5,
    "書く": 5,
    "買う": 5,
    "大きい": 5,
    "小さい": 5,
    "新しい": 5,
    "古い": 5,
    "高い": 5,
    "安い": 5,
    "好き": 5,
    "今日": 5,
    "明日": 5,
    "昨日": 5,
    "今": 5,
    "時間": 5,
    "年": 5,
    "月": 5,
    "日": 5,
    "人": 5,
    "何": 5,
    "語": 5,
    "本": 5,
    "水": 5,
    "山": 5,
    "川": 5,
    "空": 5,
    "海": 5,
    # N4
    "勉強": 4,
    "練習": 4,
    "授業": 4,
    "試験": 4,
    "図書館": 4,
    "病院": 4,
    "電車": 4,
    "駅": 4,
    "旅行": 4,
    "生活": 4,
    "運動": 4,
    "料理": 4,
    "音楽": 4,
    "映画": 4,
    "家族": 4,
    "友達": 4,
    "結婚": 4,
    "仕事": 4,
    # N3
    "経験": 3,
    "社会": 3,
    "問題": 3,
    "意見": 3,
    "情報": 3,
    "方法": 3,
    "関係": 3,
    "場合": 3,
    "気持ち": 3,
    "考える": 3,
    "感じる": 3,
    "使う": 3,
    # N2
    "概念": 2,
    "論理": 2,
    "評価": 2,
    "影響": 2,
    "状況": 2,
    "環境": 2,
    "現在": 2,
    "将来": 2,
    "目的": 2,
    "効果": 2,
    # N1
    "忖度": 1,
    "斟酌": 1,
    "憂慮": 1,
    "懸念": 1,
    "見解": 1,
    "施策": 1,
}

_dict_instance: dictionary.Dictionary | None = None
_tokenizer_instance = None


def _get_tokenizer():
    global _dict_instance, _tokenizer_instance
    if _tokenizer_instance is None:
        _dict_instance = dictionary.Dictionary()
        _tokenizer_instance = _dict_instance.create()
    return _tokenizer_instance


def _jlpt_level(dictionary_form: str) -> int | None:
    return _JLPT.get(dictionary_form)


_SKIP_POS = {"補助記号", "空白"}


def tokenize_japanese(text: str) -> list[dict]:
    """Tokenize Japanese with SudachiPy; returns token dicts (surface, reading, pos, jlpt_level)."""
    t = _get_tokenizer()
    morphemes = t.tokenize(text, tokenizer.Tokenizer.SplitMode.C)
    results = []
    for m in morphemes:
        surface = m.surface()
        pos_tuple = m.part_of_speech()
        pos = pos_tuple[0] if pos_tuple else ""
        if pos in _SKIP_POS or not surface.strip():
            continue
        dict_form = m.dictionary_form()
        reading = m.reading_form()
        results.append(
            {
                "surface": surface,
                "dictionary_form": dict_form,
                "reading": reading,
                "pos": pos,
                "jlpt_level": _jlpt_level(dict_form),
                "hsk_level": None,
                "pinyin": None,
            }
        )
    return results
