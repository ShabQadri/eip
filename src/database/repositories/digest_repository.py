"""
Digest repository.
"""

from src.models.digest import Digest
from src.database.repositories import BaseRepository

class DigestRepository(BaseRepository[Digest]):
    """
    CRUD repository for Digest entity.
    """
    def __init__(self) -> None:
        super().__init__(Digest)
