from fastapi.websockets import WebSocket

import logging

from database.models import Table
from database.managers import redis_manager
from config import ws_manager, configure_logging
from .stage_and_turn_helpers import (
    check_all_players_done,
    proceed_to_next_stage,
    send_game_stage_cards_and_game_started,
    get_next_turn
)
from .card_helpers import check_winner_and_end_game
from .blinds_helpers import check_player_balance_in_db
from exceptions import not_enough_funds_for_small_blind, not_enough_funds_for_call, check_done


configure_logging()
logger = logging.getLogger(__name__)


async def process_call_bet(
    websocket: WebSocket,
    username: str,
    players: list[dict],
    small_blind_index: int,
    big_blind_index: int,
    community_cards: dict,
    table: Table
) -> None:
    small_blind = table.small_blind
    big_blind = table.big_blind

    current_turn = redis_manager.get_current_turn(table.id)
    current_player = players[current_turn]
    username = current_player['username']

    player_balance = check_player_balance_in_db(username, table)

    raise_amount = redis_manager.get_raise_amount(table.id)
    current_stage = redis_manager.get_current_stage(table.id)

    logger.debug(f'current_stage: {current_stage}')

    if small_blind_index >= len(players):
        small_blind_index = 0
    if big_blind_index >= len(players):
        big_blind_index = 1 if len(players) > 1 else 0

    if not raise_amount:
        if current_turn == small_blind_index:
            if current_stage == 'Preflop':
                if player_balance < small_blind:
                    await websocket.send_text(not_enough_funds_for_small_blind)
                    return
                redis_manager.update_player_balance(username, player_balance, -small_blind)
                redis_manager.update_pot(table.id, small_blind)
            else:
                await websocket.send_text(check_done)

        elif current_turn == big_blind_index:
            await websocket.send_text(check_done)

        else:
            if player_balance < big_blind:
                await websocket.send_text(not_enough_funds_for_call)
                return
            
    else:
        if player_balance < raise_amount:
            await websocket.send_text(not_enough_funds_for_call)
            return

        redis_manager.update_player_balance(username, player_balance, -raise_amount)
        redis_manager.update_pot(table.id, raise_amount)

    redis_manager.set_player_done_move(table.id, username, True)

    all_done = await check_all_players_done(players, table.id)

    logger.debug(f'all done: {all_done}')

    if all_done:
        await proceed_to_next_stage()
        await send_game_stage_cards_and_game_started(community_cards, table.id)
        redis_manager.remove_raise_amount(table.id)
        redis_manager.set_player_done_move(table.id, username, False)

        if current_stage == 'River':
            players = redis_manager.get_players(table.id)
            await check_winner_and_end_game(websocket, username, players, table.id)

    balance_data = {}
    for player in players:
        player_balance_data = redis_manager.get_player_balance(player['username'])
        balance_data[player['username']] = player_balance_data

    await ws_manager.broadcast({"balance": balance_data})

    blinds_info = {
        'small_blind': players[small_blind_index]['username'],
        'big_blind': players[big_blind_index]['username'],
        'small_blind_amount': small_blind,
        'big_blind_amount': big_blind
    }
    await ws_manager.broadcast(blinds_info)

    logger.debug(f'до обновления current turn: {current_turn}')
    next_turn = get_next_turn(players, table.id, current_turn)
    logger.debug(f'после обновления current_turn: {next_turn}')
    redis_manager.add_current_turn(table.id, next_turn)