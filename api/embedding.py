from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List
from database.manager import DatabaseManager
import logging
from models.schemas import VectorSearchRequest
from core.app import AnkiVectorApp

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

db_manager = DatabaseManager()

anki_vector_instance = AnkiVectorApp(db_manager)

router = APIRouter()
# Embedding endpoints
@router.post("/embeddings/generate")
async def generate_embeddings(
    request: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate embeddings for specified cards"""
    try:
        card_ids = request.get("card_ids") if request else None
        force_regenerate = request.get("force_regenerate", False) if request else False
        
        result = await anki_vector_instance.generate_embeddings(
            card_ids=card_ids, 
            force_regenerate=force_regenerate
        )
        return result
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/embeddings/generate/deck/{deck_name}")
async def generate_embeddings_for_deck(
    deck_name: str, 
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """Generate embeddings for all cards in a specific deck"""
    try:
        result = await anki_vector_instance.generate_embeddings(
            deck_name=deck_name, 
            force_regenerate=force_regenerate
        )
        return result
    except Exception as e:
        logger.error(f"Error generating embeddings for deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/embeddings/generate/all")
async def generate_embeddings_for_all_decks(force_regenerate: bool = False) -> Dict[str, Any]:
    """Generate embeddings for all cards in all decks"""
    try:
        result = await anki_vector_instance.generate_embeddings_for_all_decks(force_regenerate=force_regenerate)
        return result
    except Exception as e:
        logger.error(f"Error generating embeddings for all decks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/embeddings/search")
async def search_similar_cards(request: VectorSearchRequest) -> List[Dict[str, Any]]:
    """Search for similar cards using vector similarity"""
    try:
        results = await anki_vector_instance.search_similar_cards(request)
        return results
    except Exception as e:
        logger.error(f"Error searching similar cards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/embeddings/search/{deck_name}")
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
        results = await anki_vector_instance.search_similar_cards(request)
        return results
    except Exception as e:
        logger.error(f"Error searching similar cards in deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/embeddings/stats")
async def get_embedding_statistics() -> Dict[str, Any]:
    """Get detailed embedding statistics"""
    try:
        result = await anki_vector_instance.get_embedding_statistics()
        return result
    except Exception as e:
        logger.error(f"Error getting embedding statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
