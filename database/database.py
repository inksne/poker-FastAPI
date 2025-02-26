from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
from .models import Base

from redis import Redis


DATABASE_URL = f'postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:5432/{POSTGRES_DB}'


engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


class RedisManager:
    def __init__(self):
        self.r = Redis(host='localhost', port=6379, db=0)

    def add_player(self, table_id: int, username: str):
        self.r.sadd(table_id, username)

    def get_players(self, table_id: int):
        players = self.r.smembers(table_id)
        return players
    
    def remove_player(self, table_id: int, username: str):
        self.r.srem(table_id, username)
        

redis_manager = RedisManager()