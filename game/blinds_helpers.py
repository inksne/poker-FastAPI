from fastapi.websockets import WebSocket

from database.models import Table
from database.managers import redis_manager
from config import ws_manager, logger
from exceptions import not_enough_funds_for_big_blind, not_enough_funds_for_small_blind


def get_blinds_and_dealer(players: list[dict]) -> int:
    dealer_index = 0

    small_blind_index = (dealer_index + 1) % len(players)
    big_blind_index = (dealer_index + 2) % len(players)

    return dealer_index, small_blind_index, big_blind_index


async def send_blinds_and_dealer(
    players: list[dict],
    dealer_index: int,
    small_blind_index: int,
    big_blind_index: int
) -> None:
    blinds_and_dealer = {
        'dealer': players[dealer_index]['username'],
        'small_blind': players[small_blind_index]['username'],
        'big_blind': players[big_blind_index]['username']
    }
    await ws_manager.broadcast({'blinds_and_dealer': blinds_and_dealer})


async def process_blind_bets(
    websocket: WebSocket,
    players: list[dict],
    small_blind_index: int,
    big_blind_index: int,
    table: Table
) -> None:
    small_blind = table.small_blind
    big_blind = table.big_blind

    for index, player in enumerate(players):
        username = player['username']
        player_balance = redis_manager.get_player_balance(username)

        if not player_balance:
            player_balance = table.start_money
            logger.info(f'{table.id} баланс не найден, значение psql: {player_balance}')
        else:
            logger.info(f'{table.id} баланс найден: {player_balance}')

        if player_balance < small_blind and index == small_blind_index:
            await websocket.send_text(not_enough_funds_for_small_blind)
            return
        if player_balance < big_blind and index == big_blind_index:
            await websocket.send_text(not_enough_funds_for_big_blind)
            return

        if index == small_blind_index:
            redis_manager.update_player_balance(username, player_balance, -small_blind)
            redis_manager.update_pot(table.id, small_blind)
        elif index == big_blind_index:
            redis_manager.update_player_balance(username, player_balance, -big_blind)
            redis_manager.update_pot(table.id, big_blind)

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