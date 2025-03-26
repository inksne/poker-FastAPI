from pydantic import BaseModel, ConfigDict


class CreateTableRequest(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)
    name: str
    start_money: int
    big_blind: int

    @classmethod
    def from_attributes(cls, obj):
        return cls(
            name=obj.name,
            start_money=obj.start_money,
            big_blind=obj.big_blind,
        )