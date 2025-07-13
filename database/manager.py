"""
Database management and operations
"""
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Optional

import sqlite_vec
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from models.database import Base, AnkiCard, VectorEmbedding
from config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, database_url: str = None):
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
    def get_session(self) -> Session:
        """Get database session with context manager"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    async def store_anki_cards(self, cards_data: List[Dict], deck_name: str) -> List[int]:
        """Store Anki cards in database"""
        stored_ids = []
        
        with self.get_session() as session:
            for card_data in cards_data:
                anki_note_id = card_data.get("noteId")
                is_draft = 0 if anki_note_id is not None else 1
                # Check if card already exists (by anki_note_id if present, else by front/back text)
                if anki_note_id is not None:
                    existing_card = session.query(AnkiCard).filter_by(
                        anki_note_id=anki_note_id
                    ).first()
                else:
                    existing_card = session.query(AnkiCard).filter_by(
                        front_text=self._extract_field_text(card_data["fields"], "Front"),
                        back_text=self._extract_field_text(card_data["fields"], "Back"),
                        deck_name=deck_name
                    ).first()
                print(f"existing_card: {existing_card}")
                
                if existing_card:
                    # Update existing card
                    existing_card.deck_name = card_data["deckName"]
                    existing_card.model_name = card_data.get("modelName")
                    existing_card.front_text = self._extract_field_text(card_data["fields"], "Front")
                    existing_card.back_text = self._extract_field_text(card_data["fields"], "Back")
                    existing_card.tags = card_data.get("tags", [])
                    existing_card.updated_at = datetime.now(timezone.utc)
                    existing_card.is_draft = is_draft
                    stored_ids.append(existing_card.id)
                else:
                    # Create new card
                    print(f"creating new card: {self._extract_field_text(card_data["fields"], "Front")}")
                    try:
                        new_card = AnkiCard(
                            anki_note_id=anki_note_id,
                            model_name=card_data.get("modelName"),
                            front_text=self._extract_field_text(card_data["fields"], "Front"),
                            back_text=self._extract_field_text(card_data["fields"], "Back"),
                            tags=card_data.get("tags", []),
                            deck_name=deck_name,
                            is_draft=is_draft
                        )
                    except Exception as e:
                        print(f"error creating new card: {e}")
                        continue
                    print(f"new_card: {new_card}")
                    session.add(new_card)
                    session.flush()  # Get the ID
                    stored_ids.append(new_card.id)
            
            print(f"stored_ids: {len(stored_ids)}")
            
            session.commit()
        
        return stored_ids
    
    def _extract_field_text(self, fields: Dict, field_name: str) -> Optional[str]:
        """Extract text from Anki field"""
        field_data = fields.get(field_name, {})
        return field_data.get("value") if field_data else None
    
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

    def mark_card_synced(self, card_id: int, anki_note_id: int, model_name: str = None):
        """Mark a card as synced (is_draft=0, set anki_note_id, optionally update model_name)."""
        with self.get_session() as session:
            card = session.query(AnkiCard).get(card_id)
            if card:
                card.is_draft = 0
                card.anki_note_id = anki_note_id
                if model_name:
                    card.model_name = model_name
                card.updated_at = datetime.now(timezone.utc)
                session.commit()

    def add_tag_to_card(self, card_id: int, tag: str):
        """Add a tag to a card's tags list if not already present."""
        with self.get_session() as session:
            card = session.query(AnkiCard).get(card_id)
            if card:
                tags = card.tags or []
                if tag not in tags:
                    tags.append(tag)
                    card.tags = tags
                    card.updated_at = datetime.now(timezone.utc)
                    session.commit() 
