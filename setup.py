from setuptools import setup, find_packages

setup(
    name='top8scraper',
    version='0.0.1',
    packages=find_packages(),
    description='A script that scrapes http://mtgtop8.com for Magic the Gathering tournament results',
    install_requires=[
        'sqlalchemy',
        'beautifulsoup4',
        'requests',
        'lxml',
        'progress',
        'aiohttp'
    ]
)