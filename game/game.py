from fastapi import APIRouter, Cookie, Depends
from fastapi.websockets import WebSocket, WebSocketDisconnect

import json
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from database.database import get_async_session
from database.managers import redis_manager, psql_manager
from config import ws_manager, logger
from auth.validation import ws_verify_user
from exceptions import wrong_amount_for_raise, ws_server_exc

from .card_helpers import check_player_cards_periodically, deal_cards, send_player_combinations
from .stage_and_turn_helpers import send_game_stage_cards_and_game_started, send_current_turn_and_pot, check_player_right_turn
from .blinds_helpers import get_blinds_and_dealer, send_blinds_and_dealer, process_blind_bets
from .call_helper import process_call_bet
from .fold_helper import process_fold
from .raise_helper import process_raise_bet


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

        players = redis_manager.get_players(table_id)

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
                player_cards, community_cards = deal_cards(players_list)
                logger.info(player_cards)

                cards_for_players = {}
                for player in players_list:
                    cards_for_players[player['username']] = player_cards.get(player['username'], [])
                    redis_manager.add_player_cards(player['username'], player_cards.get(player['username'], []))

                redis_manager.add_community_cards(table_id, community_cards)

                logger.warning(f'игроки после: {players_list}')
                logger.warning(f'карты: {player_cards}')

                await websocket.send_text(json.dumps({'cards': cards_for_players}))

                await send_game_stage_cards_and_game_started(community_cards, table_id)

                dealer_index, small_blind_index, big_blind_index = get_blinds_and_dealer(players_list)

                redis_manager.add_indexes(table_id, small_blind_index, big_blind_index, dealer_index)

                await send_blinds_and_dealer(players_list, dealer_index, small_blind_index, big_blind_index)

                await process_blind_bets(websocket, players_list, small_blind_index, big_blind_index, table)

                await send_current_turn_and_pot(players_list, small_blind_index, table_id)

            if data.get('action') == 'call':
                if not await check_player_right_turn(websocket, table_id, username):
                    continue

                logger.info(f'{username} делает call')

                players = redis_manager.get_players(table_id)
                community_cards = redis_manager.get_community_cards(table_id)

                small_blind_index, big_blind_index, dealer_index = redis_manager.get_indexes(table_id)

                await process_call_bet(websocket, username, players, small_blind_index, big_blind_index, community_cards, table)

                await send_current_turn_and_pot(players, small_blind_index, table_id)

                await send_player_combinations(websocket, players, table_id)

            if data.get('action') == 'fold':
                if not await check_player_right_turn(websocket, table_id, username):
                    continue

                logger.info(f'{username} делает fold')

                players = redis_manager.get_players(table_id)
                community_cards = redis_manager.get_community_cards(table_id)

                await process_fold(websocket, username, players, table_id, community_cards)

                await send_player_combinations(websocket, players, table_id)

            if data.get('action') == 'raise':
                if not await check_player_right_turn(websocket, table_id, username):
                    continue

                raise_amount = data.get('amount')
                if not raise_amount or raise_amount <= 0:
                    await websocket.send_text(wrong_amount_for_raise)
                    continue

                logger.info(f'{username} делает raise на сумму {raise_amount}')

                players = redis_manager.get_players(table_id)

                small_blind_index, big_blind_index, dealer_index = redis_manager.get_indexes(table_id)

                await process_raise_bet(websocket, players, small_blind_index, big_blind_index, table, raise_amount)

                await send_current_turn_and_pot(players, small_blind_index, table_id)

                await send_player_combinations(websocket, players, table_id)


    except WebSocketDisconnect as e:
        logger.error(e)

        ws_manager.disconnect(websocket, username)
        await ws_manager.broadcast_players_list()

        redis_manager.remove_player(table_id, username)

        players = redis_manager.get_players(table_id)
        if len(players) == 0:
            logger.info(f'удаление пота, индексов, текущей очереди и стола {table_id}')
            redis_manager.remove_current_turn(table_id)
            redis_manager.remove_indexes(table_id)
            redis_manager.remove_pot(table_id)
            redis_manager.remove_raise_amount(table_id)
            redis_manager.remove_community_cards(table_id)
            redis_manager.remove_current_stage(table_id)

            await psql_manager.delete_table_by_id(table_id, session)

            for player in players:
                redis_manager.remove_player_done_move(table_id, player['username'])
                redis_manager.remove_player_folded(table_id, player['username'])

        redis_manager.remove_player_balance(username)
        redis_manager.remove_player_cards(username)

        logger.info(f"игрок {username} покинул стол {table_id}")


    except RuntimeError as e:
        logger.error(f'RuntimeError {e}')


    # except Exception as e:
    #     logger.error(e)
    #     raise ws_server_exc