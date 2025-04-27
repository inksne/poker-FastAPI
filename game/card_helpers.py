from fastapi.websockets import WebSocket, WebSocketState

from random import shuffle
from collections import Counter
import json
import asyncio
import logging

from poker import Card
from config import ws_manager, configure_logging
from database.managers import redis_manager
from .stage_and_turn_helpers import send_game_stage_global


configure_logging()
logger = logging.getLogger(__name__)


def create_deck() -> list:
    deck = [f"{card.rank}{card.suit}" for card in list(Card)]
    shuffle(deck)
    return deck


def deal_cards(players: list[dict]) -> dict:
    deck = create_deck()
    player_cards = {}
    community_cards = {'flop': [], 'turn': [], 'river': []}
    
    for i, player in enumerate(players):
        player_cards[player['username']] = [deck.pop(), deck.pop()]

    community_cards['flop'] = [deck.pop(), deck.pop(), deck.pop()]
    community_cards['turn'] = [deck.pop()]
    community_cards['river'] = [deck.pop()]

    return player_cards, community_cards


def rank_value(rank: str) -> int:
    if rank == 'T':
        return 10
    if rank in ['J', 'Q', 'K', 'A']:
        return {'J': 11, 'Q': 12, 'K': 13, 'A': 14}[rank]
    return int(rank)


def evaluate_hand(player_cards: list, community_cards: list) -> str:
    all_cards = player_cards + community_cards
    all_cards = [(card[:-1], card[-1]) for card in all_cards]

    all_cards.sort(key=lambda x: rank_value(x[0]), reverse=True)

    is_flush = len(set(card[1] for card in all_cards)) == 1
    ranks_sorted = sorted([rank_value(card[0]) for card in all_cards], reverse=True)
    rank_counts = Counter(ranks_sorted)
    is_straight = len(rank_counts) == 5 and ranks_sorted[0] - ranks_sorted[4] == 4

    if is_flush and is_straight and set(ranks_sorted) == {14, 13, 12, 11, 10}:
        return 'Флеш Рояль'
    elif is_flush and is_straight:
        return 'Стрит Флеш'
    elif 4 in rank_counts.values():
        return 'Каре'
    elif sorted(rank_counts.values(), reverse=True) == [3, 2]:
        return 'Фулл Хаус'
    elif is_flush:
        return 'Флеш'
    elif is_straight:
        return 'Стрит'
    elif 3 in rank_counts.values():
        return 'Сет'
    elif sorted(rank_counts.values(), reverse=True) == [2, 2, 1]:
        return 'Две Пары'
    elif 2 in rank_counts.values():
        return 'Пара'
    else:
        return 'Старшая Карта'
    

async def check_player_combinations(players: list, community_cards: dict) -> dict:
    combinations = {}
    for player in players:
        player_cards = redis_manager.get_player_cards(player['username'])
        if player_cards:
            combination = evaluate_hand(player_cards, community_cards['flop'] + community_cards['turn'] + community_cards['river'])
            combinations[player['username']] = combination
    return combinations


def compare_hands(player_hand: list, opponent_hand: list) -> int:
    """
    cравнивает два набора карт игрока
    1, если первая рука сильнее
    -1, если вторая рука сильнее
    0, если руки равны
    """
    player_hand_sorted = sorted(player_hand, key=lambda x: rank_value(x[0]), reverse=True)
    opponent_hand_sorted = sorted(opponent_hand, key=lambda x: rank_value(x[0]), reverse=True)

    for player_card, opponent_card in zip(player_hand_sorted, opponent_hand_sorted):
        player_card_value = rank_value(player_card[0])
        opponent_card_value = rank_value(opponent_card[0])
        
        if player_card_value > opponent_card_value:
            return 1
        elif player_card_value < opponent_card_value:
            return -1

    return 0


def determine_winner(combinations: dict, player_cards: dict, community_cards: dict, table_id: int) -> str:
    best_combination = None
    best_player = None
    best_hand_value = -1
    best_hand = None
    candidates = []

    for player, combination in combinations.items():
        if redis_manager.get_player_folded(table_id, player):
            continue

        player_hand = player_cards[player]
        player_hand_value = evaluate_hand(player_hand, community_cards['flop'] + community_cards['turn'] + community_cards['river'])

        if best_combination is None or player_hand_value > best_hand_value:
            best_combination = combination
            best_player = player
            best_hand_value = player_hand_value
            best_hand = player_hand
            candidates = [player]
        elif player_hand_value == best_hand_value:
            candidates.append(player)
    
    if len(candidates) == 1:
        return best_player

    best_player = candidates[0]
    best_hand = player_cards[best_player]
    
    for player in candidates[1:]:
        result = compare_hands(player_cards[player], best_hand)
        if result == 1:
            best_player = player
            best_hand = player_cards[player]
    
    return best_player


async def send_player_combinations(websocket: WebSocket, players: list, table_id: int) -> None:
    community_cards = redis_manager.get_community_cards(table_id)
    combinations = await check_player_combinations(players, community_cards)

    for player in players:
        player_username = player['username']
        player_combination = combinations.get(player_username, 'high_card')
        await websocket.send_text(json.dumps({'player_combination': player_combination}))


async def check_player_cards_periodically(websocket: WebSocket, username: str) -> None:
    while True:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                player_cards = redis_manager.get_player_cards(username)
                if player_cards:
                    logger.debug(f'карты найдены для {username}')
                    cards_for_players = {}
                    cards_for_players[username] = player_cards
                    await websocket.send_text(json.dumps({'game_started': True, 'cards': cards_for_players}))
                    await send_game_stage_global()
                    break
                else:
                    logger.debug(f'карты не найдены для {username}')
            else:
                logger.error(f'ws закрыт для {username}')
                break
                
            await asyncio.sleep(5)
        except RuntimeError as e:
            logger.error(f'RuntimeError {e}')
            break


async def check_winner_and_end_game(websocket: WebSocket, username: str, players: list, table_id: int) -> None:
    community_cards = redis_manager.get_community_cards(table_id)
    player_cards = {player['username']: redis_manager.get_player_cards(player['username']) for player in players}

    combinations = await check_player_combinations(players, community_cards)

    winner = determine_winner(combinations, player_cards, community_cards, table_id)

    await ws_manager.broadcast({"pot": 0})

    await ws_manager.broadcast({'game_over': True, 'winner': winner, 'combination': combinations[winner]})

    redis_manager.update_player_balance(winner, redis_manager.get_player_balance(winner), redis_manager.get_pot(table_id))

    redis_manager.remove_community_cards(table_id)
    redis_manager.remove_current_stage(table_id)
    redis_manager.remove_indexes(table_id)
    redis_manager.remove_current_turn(table_id)
    redis_manager.remove_raise_amount(table_id)
    redis_manager.remove_pot(table_id)

    for player in players:
        redis_manager.remove_player_cards(player['username'])
        redis_manager.remove_player_folded(table_id, player['username'])
        redis_manager.remove_player_done_move(table_id, player['username'])

    logger.debug(f'победитель {winner} с комбинацией {combinations[winner]}')

    asyncio.create_task(check_player_cards_periodically(websocket, username))