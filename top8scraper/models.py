from sqlalchemy import Column, Date, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Format(Base):
    __tablename__ = 'format'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)
    code = Column(String, unique=True)

    events = relationship('Event', back_populates='format')


class Event(Base):
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True, autoincrement=True)
    top8id = Column(Integer, unique=True, nullable=True)
    name = Column(String)
    date = Column(Date)
    player_count = Column(Integer)
    event_ranking = Column(Integer)
    format_id = Column(Integer, ForeignKey('format.id'))

    format = relationship('Format', back_populates='events')
    decks = relationship('Deck', back_populates='event')


class Player(Base):
    __tablename__ = 'player'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)

    decks = relationship('Deck', back_populates='player')


class Deck(Base):
    __tablename__ = 'deck'
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('player.id'))
    event_id = Column(Integer, ForeignKey('event.id'))
    rank = Column(Integer)

    player = relationship('Player', back_populates='decks')
    event = relationship('Event', back_populates='decks')
    cards = relationship('DeckEntry', back_populates='deck')


class DeckEntry(Base):
    __tablename__ = 'deck_entry'
    id = Column(Integer, primary_key=True, autoincrement=True)
    deck_id = Column(Integer, ForeignKey('deck.id'))
    card_id = Column(Integer)

    deck = relationship('Deck', back_populates='cards')
