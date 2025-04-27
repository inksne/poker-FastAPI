from fastapi import APIRouter, Depends

import logging

from auth.validation import get_current_auth_user
from basemodels import CreateTableRequest
from config import configure_logging
from exceptions import bad_blinds, bad_big_blind_uneven, bad_big_blind_small_count, conflict_table, server_exc

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from database.database import get_async_session
from database.managers import redis_manager
from database.models import User, Table


configure_logging()
logger = logging.getLogger(__name__)


router = APIRouter(tags=['API'])


@router.post("/api/v1/authenticated/create_table")
async def post_create_table_page(
    table_data: CreateTableRequest,
    current_user: User = Depends(get_current_auth_user),
    session: AsyncSession = Depends(get_async_session)
) -> dict:
    if table_data.big_blind <= 1 or table_data.start_money <= 9:
        raise bad_blinds
        
    if table_data.big_blind %2 != 0:
        raise bad_big_blind_uneven

    if table_data.start_money // table_data.big_blind < 2:
        raise bad_big_blind_small_count

    try:
        small_blind = table_data.big_blind // 2

        new_table = Table(
            name=table_data.name,
            creator_id=current_user.id,
            big_blind=table_data.big_blind,
            small_blind=small_blind,
            start_money=table_data.start_money
        )

        session.add(new_table)
        await session.commit()

        table_response = CreateTableRequest.from_attributes(new_table)

        return {"table": table_response.model_dump(), "redirect_url": f"/authenticated/game/{new_table.id}"}
    except IntegrityError:
        await session.rollback()
        raise conflict_table
    except Exception as e:
        await session.rollback()
        logger.error(e)
        raise server_exc


@router.get("/api/v1/authenticated/get_players/{table_id}")
async def get_players_count(
    table_id: int,
    current_user: User = Depends(get_current_auth_user),
) -> dict:
    players = redis_manager.get_players(table_id)

    return {"player_count": len(players)}