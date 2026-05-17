import os
from pymongo import MongoClient

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://mongodb:27017")

_client: MongoClient = None
_db = None


def connect_db() -> None:
    global _client, _db
    _client = MongoClient(MONGODB_URL)
    _db = _client["order_db"]


def close_db() -> None:
    global _client
    if _client:
        _client.close()


def get_db():
    return _db
