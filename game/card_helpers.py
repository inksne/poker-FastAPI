from fastapi.websockets import WebSocket, WebSocketState

from random import shuffle
import json
import asyncio

from poker import Card
from config import logger
from database.managers import redis_manager
from .stage_and_turn_helpers import send_game_stage


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