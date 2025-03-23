from fastapi.websockets import WebSocket

import json

from database.models import Table
from database.managers import redis_manager
from config import ws_manager, logger

from .stage_and_turn_helpers import check_all_players_done, get_next_turn


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
    current_player = players[current_turn]
    username = current_player['username']

    player_balance = redis_manager.get_player_balance(username)
    old_raise_amount = redis_manager.get_raise_amount(table.id)

    if not player_balance:
        player_balance = table.start_money
        logger.info(f'{table.id} баланс не найден, значение psql: {player_balance}')
    else:
        player_balance = int(player_balance)
        logger.info(f'{table.id} баланс найден: {player_balance}')

    if raise_amount < big_blind // 2:
        await websocket.send_text(json.dumps({"error": "Raise должен быть не меньше, чем двойной размер большого блайнда."}))
        return

    if old_raise_amount:
        if raise_amount <= old_raise_amount:
            await websocket.send_text(json.dumps({"error": "Ваш raise должен быть выше, чем raise другого игрока."}))
            return

    if player_balance < raise_amount:
        await websocket.send_text(json.dumps({"error": "Недостаточно средств для raise."}))
        return

    redis_manager.update_player_balance(username, player_balance, -raise_amount)
    redis_manager.update_pot(table.id, raise_amount)

    logger.info(f'raise_amount: {raise_amount}')

    redis_manager.add_raise_amount(table.id, raise_amount)

    redis_manager.set_player_done_move(table.id, username, True)

    all_done = await check_all_players_done(players, table.id)

    logger.info(f'all done: {all_done}')

    if all_done:
        next_turn = get_next_turn(players, table.id, current_turn)
        logger.info(f'следующий ход за {players[next_turn]["username"]}')
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

    logger.info(f'до обновления current turn: {current_turn}')
    next_turn = get_next_turn(players, table.id, current_turn)
    logger.info(f'после обновления current_turn: {next_turn}')
    redis_manager.add_current_turn(table.id, next_turn)