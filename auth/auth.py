from fastapi import APIRouter, Depends, Response, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer
from starlette import status

from auth.helpers import create_access_token, create_refresh_token
from auth.validation import (
    get_current_access_token_payload,
    get_current_auth_user_for_refresh,
    get_current_auth_user,
    validate_auth_user_db,
    validate_email
)
from auth.utils import hash_password

from database.database import get_async_session
from database.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from exceptions import conflict_name, bad_email_exc

from pydantic import BaseModel
from datetime import timedelta


http_bearer = HTTPBearer(auto_error=False)


class TokenInfo(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"


router = APIRouter(prefix='/jwt', tags=["JWT"], dependencies=[Depends(http_bearer)])


@router.post('/register')
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_async_session)
):
    try:
        hashed_password = hash_password(password).decode('utf-8')
        new_user = User(username=username, password=hashed_password, email=email)

        validate_email(email)

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        return RedirectResponse('/jwt/login/', status_code=status.HTTP_303_SEE_OTHER)
    except IntegrityError:
        raise conflict_name
    except HTTPException:
        raise bad_email_exc


@router.post('/login/', response_model=TokenInfo)
async def auth_user_issue_jwt(response: Response, user: User = Depends(validate_auth_user_db)):
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    response.set_cookie(
        key="access_token",
          value=access_token,
            httponly=False,
              secure=False,
                samesite="Lax",
                  max_age=int(timedelta(minutes=5).total_seconds()))
    
    response.set_cookie(
        key="refresh_token",
          value=refresh_token,
            httponly=False,
              secure=False,
                samesite="Lax",
                  max_age=int(timedelta(days=30).total_seconds()))
    
    return TokenInfo(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh/")
async def refresh_jwt(current_user: User = Depends(get_current_auth_user_for_refresh)):
    new_access_token = create_access_token(current_user)
    response = JSONResponse(content={"access_token": new_access_token})
    response.set_cookie(
        key="access_token",
          value=new_access_token,
            httponly=False,  
              secure=False,    
                samesite="Lax",  
                  max_age=int(timedelta(minutes=1).total_seconds())) 
    
    return response


@router.get('/users/me/')
async def auth_user_check_self_info(
    payload: dict = Depends(get_current_access_token_payload), 
    user: User = Depends(get_current_auth_user),
):
    iat = payload.get("iat")
    return {
        "username": user.username,
        "email": user.email,
        "logged_in_at": iat,
    }

@router.post('/logout')
async def logout(response: Response):
    response.delete_cookie(key="access_token", httponly=False, secure=False, samesite="Lax")
    response.delete_cookie(key="refresh_token", httponly=False, secure=False, samesite="Lax")

    return