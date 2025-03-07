from fastapi import APIRouter, Cookie, Depends
from fastapi.websockets import WebSocket, WebSocketDisconnect, WebSocketState
from starlette import status

from random import shuffle
import logging
import json
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from database.database import redis_manager, get_async_session
from database.models import Table

from config import configure_logging, ws_manager
from auth.validation import ws_verify_user
from exceptions import ws_not_found_table, ws_max_players, ws_server_exc


router = APIRouter(tags=['Game'])


configure_logging()
logger = logging.getLogger(__name__)


suits = ['♠', '♥', '♦', '♣']
ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']


def create_deck():
    return [f'{rank}{suit}' for suit in suits for rank in ranks]


def deal_cards(players):
    deck = create_deck()
    shuffle(deck)

    player_cards = {}
    for i, player in enumerate(players):
        player_cards[player['username']] = [deck[i], deck[i + 1]]

    return player_cards



async def check_player_cards_periodically(websocket: WebSocket, username: str):
    while True:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                result_player_cards = redis_manager.get_player_cards(username)
                if result_player_cards:
                    logger.info(f'карты найдены для {username}')
                    player_cards = [card.decode() if isinstance(card, bytes) else card for card in result_player_cards]
                    cards_for_players = {}
                    cards_for_players[username] = player_cards
                    await websocket.send_text(json.dumps({'game_started': True, 'cards': cards_for_players}))
                    break
                else:
                    logger.info(f'карты не найдены для {username}')
            else:
                logger.error(f'ws закрыт для {username}')
                break
                
            await asyncio.sleep(5)
        except RuntimeError as e:
            logger.info('RuntimeError')
            logger.error(e)
            break


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
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise ws_not_found_table

        players = redis_manager.get_players(table_id)
        players = [{'username': player.decode() if isinstance(player, bytes) else player} for player in players]

        if len(players) > 10:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise ws_max_players

        logger.warning(players)

        asyncio.create_task(check_player_cards_periodically(websocket, username))

        await ws_manager.broadcast()

        while True:
            result_data = await websocket.receive_text()

            data = json.loads(result_data)

            logger.warning(f'игроки до start_game: {players}')

            if data.get('action') == 'start_game':

                logger.info(f"игра начинается за столом {table_id}")

                result_players = redis_manager.get_players(table_id)
                players_list = [
                    {'username': player.decode() if isinstance(player, bytes) else player} for player in result_players
                ]
                player_cards = deal_cards(players_list)

                cards_for_players = {}
                for player in players_list:
                    cards_for_players[player['username']] = player_cards.get(player['username'], [])
                    redis_manager.add_player_cards(player['username'], player_cards.get(player['username'], []))

                logger.warning(f'игроки после: {players_list}')
                logger.warning(f'карты: {player_cards}')

                await websocket.send_text(json.dumps({'game_started': True, 'cards': cards_for_players}))


    except WebSocketDisconnect as e:
        logger.error(e)

        ws_manager.disconnect(websocket, username)
        await ws_manager.broadcast()

        redis_manager.remove_player_cards(username)
        redis_manager.remove_player(table_id, username)

        logger.info(f"игрок {username} покинул стол {table_id}")

    except RuntimeError as e:
        logger.info('RuntimeError')
        logger.error(e)

    except Exception as e:
        logger.error(e)
        raise ws_server_exc