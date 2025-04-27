from fastapi.websockets import WebSocket

import logging

from database.managers import redis_manager
from config import ws_manager, configure_logging

from .stage_and_turn_helpers import (
    check_all_players_done,
    proceed_to_next_stage,
    send_game_stage_cards_and_game_started,
    get_next_turn,
    check_single_player_left
)
from .card_helpers import check_winner_and_end_game


configure_logging()
logger = logging.getLogger(__name__)


async def process_fold(
    websocket: WebSocket,
    username: str,
    players: list[dict],
    table_id: int,
    community_cards: dict
) -> None:
    current_turn = redis_manager.get_current_turn(table_id)
    current_player = players[current_turn]
    username = current_player['username']

    logger.debug(f'{username} сделал fold')

    redis_manager.set_player_done_move(table_id, username, True)
    redis_manager.set_player_folded(table_id, username, True)
    current_stage = redis_manager.get_current_stage(table_id)

    winner = await check_single_player_left(players, table_id)
    if winner:
        logger.debug(f'победитель: {winner}')
        await check_winner_and_end_game(websocket, winner, players, table_id)
        return
    
    all_done = await check_all_players_done(players, table_id)

    if all_done:
        await proceed_to_next_stage()
        await send_game_stage_cards_and_game_started(community_cards, table_id)

        if current_stage == 'River':
            players = redis_manager.get_players(table_id)
            await check_winner_and_end_game(websocket, username, players, table_id)

    next_turn = get_next_turn(players, table_id, current_turn)
    redis_manager.add_current_turn(table_id, next_turn)
    await ws_manager.broadcast({
        "current_turn": players[next_turn]['username']
    })