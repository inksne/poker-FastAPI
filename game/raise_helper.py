from fastapi.websockets import WebSocket

import logging

from database.models import Table
from database.managers import redis_manager
from config import ws_manager, configure_logging
from .stage_and_turn_helpers import check_all_players_done, get_next_turn
from .blinds_helpers import check_player_balance_in_db
from exceptions import twice_raise, raise_less_than_old, not_enough_funds_for_raise


configure_logging()
logger = logging.getLogger(__name__)


async def process_raise_bet(
    websocket: WebSocket,
    players: list[dict],
    small_blind_index: int,
    big_blind_index: int,
    table: Table,
    raise_amount: int
) -> None:
    small_blind = table.small_blind
    big_blind = table.big_blind

    current_turn = redis_manager.get_current_turn(table.id)

    if current_turn is not None and current_turn >= len(players):
        current_turn = 0
        redis_manager.add_current_turn(table.id, current_turn)
    
    current_player = players[current_turn]
    username = current_player['username']

    old_raise_amount = redis_manager.get_raise_amount(table.id)
    player_balance = check_player_balance_in_db(username, table)

    if raise_amount < big_blind // 2:
        await websocket.send_text(twice_raise)
        return

    if old_raise_amount:
        if raise_amount <= old_raise_amount:
            await websocket.send_text(raise_less_than_old)
            return

    if player_balance < raise_amount:
        await websocket.send_text(not_enough_funds_for_raise)
        return

    redis_manager.update_player_balance(username, player_balance, -raise_amount)
    redis_manager.update_pot(table.id, raise_amount)

    logger.debug(f'raise_amount: {raise_amount}')

    redis_manager.add_raise_amount(table.id, raise_amount)

    redis_manager.set_player_done_move(table.id, username, True)

    all_done = check_all_players_done(players, table.id)

    logger.debug(f'all done: {all_done}')

    if small_blind_index >= len(players):
        small_blind_index = 0
    if big_blind_index >= len(players):
        big_blind_index = 1 if len(players) > 1 else 0

    if all_done:
        next_turn = get_next_turn(players, table.id, current_turn)
        logger.debug(f'следующий ход за {players[next_turn]["username"]}')
        redis_manager.add_current_turn(table.id, next_turn)

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