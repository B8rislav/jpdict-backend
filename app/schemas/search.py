from pydantic import BaseModel


class DictEntry(BaseModel):
    id: str
    lang: str
    headword: str | None = None
    reading: str | None = None
    traditional: str | None = None
    simplified: str | None = None
    pinyin: str | None = None
    definitions: list[str]
    part_of_speech: str | None = None
    jlpt_level: int | None = None
    hsk_level: int | None = None
    is_common: bool = False
