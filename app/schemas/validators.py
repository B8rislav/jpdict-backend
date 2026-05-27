from typing import Annotated

from pydantic.functional_validators import BeforeValidator


def _clean_str(v: object) -> object:
    if not isinstance(v, str):
        return v
    v = v.replace("\x00", "")
    if not v.strip():
        raise ValueError("must not be blank")
    return v


SafeStr = Annotated[str, BeforeValidator(_clean_str)]
