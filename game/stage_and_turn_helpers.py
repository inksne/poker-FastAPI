from fastapi.websockets import WebSocket

import logging

from config import ws_manager, configure_logging, GAME_STAGES
from database.managers import redis_manager
from exceptions import player_folded_or_not_enough_money, other_turn


configure_logging()
logger = logging.getLogger(__name__)


current_stage = 0


async def send_game_stage_cards_and_game_started(community_cards: dict, table_id: int) -> None:
    global current_stage
    old_current_stage = redis_manager.get_current_stage(table_id)
    if old_current_stage == 0:
        current_stage = old_current_stage
    stage = GAME_STAGES[current_stage]
    redis_manager.add_current_stage(table_id, stage)
    await ws_manager.broadcast({'game_started': True, 'game_stage': stage, 'community_cards': community_cards})


async def send_game_stage_global() -> None:
    global current_stage
    stage = GAME_STAGES[current_stage]
    await ws_manager.broadcast({'game_stage': stage})


def proceed_to_next_stage() -> None:
    global current_stage
    if current_stage < len(GAME_STAGES) - 1:
        current_stage += 1
    else:
        current_stage = 0


def get_next_turn(players: list[dict], table_id: int, current_turn: int) -> int:
    next_turn = (current_turn + 1) % len(players)
    while redis_manager.get_player_folded(table_id, players[next_turn]['username']):
        next_turn = (next_turn + 1) % len(players)
    return next_turn


def check_all_players_done(players: list[dict], table_id: int) -> bool:
    all_done = True
    for player in players:
        if redis_manager.get_player_folded(table_id, player['username']):
            logger.debug(f'{player['username']} сделал fold ')
            continue  
        player_done = redis_manager.get_player_done_move(table_id, player['username'])
        logger.debug(f'{player['username']}: {player_done}')
        if not player_done:
            all_done = False
            break
    return all_done


async def check_player_right_turn(websocket: WebSocket, table_id: int, username: str) -> bool:
    if redis_manager.get_player_folded(table_id, username) or redis_manager.get_player_balance(username) == 0:
        await websocket.send_text(player_folded_or_not_enough_money)
        return False

    players = redis_manager.get_players(table_id)
    current_turn = redis_manager.get_current_turn(table_id)

    if current_turn is not None and current_turn >= len(players):
        current_turn = 0
        redis_manager.add_current_turn(table_id, current_turn)

    current_player = players[current_turn]
    if current_player['username'] != username:
        await websocket.send_text(other_turn)
        return False
    
    return True


async def send_current_turn_and_pot(
    players: list[dict],
    small_blind_index: int,
    table_id: int
):

    current_turn = redis_manager.get_current_turn(table_id)
    logger.debug(f'current_turn из редиса: {current_turn}')
    if current_turn is None:
        current_turn = small_blind_index
    logger.debug(f'установка current_turn в редис: {current_turn}')
    redis_manager.add_current_turn(table_id, current_turn)

    pot = redis_manager.get_pot(table_id)
    logger.debug(f'pot из редиса: {pot}')

    await ws_manager.broadcast({
        "current_turn": players[current_turn]['username'],
        "pot": pot
    })


def check_single_player_left(players: list[dict], table_id: int) -> str | None:
    active_players = [
        player for player in players
        if not redis_manager.get_player_folded(table_id, player['username'])
    ]

    if len(active_players) == 1:
        return active_players[0]['username']
    
    return None