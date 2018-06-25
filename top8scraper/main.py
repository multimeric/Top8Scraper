import argparse
import asyncio

import sqlalchemy
from sqlalchemy.orm import sessionmaker

from top8scraper.scrape import create_tables, latest_scraped, scrape_events, update_formats, newest_event


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', metavar='connection_string', type=sqlalchemy.create_engine)
    return parser


def main():
    args = get_parser().parse_args()

    # Setup the DB connection
    engine = args.engine
    Session = sessionmaker(bind=engine)
    dbsession = Session()

    # Scrape
    create_tables(engine)
    update_formats(dbsession)
    next_id = latest_scraped(dbsession) + 1  # The next event to scrape is one after the last one we scraped
    newest_id = newest_event()

    # Scrape
    loop = asyncio.get_event_loop()
    loop.run_until_complete(scrape_events(next_id, newest_id, dbsession))

    # Add to DB
    dbsession.commit()
    # scrape_events(latest, newest, session)


if __name__ == '__main__':
    main()
