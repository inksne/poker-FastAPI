from database.managers import redis_manager
from config import ws_manager, logger

from .stage_and_turn_helpers import check_all_players_done, proceed_to_next_stage, send_game_stage_cards_and_game_started, get_next_turn


async def process_fold(players: list[dict], table_id: int, community_cards: dict) -> None:
    current_turn = redis_manager.get_current_turn(table_id)
    current_player = players[current_turn]
    username = current_player['username']

    redis_manager.set_player_done_move(table_id, username, True)
    redis_manager.set_player_folded(table_id, username, True)
    
    all_done = await check_all_players_done(players, table_id)

    if all_done:
        await proceed_to_next_stage()
        await send_game_stage_cards_and_game_started(community_cards, table_id)

    next_turn = get_next_turn(players, table_id, current_turn)
    redis_manager.add_current_turn(table_id, next_turn)
    await ws_manager.broadcast({
        "current_turn": players[next_turn]['username']
    })
    logger.info(f'{username} сделал fold')