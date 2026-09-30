import psycopg

from src.config import settings


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url)
