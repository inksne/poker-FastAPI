from fastapi.websockets import WebSocket

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pathlib import Path

from typing import List, Final

import os
import logging
import json


load_dotenv()


POSTGRES_USER: Final[str] = os.environ.get("POSTGRES_USER", "inksne")
POSTGRES_PASSWORD: Final[str] = os.environ.get("POSTGRES_PASSWORD", "inksne")
POSTGRES_DB: Final[str] = os.environ.get("POSTGRES_DB", "inksne")
POSTGRES_HOST: Final[str] = os.environ.get("POSTGRES_HOST", "postgres")

REDIS_HOST: Final[str] = os.environ.get("REDIS_HOST", "redis")

TEST_ACCESS_TOKEN: Final[str] = os.environ.get("TEST_ACCESS_TOKEN")

GAME_STAGES = ('Preflop', 'Flop', 'Turn', 'River')


class AuthJWT(BaseModel):
    private_key_path: Path = Path("certs") / "jwt-private.pem"
    public_key_path: Path = Path("certs") / "jwt-public.pem"
    algorithm: Final[str] = "RS256"
    access_token_expire_minutes: int = 5
    refresh_token_expire_days: int = 30


class Settings(BaseSettings):
    auth_jwt: AuthJWT = AuthJWT()


settings = Settings()


class DBSettings(BaseSettings):
    db_url: str = f'postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:5432/{POSTGRES_DB}'


db_settings = DBSettings()


def configure_logging(level: int = logging.INFO):
    logging.basicConfig(
        level=level,
        datefmt="%Y-%m-%d %H:%M:%S",
        format="[%(asctime)s.%(msecs)03d] %(funcName)20s %(module)s:%(lineno)d %(levelname)-8s - %(message)s"
    )


configure_logging()
logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.players: List[dict] = []

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.players.append({'username': username, 'websocket': websocket})

    def disconnect(self, websocket: WebSocket, username: str):
        self.active_connections.remove(websocket)
        for player in self.players:
            if player['username'] == username and player['websocket'] == websocket:
                self.players.remove(player)
                break

    async def broadcast_players_list(self):
        players_list = [{'username': player['username']} for player in self.players]
        for connection in self.active_connections:
            await connection.send_text(json.dumps({'players': players_list}))

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_text(json.dumps(message))


ws_manager = ConnectionManager()