from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

System = Literal["gl", "ma", "fa"]
Role = Literal["analyst", "approver", "admin"]
Band = Literal["low", "medium", "high", "critical"]
Decision = Literal["confirmed", "false_positive"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
