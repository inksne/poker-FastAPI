from sqlalchemy import Integer, String, Column, ForeignKey
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


class Table(Base):
    __tablename__ = 'tables'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=32), unique=True, nullable=False)
    start_money = Column(Integer, nullable=False)
    big_blind = Column(Integer, nullable=False)
    small_blind = Column(Integer, nullable=False)

    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    creator = relationship('User', back_populates='table')