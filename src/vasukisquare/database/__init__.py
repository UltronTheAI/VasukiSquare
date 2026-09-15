"""Database domain: PyMongo connection lifecycle and repositories."""

from vasukisquare.database.connection import DatabaseManager
from vasukisquare.database.repository import (
    BookRepository,
    PageRepository,
    CoverRepository,
    AdRepository,
    select_weighted_ad,
)

__all__ = [
    "DatabaseManager",
    "BookRepository",
    "PageRepository",
    "CoverRepository",
    "AdRepository",
    "select_weighted_ad",
]

