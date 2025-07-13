"""
FastAPI server for the Anki Vector application
"""
import json
import logging
from typing import List, Dict, Any, Generator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.app import AnkiVectorApp
from database.manager import DatabaseManager
from models.schemas import AnkiCardResponse, VectorSearchRequest, SyncCardRequest
from models.database import AnkiCard
from config import settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Initialize app and database
app_instance = AnkiVectorApp()
db_manager = DatabaseManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting Anki Vector API server")
    yield
    logger.info("Shutting down Anki Vector API server")

# FastAPI app
app = FastAPI(
    title="Anki Vector API",
    description="API for managing Anki cards with vector embeddings",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get database session
def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    with db_manager.get_session() as session:
        yield session

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Anki Vector API is running"}

# Sync endpoints
@app.post("/sync/deck")
async def sync_deck(request: SyncCardRequest) -> Dict[str, Any]:
    """Sync specific deck from Anki"""
    if not request.deck_names or len(request.deck_names) != 1:
        raise HTTPException(status_code=400, detail="Must provide exactly one deck name")
    
    deck_name = request.deck_names[0]
    try:
        result = await app_instance.sync_deck(deck_name)
        return result
    except Exception as e:
        logger.error(f"Error syncing deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync/all")
async def sync_all_decks() -> Dict[str, Any]:
    """Sync all decks from Anki"""
    try:
        result = await app_instance.sync_all_decks()
        return result
    except Exception as e:
        logger.error(f"Error syncing all decks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Card endpoints  
@app.get("/cards/deck", response_model=List[AnkiCardResponse])
async def get_cards_by_deck(deck_name: str) -> List[AnkiCardResponse]:
    """Get all cards for a specific deck"""
    try:
        cards = await db_manager.get_cards_by_deck(deck_name)
        return [
            AnkiCardResponse(
                id=card.id,
                anki_note_id=card.anki_note_id,
                deck_name=card.deck_name,
                model_name=card.model_name,
                front_text=card.front_text,
                back_text=card.back_text,
                tags=card.tags if card.tags else [],
                created_at=card.created_at,
                updated_at=card.updated_at,
                is_draft=getattr(card, 'is_draft', 1),
                example=getattr(card, 'example', None)
            )
            for card in cards
        ]
    except Exception as e:
        logger.error(f"Error getting cards for deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cards", response_model=List[AnkiCardResponse])
async def get_all_cards(limit: int = 100, offset: int = 0) -> List[AnkiCardResponse]:
    """Get all cards with pagination"""
    try:
        with db_manager.get_session() as session:
            cards = session.query(AnkiCard).offset(offset).limit(limit).all()
            return [
                AnkiCardResponse(
                    id=card.id,
                    anki_note_id=card.anki_note_id,
                    deck_name=card.deck_name,
                    model_name=card.model_name,
                    front_text=card.front_text,
                    back_text=card.back_text,
                    tags=card.tags if card.tags else [],
                    created_at=card.created_at,
                    updated_at=card.updated_at,
                    is_draft=getattr(card, 'is_draft', 1),
                    example=getattr(card, 'example', None)
                )
                for card in cards
            ]
    except Exception as e:
        logger.error(f"Error getting all cards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cards/{card_id}/audio")
async def get_card_audio(card_id: int):
	"""Return the audio for a card as an audio file (e.g., mp3)"""
	with db_manager.get_session() as session:
		card = session.get(AnkiCard, card_id)
		if not card or not card.audio:
			raise HTTPException(status_code=404, detail="Card or audio not found")
		# Default to mp3, could be made dynamic if needed
		return Response(card.audio, media_type="audio/mpeg")

# Embedding endpoints
@app.post("/embeddings/generate")
async def generate_embeddings(
    request: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate embeddings for specified cards"""
    try:
        card_ids = request.get("card_ids") if request else None
        force_regenerate = request.get("force_regenerate", False) if request else False
        
        result = await app_instance.generate_embeddings(
            card_ids=card_ids, 
            force_regenerate=force_regenerate
        )
        return result
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings/generate/deck/{deck_name}")
async def generate_embeddings_for_deck(
    deck_name: str, 
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """Generate embeddings for all cards in a specific deck"""
    try:
        result = await app_instance.generate_embeddings(
            deck_name=deck_name, 
            force_regenerate=force_regenerate
        )
        return result
    except Exception as e:
        logger.error(f"Error generating embeddings for deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings/generate/all")
async def generate_embeddings_for_all_decks(force_regenerate: bool = False) -> Dict[str, Any]:
    """Generate embeddings for all cards in all decks"""
    try:
        result = await app_instance.generate_embeddings_for_all_decks(force_regenerate=force_regenerate)
        return result
    except Exception as e:
        logger.error(f"Error generating embeddings for all decks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings/search")
async def search_similar_cards(request: VectorSearchRequest) -> List[Dict[str, Any]]:
    """Search for similar cards using vector similarity"""
    try:
        results = await app_instance.search_similar_cards(request)
        return results
    except Exception as e:
        logger.error(f"Error searching similar cards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/embeddings/search/{deck_name}")
async def search_similar_cards_in_deck(
    deck_name: str,
    query_text: str,
    embedding_type: str = "combined",
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """Search for similar cards within a specific deck"""
    try:
        request = VectorSearchRequest(
            query_text=query_text,
            deck_name=deck_name,
            embedding_type=embedding_type,
            top_k=top_k
        )
        results = await app_instance.search_similar_cards(request)
        return results
    except Exception as e:
        logger.error(f"Error searching similar cards in deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/embeddings/stats")
async def get_embedding_statistics() -> Dict[str, Any]:
    """Get detailed embedding statistics"""
    try:
        result = await app_instance.get_embedding_statistics()
        return result
    except Exception as e:
        logger.error(f"Error getting embedding statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Stats endpoints
@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get database statistics"""
    try:
        with db_manager.get_session() as session:
            total_cards = session.query(AnkiCard).count()
            deck_counts = {}
            
            # Get card count per deck
            decks = session.query(AnkiCard.deck_name).distinct().all()
            for (deck_name,) in decks:
                count = session.query(AnkiCard).filter_by(deck_name=deck_name).count()
                deck_counts[deck_name] = count
            
            return {
                "total_cards": total_cards,
                "total_decks": len(deck_counts),
                "deck_counts": deck_counts
            }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    ) 
