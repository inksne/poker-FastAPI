from fastapi import APIRouter, Cookie, Depends
from fastapi.websockets import WebSocket, WebSocketDisconnect
from starlette import status

import logging
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from database.database import redis_manager, get_async_session
from database.models import Table

from config import configure_logging, ws_manager
from auth.validation import ws_verify_user


router = APIRouter(tags=['Game'])


configure_logging()
logger = logging.getLogger(__name__)


@router.websocket('/authenticated/game/{table_id}')
async def ws_game_page(
    websocket: WebSocket,
    table_id: int,
    access_token: str = Cookie(None),
    session: AsyncSession = Depends(get_async_session)
):
    try:
        username = await ws_verify_user(access_token)

        await ws_manager.connect(websocket, username)

        result_table = await session.execute(
            select(Table)
            .options(selectinload(Table.creator))
            .where(Table.id == table_id)
        )
        table = result_table.scalars().first()

        if not table:
            await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
            logger.error('стол не найден')
            return

        players = redis_manager.get_players(table_id)

        players = [{'username': player.decode() if isinstance(player, bytes) else player} for player in players]

        logger.warning(players)

        await websocket.send_text(json.dumps({
            'players': players
        }))

        while True:
            data = await websocket.receive_text()
            logger.info(f"получено сообщение от {username}: {data}")

    except WebSocketDisconnect as e:
        logger.error(e)

        ws_manager.disconnect(websocket, username)
        await ws_manager.broadcast()

        redis_manager.remove_player(table_id, username)

        logger.info(f"игрок {username} покинул стол {table_id}")

    except RuntimeError as e:
        logger.info('RuntimeError')
        logger.error(e)