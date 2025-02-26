from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional

from exceptions import bad_email_exc


class UserSchema(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)
    username: str
    password: str | bytes
    email: Optional[EmailStr] = None

    @classmethod
    def from_attributes(cls, obj):
        return cls(
            username=obj.username,
            password=obj.password,
            email=obj.email,
        )
    
    @field_validator('email', mode='before')
    def check_email(cls, v):
        if v in [None, '', 'null'] or '@' not in v or '.' not in v:
            raise bad_email_exc
        return v