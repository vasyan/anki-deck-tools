"""
Main application for Anki Vector data management
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import random

import httpx
import sqlite3
import sqlite_vec
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from pydantic import BaseModel, Field

from config import settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# SQLAlchemy setup
Base = declarative_base()

# Database Models
class AnkiCard(Base):
    """SQLAlchemy model for Anki cards"""
    __tablename__ = "anki_cards"
    
    id = Column(Integer, primary_key=True)
    anki_note_id = Column(Integer, unique=True, nullable=False)
    deck_name = Column(String(255), nullable=False)
    model_name = Column(String(255), nullable=False)
    front_text = Column(Text)
    back_text = Column(Text)
    tags = Column(JSON)  # Store as JSON array
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to embeddings
    embeddings = relationship("VectorEmbedding", back_populates="card")

class VectorEmbedding(Base):
    """SQLAlchemy model for vector embeddings"""
    __tablename__ = "vector_embeddings"
    
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("anki_cards.id"), nullable=False)
    embedding_type = Column(String(50), nullable=False)  # e.g., 'front', 'back', 'combined'
    vector_data = Column(Text)  # Store as JSON for now, will be BLOB for sqlite-vec
    vector_dimension = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to card
    card = relationship("AnkiCard", back_populates="embeddings")

# Pydantic Models for API responses
class AnkiCardResponse(BaseModel):
    """Response model for Anki cards"""
    id: int
    anki_note_id: int
    deck_name: str
    model_name: str
    front_text: Optional[str] = None
    back_text: Optional[str] = None
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime

class VectorSearchRequest(BaseModel):
    """Request model for vector search"""
    query_text: str
    query_embedding: Optional[List[float]] = None
    top_k: int = Field(default=10, ge=1, le=100)
    deck_name: Optional[str] = None
    embedding_type: str = Field(default="combined")

class SyncCardRequest(BaseModel):
    """Request model for syncing cards"""
    deck_names: Optional[List[str]] = None
    force_update: bool = False

# AnkiConnect Client
class AnkiConnectClient:
    """Client for communicating with AnkiConnect"""
    
    def __init__(self, url: str = None, timeout: int = None):
        self.url = url or settings.anki_connect_url
        self.timeout = timeout or settings.anki_connect_timeout
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def _request(self, action: str, params: Dict = None) -> Any:
        """Make a request to AnkiConnect"""
        data = {
            "action": action,
            "version": 6,
            "params": params or {}
        }
        
        try:
            response = await self.client.post(self.url, json=data)
            response.raise_for_status()
            
            result = response.json()
            if result.get("error"):
                raise Exception(f"AnkiConnect error: {result['error']}")
            
            return result.get("result")
        except httpx.RequestError as e:
            raise Exception(f"Failed to connect to AnkiConnect: {e}")
    
    async def get_version(self) -> int:
        """Get AnkiConnect version"""
        return await self._request("version")
    
    async def get_deck_names(self) -> List[str]:
        """Get all deck names"""
        return await self._request("deckNames")
    
    async def find_notes(self, query: str) -> List[int]:
        """Find notes by query"""
        return await self._request("findNotes", {"query": query})
    
    async def notes_info(self, note_ids: List[int]) -> List[Dict]:
        """Get detailed info for notes"""
        return await self._request("notesInfo", {"notes": note_ids})

# Database Manager
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
                # Check if card already exists
                existing_card = session.query(AnkiCard).filter_by(
                    anki_note_id=card_data["noteId"]
                ).first()
                print(f"existing_card: {existing_card}")
                
                if existing_card:
                    # Update existing card
                    existing_card.deck_name = card_data["deckName"]
                    existing_card.model_name = card_data["modelName"]
                    existing_card.front_text = self._extract_field_text(card_data["fields"], "Front")
                    existing_card.back_text = self._extract_field_text(card_data["fields"], "Back")
                    existing_card.tags = card_data.get("tags", [])
                    existing_card.updated_at = datetime.utcnow()
                    stored_ids.append(existing_card.id)
                else:
                    # Create new card
                    print(f"creating new card: {self._extract_field_text(card_data["fields"], "Front")}")
                    try:
                        new_card = AnkiCard(
                            anki_note_id=card_data["noteId"],
                            model_name=card_data["modelName"],
                            front_text=self._extract_field_text(card_data["fields"], "Front"),
                            back_text=self._extract_field_text(card_data["fields"], "Back"),
                            tags=card_data.get("tags", []),
                            deck_name=deck_name
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
            session.flush()
            
            # Also store in sqlite-vec table for efficient search
            if "sqlite" in self.database_url:
                self._store_in_sqlite_vec(card_id, embedding, embedding_type)
            
            session.commit()
            return vector_embedding.id
    
    def _store_in_sqlite_vec(self, card_id: int, embedding: List[float], embedding_type: str):
        """Store embedding in sqlite-vec format"""
        try:
            conn = sqlite3.connect(self.database_url.replace("sqlite:///", ""))
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
            conn.close()
        except Exception as e:
            logger.error(f"Failed to store in sqlite-vec: {e}")

# Main Application Class
class AnkiVectorApp:
    """Main application class for Anki Vector management"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        logger.info("AnkiVectorApp initialized")
    
    async def sync_deck(self, deck_name: str) -> Dict[str, Any]:
        print(f"calling sync_deck: {deck_name}")
        """Sync a specific deck from Anki"""
        try:
            async with AnkiConnectClient() as anki_client:
                # Find all notes in the deck
                query = f'deck:"{deck_name}"'
                note_ids = await anki_client.find_notes(query)
                
                if not note_ids:
                    return {"message": f"No notes found in deck: {deck_name}", "synced": 0}
                
                # Get detailed note information
                notes_info = await anki_client.notes_info(note_ids)

                # Store cards in database
                stored_ids = await self.db_manager.store_anki_cards(notes_info, deck_name)
                
                return {
                    "message": f"Successfully synced deck: {deck_name}",
                    "synced": len(stored_ids),
                    "card_ids": stored_ids
                }
        
        except Exception as e:
            logger.error(f"Error syncing deck {deck_name}: {e}")
            raise
    
    async def sync_all_decks(self) -> Dict[str, Any]:
        """Sync all decks from Anki"""
        try:
            async with AnkiConnectClient() as anki_client:
                deck_names = await anki_client.get_deck_names()
                
                total_synced = 0
                results = {}
                
                for deck_name in deck_names:
                    try:
                        result = await self.sync_deck(deck_name)
                        results[deck_name] = result
                        total_synced += result["synced"]
                    except Exception as e:
                        logger.error(f"Failed to sync deck {deck_name}: {e}")
                        results[deck_name] = {"error": str(e)}
                
                return {
                    "message": f"Synced {total_synced} cards from {len(deck_names)} decks",
                    "total_synced": total_synced,
                    "deck_results": results
                }
        
        except Exception as e:
            logger.error(f"Error syncing all decks: {e}")
            raise
    
    async def generate_embeddings(self, card_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """Generate embeddings for cards (mock implementation)"""
        try:
            # If no card_ids provided, get all cards without embeddings
            if not card_ids:
                with self.db_manager.get_session() as session:
                    cards_without_embeddings = session.query(AnkiCard).filter(
                        ~AnkiCard.embeddings.any()
                    ).all()
                    card_ids = [card.id for card in cards_without_embeddings]
            
            if not card_ids:
                return {"message": "No cards found for embedding generation", "generated": 0}
            
            generated_count = 0
            
            with self.db_manager.get_session() as session:
                for card_id in card_ids:
                    card = session.query(AnkiCard).filter_by(id=card_id).first()
                    if not card:
                        continue
                    
                    # Mock embedding generation (replace with actual embedding model)
                    embeddings = self._generate_mock_embeddings(card)
                    
                    # Store embeddings
                    for embedding_type, embedding in embeddings.items():
                        await self.db_manager.store_vector_embedding(
                            card_id, embedding, embedding_type
                        )
                    
                    generated_count += 1
            
            logger.info(f"Generated embeddings for {generated_count} cards")
            return {
                "message": f"Generated embeddings for {generated_count} cards",
                "generated": generated_count
            }
        
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    def _generate_mock_embeddings(self, card: AnkiCard) -> Dict[str, List[float]]:
        """Generate mock embeddings for a card (replace with actual model)"""
        
        # Mock embeddings with fixed dimension
        dimension = settings.embedding_dimension
        
        embeddings = {}
        
        if card.front_text:
            # Mock embedding for front text
            embeddings["front"] = [random.random() for _ in range(dimension)]
        
        if card.back_text:
            # Mock embedding for back text
            embeddings["back"] = [random.random() for _ in range(dimension)]
        
        if card.front_text and card.back_text:
            # Mock combined embedding
            embeddings["combined"] = [random.random() for _ in range(dimension)]
        
        return embeddings
    
    async def search_similar_cards(self, request: VectorSearchRequest) -> List[Dict[str, Any]]:
        """Search for similar cards using vector similarity (mock implementation)"""
        try:
            # Mock implementation - in real implementation, use sqlite-vec functions
            if request.query_embedding is None:
                # Generate mock query embedding from text
                request.query_embedding = [random.random() for _ in range(settings.embedding_dimension)]
            
            # Mock results
            mock_results = []
            
            with self.db_manager.get_session() as session:
                # Get some cards (mock search)
                query = session.query(AnkiCard)
                if request.deck_name:
                    query = query.filter_by(deck_name=request.deck_name)
                
                cards = query.limit(request.top_k).all()
                
                for i, card in enumerate(cards):
                    mock_results.append({
                        "card_id": card.id,
                        "anki_note_id": card.anki_note_id,
                        "deck_name": card.deck_name,
                        "front_text": card.front_text,
                        "back_text": card.back_text,
                        "similarity_score": 1.0 - (i * 0.1),  # Mock decreasing similarity
                        "distance": i * 0.1  # Mock increasing distance
                    })
            
            return mock_results
        
        except Exception as e:
            logger.error(f"Error searching similar cards: {e}")
            raise

# CLI functions (basic implementation)
async def main():
    """Main function for basic testing"""
    app = AnkiVectorApp()
    
    try:
        # Test AnkiConnect connection
        async with AnkiConnectClient() as client:
            version = await client.get_version()
            print(f"AnkiConnect version: {version}")
            
            decks = await client.get_deck_names()
            print(f"Available decks: {decks}")
        
        print("AnkiVectorApp initialized successfully!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 
