from __future__ import annotations

import jieba.posseg as pseg
from pypinyin import Style, pinyin as to_pinyin

# HSK level lookup by word.
# Level key: 1=HSK1 (easiest) … 6=HSK6 (hardest)
_HSK: dict[str, int] = {
    # HSK 1
    "你": 1, "我": 1, "他": 1, "她": 1, "它": 1, "我们": 1, "你们": 1,
    "他们": 1, "好": 1, "是": 1, "不": 1, "在": 1, "人": 1, "有": 1,
    "大": 1, "小": 1, "中": 1, "国": 1, "来": 1, "去": 1, "说": 1,
    "看": 1, "吃": 1, "喝": 1, "买": 1, "学": 1, "汉语": 1, "中文": 1,
    "老师": 1, "学生": 1, "朋友": 1, "爸爸": 1, "妈妈": 1, "书": 1,
    "水": 1, "饭": 1, "今天": 1, "明天": 1, "昨天": 1, "年": 1, "月": 1,
    "日": 1, "号": 1, "一": 1, "二": 1, "三": 1, "四": 1, "五": 1,
    # HSK 2
    "因为": 2, "所以": 2, "但是": 2, "而且": 2, "或者": 2, "还是": 2,
    "身体": 2, "眼睛": 2, "耳朵": 2, "手": 2, "脸": 2, "头": 2,
    "公司": 2, "工作": 2, "问题": 2, "时候": 2, "知道": 2, "觉得": 2,
    # HSK 3
    "经历": 3, "经验": 3, "历史": 3, "文化": 3, "社会": 3, "发展": 3,
    "教育": 3, "环境": 3, "方法": 3, "关系": 3, "情况": 3, "使用": 3,
    # HSK 4
    "政治": 4, "经济": 4, "科技": 4, "影响": 4, "目的": 4, "效果": 4,
    "结果": 4, "意义": 4, "条件": 4, "标准": 4,
    # HSK 5
    "哲学": 5, "心理": 5, "逻辑": 5, "分析": 5, "理论": 5, "概念": 5,
    # HSK 6
    "辩证": 6, "唯物": 6, "辩证法": 6, "辩证唯物": 6,
}


def _word_pinyin(word: str) -> str:
    syllables = to_pinyin(word, style=Style.TONE)
    return " ".join(s[0] for s in syllables if s)


def _hsk_level(word: str) -> int | None:
    return _HSK.get(word)


def tokenize_chinese(text: str) -> list[dict]:
    results = []
    for word, pos in pseg.cut(text):
        if pos == "x" or not word.strip():
            continue
        results.append(
            {
                "surface": word,
                "dictionary_form": word,
                "reading": None,
                "pos": pos,
                "jlpt_level": None,
                "hsk_level": _hsk_level(word),
                "pinyin": _word_pinyin(word),
            }
        )
    return results
