"""
Service for managing vector embedding operations
"""
import logging
from typing import Dict, Any, List, Optional

from database.manager import DatabaseManager
from models.database import AnkiCard, VectorEmbedding
from models.schemas import VectorSearchRequest

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for vector embedding operations"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or DatabaseManager()
        self._embedding_manager = None  # Lazy initialization
    
    async def _get_embedding_manager(self):
        """Get embedding manager with lazy initialization"""
        if self._embedding_manager is None:
            # Import here to avoid circular imports
            from embedding_processor import EmbeddingManager, EmbeddingConfig
            
            config = EmbeddingConfig()
            self._embedding_manager = EmbeddingManager(config)
            
            if not await self._embedding_manager.initialize():
                raise Exception("Failed to initialize embedding manager")
                
        return self._embedding_manager
    
    async def generate_embeddings(self, 
                                card_ids: Optional[List[int]] = None,
                                deck_name: Optional[str] = None,
                                force_regenerate: bool = False) -> Dict[str, Any]:
        """Generate embeddings for cards using the embedding processor"""
        try:
            embedding_manager = await self._get_embedding_manager()
            
            # If deck_name is specified, generate for entire deck
            if deck_name:
                return await embedding_manager.generate_embeddings_for_deck(
                    deck_name, force_regenerate=force_regenerate
                )
            
            # If no card_ids provided, process all cards without embeddings
            if not card_ids:
                with self.db_manager.get_session() as session:
                    cards_without_embeddings = session.query(AnkiCard).filter(
                        ~AnkiCard.embeddings.any()
                    ).all()
                    card_ids = [card.id for card in cards_without_embeddings]
            
            if not card_ids:
                return {"message": "No cards found for embedding generation", "generated": 0}
            
            # Process specific cards
            generated_count = 0
            failed_count = 0
            
            with self.db_manager.get_session() as session:
                cards = session.query(AnkiCard).filter(AnkiCard.id.in_(card_ids)).all()
                
                for card in cards:
                    try:
                        # Generate embeddings for each type
                        for embedding_type in embedding_manager.config.embedding_types:
                            # Check if embedding already exists
                            if not force_regenerate:
                                existing = embedding_manager._get_existing_embedding(card.id, embedding_type)
                                if existing:
                                    continue
                            
                            # Generate embedding
                            result = await embedding_manager.generator.process_card(card, embedding_type)
                            
                            if result.success:
                                try:
                                    # Store in database (sequential to avoid lock issues)
                                    await self.db_manager.store_vector_embedding(
                                        card_id=result.card_id,
                                        embedding=result.embedding,
                                        embedding_type=result.embedding_type
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to store embedding for card {card.id}: {e}")
                                    failed_count += 1
                            else:
                                logger.error(f"Failed to generate embedding for card {card.id}: {result.error_message}")
                                failed_count += 1
                        
                        generated_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing card {card.id}: {e}")
                        failed_count += 1
            
            logger.info(f"Generated embeddings for {generated_count} cards, {failed_count} failed")
            return {
                "message": f"Generated embeddings for {generated_count} cards",
                "generated": generated_count,
                "failed": failed_count,
                "card_ids": card_ids
            }
        
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    async def generate_embeddings_for_all_decks(self, force_regenerate: bool = False) -> Dict[str, Any]:
        """Generate embeddings for all decks"""
        try:
            embedding_manager = await self._get_embedding_manager()
            return await embedding_manager.generate_embeddings_for_all_decks(force_regenerate=force_regenerate)
        
        except Exception as e:
            logger.error(f"Error generating embeddings for all decks: {e}")
            raise
    
    async def search_similar_cards(self, request: VectorSearchRequest) -> List[Dict[str, Any]]:
        """Search for similar cards using vector similarity"""
        try:
            embedding_manager = await self._get_embedding_manager()
            
            # Use the embedding processor's search functionality
            results = await embedding_manager.search_similar_cards(
                query_text=request.query_text,
                embedding_type=request.embedding_type,
                top_k=request.top_k,
                deck_name=request.deck_name,
                similarity_threshold=0.5  # Default threshold
            )
            
            # Add distance field for compatibility
            for result in results:
                result["distance"] = 1.0 - result["similarity_score"]
            
            return results
        
        except Exception as e:
            logger.error(f"Error searching similar cards: {e}")
            raise
    
    async def get_embedding_statistics(self) -> Dict[str, Any]:
        """Get embedding statistics"""
        try:
            embedding_manager = await self._get_embedding_manager()
            return await embedding_manager.get_embedding_statistics()
        
        except Exception as e:
            logger.error(f"Error getting embedding statistics: {e}")
            raise 
