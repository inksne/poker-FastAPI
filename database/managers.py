from fastapi import Depends

from redis import Redis

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.future import select

from .database import get_async_session
from .models import Table


class RedisManager:
    def __init__(self):
        self.r = Redis(host='localhost')


    def add_player(self, table_id: int, username: str) -> None:
        self.r.sadd(table_id, username)

    def get_players(self, table_id: int) -> list[dict]:
        players = self.r.smembers(table_id)
        return [{'username': player.decode() if isinstance(player, bytes) else player} for player in players]

    def remove_player(self, table_id: int, username: str) -> None:
        self.r.srem(table_id, username)


    def add_player_cards(self, username: str, cards: list) -> None:
        for card in cards:
            self.r.sadd(username, card)

    def get_player_cards(self, username: str) -> list[str]:
        cards = self.r.smembers(username)
        return [card.decode() if isinstance(card, bytes) else card for card in cards]
    
    def remove_player_cards(self, username: str) -> None:
        self.r.delete(username)


    def get_player_balance(self, username: str) -> str:
        balance = self.r.get(f'{username}:balance')
        return balance.decode() if isinstance(balance, bytes) else balance

    def set_player_balance(self, username: str, balance: int) -> None:
        self.r.set(f'{username}:balance', balance)
    
    def update_player_balance(self, username: str, balance: int, delta: int) -> None:
        new_balance = balance + delta
        self.set_player_balance(username, new_balance)

    def remove_player_balance(self, username: str) -> None:
        self.r.delete(f'{username}:balance')


    def set_pot(self, table_id: int, pot: int) -> None:
        self.r.set(f'{table_id}:pot', pot)

    def get_pot(self, table_id: int) -> int:
        pot =  self.r.get(f'{table_id}:pot')
        return int(pot.decode() if isinstance(pot, bytes) else pot) if pot else 0
    
    def update_pot(self, table_id: int, delta: int) -> None:
        pot = self.get_pot(table_id)

        if not pot:
            pot = 0

        new_pot = pot + delta
        self.set_pot(table_id, new_pot)
    
    def remove_pot(self, table_id: int) -> None:
        self.r.delete(f'{table_id}:pot')


    def add_sb_index(self, table_id: int, sb_index: int) -> None:
        self.r.set(f'{table_id}:sb_index', sb_index)

    def add_bb_index(self, table_id: int, bb_index: int) -> None:
        self.r.set(f'{table_id}:bb_index', bb_index)

    def add_d_index(self, table_id: int, d_index: int) -> None:
        self.r.set(f'{table_id}:d_index', d_index)

    def get_sb_index(self, table_id: int) -> int:
        sb_index = self.r.get(f'{table_id}:sb_index')
        return int(sb_index.decode() if isinstance(sb_index, bytes) else sb_index)
    
    def get_bb_index(self, table_id: int) -> int:
        bb_index = self.r.get(f'{table_id}:bb_index')
        return int(bb_index.decode() if isinstance(bb_index, bytes) else bb_index)
    
    def get_d_index(self, table_id: int) -> int:
        d_index = self.r.get(f'{table_id}:d_index')
        return int(d_index.decode() if isinstance(d_index, bytes) else d_index)
    
    def remove_indexes(self, table_id: int) -> None:
        self.r.delete(f'{table_id}:sb_index')
        self.r.delete(f'{table_id}:bb_index')
        self.r.delete(f'{table_id}:d_index')


    def add_current_turn(self, table_id: int, current_turn: int) -> None:
        self.r.set(f'{table_id}:current_turn', current_turn)

    def get_current_turn(self, table_id: int) -> int:
        current_turn = self.r.get(f'{table_id}:current_turn')
        return int(current_turn.decode() if isinstance(current_turn, bytes) else current_turn) if current_turn else None
    
    def remove_current_turn(self, table_id: int) -> None:
        self.r.delete(f'{table_id}:current_turn')


    def add_player_to_stage(self, table_id: int, stage: int, username: str) -> None:
        self.r.sadd(f'{table_id}:stage:{stage}:players', username)

    def get_players_who_played_on_stage(self, table_id: int, stage: int) -> set:
        players_who_played = self.r.smembers(f'{table_id}:stage:{stage}:players')
        return {player.decode() if isinstance(player, bytes) else player for player in players_who_played}

    def remove_players_for_stage(self, table_id: int, stage: int) -> None:
        self.r.delete(f'{table_id}:stage:{stage}:players')

redis_manager = RedisManager()


class PSQLManager:
    async def get_table_by_id(self, table_id: int, session: AsyncSession = Depends(get_async_session)) -> Table:
        result_table = await session.execute(
            select(Table)
            .options(selectinload(Table.creator))
            .where(Table.id == table_id)
        )
        table = result_table.scalars().first()
        return table
    
    async def get_all_tables(self, session: AsyncSession = Depends(get_async_session)) -> Table:
        result_tables = await session.execute(select(Table))
        tables = result_tables.scalars().all()
        return tables
    
    async def get_tables_by_query(self, query: str, session: AsyncSession = Depends(get_async_session)) -> Table:
        result_tables = await session.execute(select(Table).where(Table.name.ilike(f"%{query}%")))
        tables = result_tables.scalars().all()
        return tables
    

psql_manager = PSQLManager()