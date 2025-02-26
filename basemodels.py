from pydantic import BaseModel
from typing import Optional


class CreateTableRequest(BaseModel):
    name: str
    start_money: Optional[int] = 1000
    big_blind: Optional[int] = 50