from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from database.database import get_async_session, redis_manager
from database.models import User, Table

from auth.validation import get_current_auth_user
from exceptions import not_found_table
from config import configure_logging


router = APIRouter(tags=['Templates'])


templates = Jinja2Templates(directory='templates')


configure_logging()
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def get_base_page(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.get('/about_us', response_class=HTMLResponse)
async def get_base_page(request: Request):
    return templates.TemplateResponse(request, 'about_us.html')


@router.get('/jwt/register', response_class=HTMLResponse)
async def get_register_page(request: Request):
    return templates.TemplateResponse(request, 'register.html')


@router.get('/jwt/login/', response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse(request, 'login.html')


@router.get("/authenticated/", response_class=HTMLResponse)
async def get_auth_page(request: Request, current_user: User = Depends(get_current_auth_user)):
    return templates.TemplateResponse(request, "auth_index.html")


@router.get("/authenticated/create_table", response_class=HTMLResponse)
async def get_create_table_page(request: Request, current_user: User = Depends(get_current_auth_user)):
    return templates.TemplateResponse(request, 'create_table.html')


@router.get("/authenticated/search", response_class=HTMLResponse)
async def get_search_table_page(
    request: Request,
    current_user: User = Depends(get_current_auth_user),
    session: AsyncSession = Depends(get_async_session)
):
    result_tables = await session.execute(select(Table))
    tables = result_tables.scalars().all()
    
    return templates.TemplateResponse(request, 'search_table.html', {'tables': tables})


@router.post("/authenticated/search")
async def post_search_table_page(
    request: Request,
    query: str = Form(...),
    current_user: User = Depends(get_current_auth_user),
    session: AsyncSession = Depends(get_async_session)
):
    result_tables = await session.execute(select(Table).where(Table.name.ilike(f"%{query}%")))
    tables = result_tables.scalars().all()
    
    return templates.TemplateResponse(request, 'search_table.html', {'tables': tables})


@router.get('/authenticated/game/{table_id}')
async def game_page(
    request: Request,
    table_id: int,
    current_user: User = Depends(get_current_auth_user),
    session: AsyncSession = Depends(get_async_session)
):
    result_table = await session.execute(
        select(Table)
        .options(selectinload(Table.creator))
        .where(Table.id == table_id)
    )
    table = result_table.scalars().first()

    if not table:
        raise not_found_table

    redis_manager.add_player(table_id, current_user.username)

    players = redis_manager.get_players(table_id)

    players = [{'username': player.decode() if isinstance(player, bytes) else player} for player in players]

    logger.warning(players)
    
    return templates.TemplateResponse(
        request,
        'game.html',
        {
            'table': table,
            'players': players,
            'current_user': current_user
        }
    )