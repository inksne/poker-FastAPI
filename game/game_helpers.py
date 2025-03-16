from fastapi.websockets import WebSocket, WebSocketState

from random import shuffle
from poker import Card
import asyncio
import json

from config import logger, ws_manager
from database.managers import redis_manager
from database.models import Table


game_stages = ('Preflop', 'Flop', 'Turn', 'River')
current_stage = 0


def create_deck() -> list:
    deck = deck = [f"{card.rank}{card.suit}" for card in list(Card)]
    shuffle(deck)
    return deck


def deal_cards(players: list[dict]) -> dict:
    deck = create_deck()
    player_cards = {}
    for i, player in enumerate(players):
        player_cards[player['username']] = [deck.pop(), deck.pop()]

    return player_cards


async def send_game_stage(websocket: WebSocket) -> None:
    global current_stage
    stage = game_stages[current_stage]
    await websocket.send_text(json.dumps({'game_stage': stage}))


async def proceed_to_next_stage() -> None:
    global current_stage
    if current_stage < len(game_stages) - 1:
        current_stage += 1
    else:
        current_stage = 0


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
            player_balance = int(player_balance)
            logger.info(f'{table.id} баланс найден: {player_balance}')

        if player_balance < small_blind and index == small_blind_index:
            await websocket.send_text(json.dumps({"error": "Недостаточно средств для малого блайнда."}))
            return
        if player_balance < big_blind and index == big_blind_index:
            await websocket.send_text(json.dumps({"error": "Недостаточно средств для большого блайнда."}))
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


async def send_current_turn_and_pot(
    players: list[dict],
    small_blind_index: int,
    table_id: int
):

    current_turn = redis_manager.get_current_turn(table_id)
    logger.info(f'current_turn из редиса: {current_turn}')
    if current_turn is None:
        current_turn = small_blind_index
    logger.info(f'установка current_turn в редис: {current_turn}')
    redis_manager.add_current_turn(table_id, current_turn)

    pot = redis_manager.get_pot(table_id)
    logger.info(f'pot из редиса: {pot}')

    await ws_manager.broadcast({
        "current_turn": players[current_turn]['username'],
        "pot": pot
    })


async def check_player_cards_periodically(websocket: WebSocket, username: str) -> None:
    while True:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                player_cards = redis_manager.get_player_cards(username)
                if player_cards:
                    logger.info(f'карты найдены для {username}')
                    cards_for_players = {}
                    cards_for_players[username] = player_cards
                    await websocket.send_text(json.dumps({'game_started': True, 'cards': cards_for_players}))
                    await send_game_stage(websocket)
                    break
                else:
                    logger.info(f'карты не найдены для {username}')
            else:
                logger.error(f'ws закрыт для {username}')
                break
                
            await asyncio.sleep(5)
        except RuntimeError as e:
            logger.error(f'RuntimeError {e}')
            break


async def process_call_bet(
    websocket: WebSocket,
    players: list[dict],
    small_blind_index: int,
    big_blind_index: int,
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

    if current_turn == small_blind_index:
        if player_balance < small_blind:
            await websocket.send_text(json.dumps({"error": "Недостаточно средств для малого блайнда."}))
            return
        redis_manager.update_player_balance(username, player_balance, -small_blind)
        redis_manager.update_pot(table.id, small_blind)

    elif current_turn == big_blind_index:
        await websocket.send_text(json.dumps({"info": "Сделан check."}))
        # if player_balance < big_blind:
        #     await websocket.send_text(json.dumps({"error": "Недостаточно средств для большого блайнда."}))
        #     return
        # redis_manager.update_player_balance(username, player_balance, -big_blind)
        # redis_manager.update_pot(table.id, big_blind)

    else:
        if player_balance < big_blind:
            await websocket.send_text(json.dumps({"error": "Недостаточно средств для call."}))
            return
        # redis_manager.update_player_balance(username, player_balance, -big_blind)
        # redis_manager.update_pot(table.id, big_blind)

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
    next_turn = (current_turn + 1) % len(players)
    logger.info(f'после обновления current_turn: {next_turn}')
    redis_manager.add_current_turn(table.id, next_turn)