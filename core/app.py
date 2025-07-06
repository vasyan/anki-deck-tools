"""
Main application orchestration for Anki Vector management
"""
import logging
from typing import Dict, Any, List, Optional

from database.manager import DatabaseManager
from services.card_service import CardService
from services.embedding_service import EmbeddingService
from models.schemas import VectorSearchRequest

logger = logging.getLogger(__name__)

class AnkiVectorApp:
    """Main application class for Anki Vector management"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or DatabaseManager()
        self.card_service = CardService(self.db_manager)
        self.embedding_service = EmbeddingService(self.db_manager)
        logger.info("AnkiVectorApp initialized")
    
    # Card operations (delegate to CardService)
    async def sync_deck(self, deck_name: str) -> Dict[str, Any]:
        """Sync a specific deck from Anki"""
        return await self.card_service.sync_deck(deck_name)
    
    async def sync_all_decks(self) -> Dict[str, Any]:
        """Sync all decks from Anki"""
        return await self.card_service.sync_all_decks()
    
    # Embedding operations (delegate to EmbeddingService)
    async def generate_embeddings(self, 
                                card_ids: Optional[List[int]] = None,
                                deck_name: Optional[str] = None,
                                force_regenerate: bool = False) -> Dict[str, Any]:
        """Generate embeddings for cards"""
        return await self.embedding_service.generate_embeddings(
            card_ids=card_ids,
            deck_name=deck_name,
            force_regenerate=force_regenerate
        )
    
    async def generate_embeddings_for_all_decks(self, force_regenerate: bool = False) -> Dict[str, Any]:
        """Generate embeddings for all decks"""
        return await self.embedding_service.generate_embeddings_for_all_decks(force_regenerate=force_regenerate)
    
    async def search_similar_cards(self, request: VectorSearchRequest) -> List[Dict[str, Any]]:
        """Search for similar cards using vector similarity"""
        return await self.embedding_service.search_similar_cards(request)
    
    async def get_embedding_statistics(self) -> Dict[str, Any]:
        """Get embedding statistics"""
        return await self.embedding_service.get_embedding_statistics() 
