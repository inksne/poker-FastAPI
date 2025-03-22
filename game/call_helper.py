from fastapi.websockets import WebSocket

import json

from database.models import Table
from database.managers import redis_manager
from config import ws_manager, logger

from .stage_and_turn_helpers import check_all_players_done, proceed_to_next_stage, send_game_stage_cards_and_game_started, get_next_turn


async def process_call_bet(
    websocket: WebSocket,
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

    player_balance = redis_manager.get_player_balance(username)
    if not player_balance:
        player_balance = table.start_money
        logger.info(f'{table.id} баланс не найден, значение psql: {player_balance}')
    else:
        player_balance = int(player_balance)
        logger.info(f'{table.id} баланс найден: {player_balance}')

    raise_amount = redis_manager.get_raise_amount(table.id)

    if not raise_amount:
        if current_turn == small_blind_index:
            if player_balance < small_blind:
                await websocket.send_text(json.dumps({"error": "Недостаточно средств для малого блайнда."}))
                return
            redis_manager.update_player_balance(username, player_balance, -small_blind)
            redis_manager.update_pot(table.id, small_blind)

        elif current_turn == big_blind_index:
            await websocket.send_text(json.dumps({"info": "Сделан check."}))

        else:
            if player_balance < big_blind:
                await websocket.send_text(json.dumps({"error": "Недостаточно средств для call."}))
                return
            
    else:
        if player_balance < raise_amount:
            await websocket.send_text(json.dumps({"error": f"Недостаточно средств для call на {raise_amount}."}))
            return

        redis_manager.update_player_balance(username, player_balance, -raise_amount)
        redis_manager.update_pot(table.id, raise_amount)

    redis_manager.set_player_done_move(table.id, username, True)

    all_done = await check_all_players_done(players, table.id)

    logger.info(f'all done: {all_done}')

    if all_done:
        await proceed_to_next_stage()
        await send_game_stage_cards_and_game_started(community_cards)
        redis_manager.remove_raise_amount(table.id)
        redis_manager.set_player_done_move(table.id, username, False)

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