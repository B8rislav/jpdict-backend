from __future__ import annotations

import math
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    total: int
    page: int
    per_page: int
    total_pages: int
    items: list[T]

    @classmethod
    def build(cls, items: list[T], total: int, page: int, per_page: int) -> "Page[T]":
        return cls(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=max(1, math.ceil(total / per_page)),
            items=items,
        )
