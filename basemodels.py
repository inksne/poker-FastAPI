from pydantic import BaseModel


class CreateTableRequest(BaseModel):
    name: str
    start_money: int
    big_blind: int