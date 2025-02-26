from fastapi.websockets import WebSocket

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pathlib import Path

from typing import List

import os
import logging
import json


load_dotenv()


POSTGRES_USER = os.environ.get("POSTGRES_USER", "inksne")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "inksne")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "inksne")


class AuthJWT(BaseModel):
    private_key_path: Path = Path("certs") / "jwt-private.pem"
    public_key_path: Path = Path("certs") / "jwt-public.pem"
    algorithm: str = "RS256"
    access_token_expire_minutes: int = 5
    refresh_token_expire_days: int = 30


class Settings(BaseSettings):
    auth_jwt: AuthJWT = AuthJWT()


settings = Settings()


class DBSettings(BaseSettings):
    db_url: str = f'postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:5432/{POSTGRES_DB}'
    db_echo: bool = False

db_settings = DBSettings()


def configure_logging(level: int = logging.INFO):
    logging.basicConfig(
        level=level,
        datefmt="%Y-%m-%d %H:%M:%S",
        format="[%(asctime)s.%(msecs)03d] %(funcName)20s %(module)s:%(lineno)d %(levelname)-8s - %(message)s"
    )


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.players: List[str] = []

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.players.append(username)

    def disconnect(self, websocket: WebSocket, username: str):
        self.active_connections.remove(websocket)
        self.players.remove(username)

    async def broadcast(self):
        message = json.dumps({'players': self.players})
        for connection in self.active_connections:
            await connection.send_text(message)


ws_manager = ConnectionManager()