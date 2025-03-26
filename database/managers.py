from fastapi import Depends

from redis import Redis

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.future import select

from .database import get_async_session
from .models import Table
from config import REDIS_HOST


class RedisManager:
    def __init__(self):
        self.r = Redis(host=REDIS_HOST)


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


    def get_player_balance(self, username: str) -> int:
        balance = self.r.get(f'{username}:balance')
        return int(balance.decode()) if isinstance(balance, bytes) else balance

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


    def add_indexes(self, table_id: int, sb_index: int, bb_index: int, d_index: int) -> None:
        self.r.set(f'{table_id}:sb_index', sb_index)
        self.r.set(f'{table_id}:bb_index', bb_index)
        self.r.set(f'{table_id}:d_index', d_index)
    
    def get_indexes(self, table_id: int) -> int:
        sb_index = self.r.get(f'{table_id}:sb_index')
        bb_index = self.r.get(f'{table_id}:bb_index')
        d_index = self.r.get(f'{table_id}:d_index')
        return int(sb_index.decode() if isinstance(sb_index, bytes) else sb_index), int(bb_index.decode() if isinstance(bb_index, bytes) else bb_index), int(d_index.decode() if isinstance(d_index, bytes) else d_index)
    
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


    def set_player_done_move(self, table_id: int, username: str, done: bool) -> None:
        self.r.set(f'{table_id}:player_done_move:{username}', str(done))

    def get_player_done_move(self, table_id: int, username: str) -> bool:
        done = self.r.get(f'{table_id}:player_done_move:{username}')
        normal_done = str(done.decode() if isinstance(done, bytes) else done)
        return True if normal_done == 'True' else False if done else False
    
    def remove_player_done_move(self, table_id: int, username: str) -> None:
        self.r.delete(f'{table_id}:player_done_move:{username}')


    def set_player_folded(self, table_id: int, username: str, folded: bool) -> None:
        self.r.set(f'{table_id}:player_folded:{username}', str(folded))

    def get_player_folded(self, table_id: int, username: str) -> bool:
        folded = self.r.get(f'{table_id}:player_folded:{username}')
        normal_folded = str(folded.decode() if isinstance(folded, bytes) else folded)
        return True if normal_folded == 'True' else False if folded else False
    
    def remove_player_folded(self, table_id: int, username: str) -> None:
        self.r.delete(f'{table_id}:player_folded:{username}')


    def add_raise_amount(self, table_id: int, amount: int) -> None:
        self.r.set(f'{table_id}:raise_amount', amount)

    def get_raise_amount(self, table_id: int) -> int | None:
        raise_amount = self.r.get(f'{table_id}:raise_amount')
        return int(raise_amount.decode()) if isinstance(raise_amount, bytes) else raise_amount
    
    def remove_raise_amount(self, table_id: int) -> None:
        self.r.delete(f'{table_id}:raise_amount')
        

    def add_community_cards(self, table_id: int, community_cards: dict) -> None:
        self.r.set(f'{table_id}:community_cards:flop', ','.join(community_cards['flop']))
        self.r.set(f'{table_id}:community_cards:turn', ','.join(community_cards['turn']))
        self.r.set(f'{table_id}:community_cards:river', ','.join(community_cards['river']))

    def get_community_cards(self, table_id: int) -> dict:
        flop = self.r.get(f'{table_id}:community_cards:flop')
        turn = self.r.get(f'{table_id}:community_cards:turn')
        river = self.r.get(f'{table_id}:community_cards:river')

        return {
            'flop': flop.decode().split(',') if isinstance(flop, bytes) else flop if flop else [],
            'turn': turn.decode().split(',') if isinstance(turn, bytes) else turn if turn else [],
            'river': river.decode().split(',') if isinstance(river, bytes) else river if river else []
        }

    def remove_community_cards(self, table_id: int) -> None:
        self.r.delete(f'{table_id}:community_cards:flop')
        self.r.delete(f'{table_id}:community_cards:turn')
        self.r.delete(f'{table_id}:community_cards:river')


    def add_current_stage(self, table_id: int, stage: str) -> None:
        self.r.set(f'{table_id}:current_stage', stage)

    def get_current_stage(self, table_id: int) -> str | int:
        stage = self.r.get(f'{table_id}:current_stage')
        return stage.decode() if isinstance(stage, bytes) else stage if stage else 0
    
    def remove_current_stage(self, table_id: int) -> None:
        self.r.delete(f'{table_id}:current_stage')
        

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
    

    async def delete_table_by_id(self, table_id: int, session: AsyncSession = Depends(get_async_session)) -> None:
        result_table = await session.execute(select(Table).where(Table.id == table_id))
        table = result_table.scalar_one_or_none()

        if not table:
            return

        await session.delete(table)
        await session.commit()
    

psql_manager = PSQLManager()