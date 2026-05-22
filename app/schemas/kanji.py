from pydantic import BaseModel


class KanjiCard(BaseModel):
    character: str
    stroke_count: int | None
    radicals: list[str]
    on_readings: list[str]
    kun_readings: list[str]
    meanings: list[str]
    jlpt_level: str | None
