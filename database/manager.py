# TODO: extract specific methods to corresponding services

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import List, Iterator

import sqlite_vec
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from models.database import Base, AnkiCard, VectorEmbedding
from config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class DatabaseManager:
    """Manages database connections and operations"""

    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Create tables
        Base.metadata.create_all(bind=self.engine)

        # Setup sqlite-vec if using SQLite
        if "sqlite" in self.database_url:
            self._setup_sqlite_vec()

    def _setup_sqlite_vec(self):
        """Setup sqlite-vec extension"""
        try:
            # Get raw SQLite connection for extension loading
            conn = sqlite3.connect(self.database_url.replace("sqlite:///", ""))
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)

            # Create vector table for similarity search
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vector_search (
                    id INTEGER PRIMARY KEY,
                    card_id INTEGER NOT NULL,
                    embedding_type TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    FOREIGN KEY (card_id) REFERENCES anki_cards (id)
                )
            """)
            conn.commit()
            conn.close()

            logger.info("sqlite-vec extension loaded successfully")
        except Exception as e:
            logger.error(f"Failed to setup sqlite-vec: {e}")

    @contextmanager
    def get_session(self) -> Iterator[Session]:
        """Get database session with context manager"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    async def get_cards_by_deck(self, deck_name: str) -> List[AnkiCard]:
        """Get all cards for a specific deck"""
        with self.get_session() as session:
            return session.query(AnkiCard).filter_by(deck_name=deck_name).all()

    async def store_vector_embedding(self, card_id: int, embedding: List[float],
                                   embedding_type: str) -> int:
        """Store vector embedding for a card"""
        with self.get_session() as session:
            # Store in SQLAlchemy table
            vector_embedding = VectorEmbedding(
                card_id=card_id,
                embedding_type=embedding_type,
                vector_data=json.dumps(embedding),
                vector_dimension=len(embedding)
            )
            session.add(vector_embedding)
            session.commit()  # Commit first to avoid locks

            # Store in sqlite-vec table after main commit (sequential, not concurrent)
            if "sqlite" in self.database_url:
                try:
                    self._store_in_sqlite_vec(card_id, embedding, embedding_type)
                except Exception as e:
                    # Log but don't fail the main operation
                    logger.warning(f"Failed to store in sqlite-vec for card {card_id}: {e}")

            return vector_embedding.id

    def _store_in_sqlite_vec(self, card_id: int, embedding: List[float], embedding_type: str):
        """Store embedding in sqlite-vec format"""
        # Use a timeout and WAL mode to reduce lock contention
        db_path = self.database_url.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path, timeout=30.0)
        try:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)

            # Convert embedding to sqlite-vec format
            vector_blob = sqlite_vec.serialize_float32(embedding)

            conn.execute("""
                INSERT OR REPLACE INTO vector_search (card_id, embedding_type, vector)
                VALUES (?, ?, ?)
            """, (card_id, embedding_type, vector_blob))

            conn.commit()
        finally:
            conn.close()
