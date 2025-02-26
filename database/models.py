from sqlalchemy import Integer, String, Column, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(length=24), unique=True, nullable=False)
    email = Column(String)
    password = Column(String(length=1024), nullable=False)

    table = relationship('Table', back_populates='creator')
    tables = relationship('TablePlayer', back_populates='user')


class Table(Base):
    __tablename__ = 'tables'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=32), unique=True, nullable=False)
    start_money = Column(Integer, default=1000, nullable=False)
    big_blind = Column(Integer, default=50, nullable=False)
    small_blind = Column(Integer, nullable=False)

    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    creator = relationship('User', back_populates='table')
    players = relationship('TablePlayer', back_populates='table')


class TablePlayer(Base):
    __tablename__ = 'table_players'
    table_id = Column(Integer, ForeignKey('tables.id'), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)

    table = relationship('Table', back_populates='players')
    user = relationship('User', back_populates='tables')
