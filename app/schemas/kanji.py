from pydantic import BaseModel


class KanjiCard(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "character": "猫",
                "stroke_count": 11,
                "radicals": ["犬"],
                "on_readings": ["ビョウ"],
                "kun_readings": ["ねこ"],
                "meanings": ["кошка", "кот"],
                "meanings_ru": ["кошка", "кот"],
                "jlpt_level": "N3",
            }
        }
    }

    character: str
    stroke_count: int | None
    radicals: list[str]
    on_readings: list[str]
    kun_readings: list[str]
    meanings: list[str]
    meanings_ru: list[str] = []
    jlpt_level: str | None
