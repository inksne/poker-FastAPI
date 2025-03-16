from fastapi import APIRouter, Cookie, Depends
from fastapi.websockets import WebSocket, WebSocketDisconnect
from starlette import status

import json
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from database.database import get_async_session
from database.managers import redis_manager, psql_manager
from .game_helpers import (
    send_game_stage,
    send_blinds_and_dealer,
    process_blind_bets,
    check_player_cards_periodically,
    get_blinds_and_dealer,
    deal_cards,
    process_call_bet,
    send_current_turn_and_pot
)
from config import ws_manager, logger
from auth.validation import ws_verify_user
from exceptions import ws_not_found_table, ws_max_players, ws_server_exc


router = APIRouter(tags=['Game'])


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

        table = await psql_manager.get_table_by_id(table_id, session)

        if not table:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise ws_not_found_table

        players = redis_manager.get_players(table_id)

        if len(players) > 10:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise ws_max_players

        logger.warning(players)

        asyncio.create_task(check_player_cards_periodically(websocket, username))

        await ws_manager.broadcast_players_list()

        while True:
            result_data = await websocket.receive_text()

            data = json.loads(result_data)

            logger.warning(f'игроки до start_game: {players}')

            if data.get('action') == 'start_game':

                logger.info(f"игра начинается за столом {table_id}")

                players_list = redis_manager.get_players(table_id)
                player_cards = deal_cards(players_list)
                logger.info(player_cards)

                cards_for_players = {}
                for player in players_list:
                    cards_for_players[player['username']] = player_cards.get(player['username'], [])
                    redis_manager.add_player_cards(player['username'], player_cards.get(player['username'], []))

                logger.warning(f'игроки после: {players_list}')
                logger.warning(f'карты: {player_cards}')

                await websocket.send_text(json.dumps({'game_started': True, 'cards': cards_for_players}))

                await send_game_stage(websocket)

                dealer_index, small_blind_index, big_blind_index = get_blinds_and_dealer(players_list)

                redis_manager.add_sb_index(table_id, small_blind_index)
                redis_manager.add_bb_index(table_id, big_blind_index)
                redis_manager.add_d_index(table_id, dealer_index)

                await send_blinds_and_dealer(players_list, dealer_index, small_blind_index, big_blind_index)

                await process_blind_bets(websocket, players_list, small_blind_index, big_blind_index, table)

                await send_current_turn_and_pot(players_list, small_blind_index, table_id)

            if data.get('action') == 'call':
                logger.info(f'Игрок {username} делает call.')

                players = redis_manager.get_players(table_id)

                dealer_index = redis_manager.get_d_index(table_id)
                small_blind_index = redis_manager.get_sb_index(table_id)
                big_blind_index = redis_manager.get_bb_index(table_id)

                current_turn = redis_manager.get_current_turn(table_id)

                current_player = players[current_turn]
                if current_player['username'] != username:
                    await websocket.send_text(json.dumps({"error": "Не ваш ход!"}))
                    continue

                await process_call_bet(websocket, players, small_blind_index, big_blind_index, table)

                await send_current_turn_and_pot(players, small_blind_index, table_id)

                await ws_manager.broadcast({
                    "current_turn": players[current_turn]['username']
                })

            if data.get('action') == 'fold':
                pass

            if data.get('action') == 'raise':
                pass


    except WebSocketDisconnect as e:
        logger.error(e)

        ws_manager.disconnect(websocket, username)
        await ws_manager.broadcast_players_list()

        players = redis_manager.get_players(table_id)
        if len(players) == 0:
            logger.info(f'удаление пота, индексов и текущей очереди для {table_id}')
            redis_manager.remove_current_turn(table_id)
            redis_manager.remove_indexes(table_id)
            redis_manager.remove_pot(table_id)

        redis_manager.remove_player_balance(username)
        redis_manager.remove_player_cards(username)
        redis_manager.remove_player(table_id, username)

        logger.info(f"игрок {username} покинул стол {table_id}")

    except RuntimeError as e:
        logger.error(f'RuntimeError {e}')

    # except Exception as e:
    #     logger.error(e)
    #     raise ws_server_exc