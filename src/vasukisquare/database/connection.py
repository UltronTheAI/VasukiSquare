"""MongoDB connection lifecycle management using PyMongo."""

from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from vasukisquare.config import Settings, get_settings


class DatabaseManager:
    """Manages PyMongo client, database connection lifecycle, and schema initialization."""

    def __init__(self, settings: Optional[Settings] = None, db: Optional[Database] = None):
        self.settings = settings or get_settings()
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = db

    @property
    def client(self) -> MongoClient:
        """Get or initialize the MongoClient instance."""
        if self._client is None:
            self._client = MongoClient(
                self.settings.mongodb_uri,
                serverSelectionTimeoutMS=5000,
            )
        return self._client

    @property
    def db(self) -> Database:
        """Get the configured database."""
        if self._db is not None:
            return self._db
        return self.client[self.settings.mongodb_database]

    @db.setter
    def db(self, value: Database) -> None:
        """Set a custom database instance (e.g. for testing)."""
        self._db = value

    def init_all_indexes(self) -> None:
        """Initialize all required MongoDB indexes across collections."""
        from vasukisquare.database.repository import (
            BookRepository,
            PageRepository,
            CoverRepository,
            AdRepository,
        )

        book_repo = BookRepository(self.db)
        page_repo = PageRepository(self.db)
        cover_repo = CoverRepository(self.db)
        ad_repo = AdRepository(self.db)

        book_repo.create_indexes()
        page_repo.create_indexes()
        cover_repo.create_indexes()
        ad_repo.create_indexes()

    def close(self) -> None:
        """Close the MongoDB connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
