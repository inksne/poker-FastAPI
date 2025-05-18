from fastapi.websockets import WebSocket

import logging

from database.models import Table
from database.managers import redis_manager
from config import ws_manager, configure_logging


configure_logging()
logger = logging.getLogger(__name__)


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


def check_player_balance_in_db(username: str, table: Table) -> int:
    player_balance = redis_manager.get_player_balance(username)
    logger.debug(f'player_balance rdb: {player_balance}')
    if not player_balance and player_balance != 0:
        player_balance = table.start_money
        logger.debug(f'{table.id} баланс не найден для {username}, значение psql: {player_balance}')
    else:
        logger.debug(f'{table.id} баланс найден для {username}: {player_balance}')

    return player_balance


async def process_blind_bets(
    players: list[dict],
    small_blind_index: int,
    big_blind_index: int,
    table: Table
) -> None:
    small_blind = table.small_blind
    big_blind = table.big_blind

    for index, player in enumerate(players):
        username = player['username']

        player_balance = check_player_balance_in_db(username, table)

        if index == small_blind_index:
            if player_balance < small_blind:
                redis_manager.set_player_balance(username, 0)
                redis_manager.update_pot(table.id, player_balance)
            else:
                redis_manager.update_player_balance(username, player_balance, -small_blind)
                redis_manager.update_pot(table.id, small_blind)
        elif index == big_blind_index:
            if player_balance < big_blind:
                redis_manager.set_player_balance(username, 0)
                redis_manager.update_pot(table.id, player_balance)
            else:
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