from urllib.parse import urlparse, parse_qs
import asyncio
import datetime

import aiohttp
import requests
from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import Session
from sqlalchemy import table, column, select, true, func
from bs4 import BeautifulSoup
from progress.bar import Bar
from aiohttp import ClientSession

from top8scraper import models

EVENT_URL = 'http://mtgtop8.com/event'


def get_or_create(session: Session, model: models.Base, **attributes):
    """
    Returns a model instance if one already exists in the database with these attributes, or otherwise creates a new
        one with these attributes
    :param session: The database session to use for database interaction
    :param model: Model corresponding to the table we want to insert/select from
    :param attributes: Model fields used to find/create the database row
    :return: An instance of the model class
    """
    instance = session.query(model).filter_by(**attributes).first()
    if instance:
        return instance
    else:
        instance = model(**attributes)
        session.add(instance)
        return instance


def update_formats(session: Session):
    """
    Ensures the format table is up-to-date in the database
    :param session: The database session to use for database interaction
    """
    formats = [
        ('Vintage', 'VI'),
        ('Legacy', 'LE'),
        ('Modern', 'MO'),
        ('Standard', 'ST'),
        ('Commander', 'EDH'),
        ('Pauper', 'PAU'),
        ('Peasant', 'PEA'),
        ('Block', 'BL'),
        ('Extended', 'EX'),
        ('Highlander', 'HIGH'),
        ('Canadian Highlander', 'CHL'),
        ('Limited', None),
    ]

    for name, code in formats:
        get_or_create(session, models.Format, name=name, code=code)


def create_tables(engine: Engine):
    models.Base.metadata.create_all(engine)


def newest_event() -> int:
    """
    Calculates the newest event stored by top8
    """
    response = requests.get('http://mtgtop8.com/index')
    soup = BeautifulSoup(response.text, 'lxml')
    recent_events = []
    for star in soup.select('td.O16'):
        link = star.find_parent('tr').select('a')[0]
        parsed_url = urlparse(link.attrs['href'])
        parsed_qs = parse_qs(parsed_url.query)
        recent_events.append(int(parsed_qs['e'][0]))

    return max(recent_events)


def latest_scraped(session: Session) -> int:
    """
    Obtains the latest event stored in the database, to use as a starting point for future scraping
    :param session: The database session to use for database interaction
    """
    qry = select([func.max(models.Event.top8id)])
    result = session.execute(qry)
    return result.first()[0] or 0


async def scrape_events(start_id: int, end_id: int, session: Session):
    """
    Scrapes a series of Magic events asynchronously
    :param start_id: The first (numerically lowest) event ID to scrape
    :param end_id: The last (numerically highest) event ID to scrape)
    :param session: The database session to use for database interaction
    """
    bar = Bar('Processing', max=end_id)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=100)) as httpsession:
        await asyncio.gather(*get_event_futures(start_id, end_id, session, httpsession, bar))

    bar.finish()


def get_event_futures(start_id: int, end_id: int, db_session: Session, http_session: ClientSession, progress_bar: Bar):
    """
    Generator that returns an iterable of futures that each scrape an event
    :param start_id: The first (numerically lowest) event ID to scrape
    :param end_id: The last (numerically highest) event ID to scrape)
    :param db_session: The database session to use for database interaction
    :param http_session: The HTTP session to use for HTTP requests
    :param progress_bar: The progress bar to update when a task finishes
    """
    for i in range(start_id, end_id + 1):
        yield scrape_event(i, db_session, http_session, progress_bar)


async def scrape_event(event_id: int, db_session: Session, http_session: ClientSession, progress_bar: Bar):
    """
    Async function that scrapes an event asynchronously and adds it to the database
    :param event_id: The mtgtop8 ID for the event
    :param db_session: The database session to use for database interaction
    :param http_session: The HTTP session to use for HTTP requests
    :param progress_bar: The progress bar to update when a task finishes
    """
    async with http_session.get(EVENT_URL, params={'e': event_id}) as response:
        soup = BeautifulSoup(await response.text(), 'lxml')

    # Get event metadata
    meta = soup.select('td.S14')[0]
    format_name = str(meta.contents[0]).strip()
    player_date = str(meta.contents[2]).replace('players', '').split('-')
    if len(player_date) == 2:
        players = int(player_date[0].strip())
        date = player_date[1]
    else:
        players = None
        date = player_date[0]

    date = datetime.datetime.strptime(date.strip(), '%d/%m/%y').date()

    event_name = soup.select('.S18')[0].text

    format = db_session.query(models.Format).filter(models.Format.name == format_name).first()

    event = models.Event(
        top8id=event_id,
        date=date,
        player_count=players,
        name=event_name,
        format=format
    )

    for deck in soup.select('div.S14 > a, div.W14 > a'):
        await scrape_deck(deck.attrs['href'], event, db_session, http_session)

    progress_bar.next()


async def scrape_deck(deck_url: str, event: models.Event, db_session: Session, http_session: ClientSession):
    """
    Scrapes the deck pointed to by the provided URL and adds it to the database
    :param deck_url: mtgtop8 URL for the deck
    :param event: The event this deck was used at
    :param db_session: The database session to use for database interaction
    :param http_session: The HTTP session to use for HTTP requests
    """
    async with http_session.get(EVENT_URL + deck_url) as response:
        soup = BeautifulSoup(await response.text(), 'html.parser')

    # Scrape player metadata from sidebar
    meta = soup.select('.chosen_tr')[0]
    children = meta.select('> div')
    rank = children[0].text.split('-')[0]
    player = children[2].text.replace('"', '')

    player = get_or_create(db_session, models.Player, name=player)
    deck = models.Deck(
        player=player,
        event=event,
        rank=rank
    )
    db_session.add(deck)

    # Scrape the cards in the deck
    for card_el in soup.select('td.G14 > div'):
        js = card_el.attrs['onclick']
        card_id = js.split(',')[-2].replace("'", '')

        entry = models.DeckEntry(
            deck=deck,
            card_id=int(card_id)
        )
        db_session.add(entry)
