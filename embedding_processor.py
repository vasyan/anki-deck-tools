#!/usr/bin/env python3
"""
Embedding Processing System for Anki Cards
==========================================

This module handles:
1. Loading and managing sentence transformer models
2. Generating embeddings for Anki card content
3. Batch processing for efficiency
4. Vector similarity search
5. Progress tracking and caching

Uses sentence-transformers for local embedding generation.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import hashlib
import re

import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util
from sqlalchemy.orm import Session
from tqdm import tqdm

# Import from current project structure
from main import DatabaseManager, AnkiCard, VectorEmbedding
from config import settings

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation"""
    model_name: str = settings.embedding_model
    batch_size: int = settings.embedding_batch_size
    max_seq_length: int = settings.embedding_max_seq_length
    normalize_embeddings: bool = True
    device: str = settings.embedding_device
    cache_dir: str = settings.embedding_cache_dir
    embedding_types: List[str] = None
    
    def __post_init__(self):
        if self.embedding_types is None:
            self.embedding_types = ["front", "back", "combined"]

@dataclass
class EmbeddingResult:
    """Result of embedding generation"""
    card_id: int
    embedding_type: str
    embedding: List[float]
    text_content: str
    processing_time: float
    success: bool
    error_message: Optional[str] = None

class TextProcessor:
    """Handles text preprocessing for embedding generation"""
    
    @staticmethod
    def clean_html(text: str) -> str:
        """Remove HTML tags and clean text"""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove special characters that might interfere
        text = re.sub(r'[^\w\s\-.,!?;:]', '', text)
        
        return text
    
    @staticmethod
    def extract_text_content(card: AnkiCard, embedding_type: str) -> str:
        """Extract and combine text content based on embedding type"""
        front_text = TextProcessor.clean_html(card.front_text or "")
        back_text = TextProcessor.clean_html(card.back_text or "")
        
        if embedding_type == "front":
            return front_text
        elif embedding_type == "back":
            return back_text
        elif embedding_type == "combined":
            # Combine front and back with separator
            combined = f"{front_text} [SEP] {back_text}".strip()
            return combined if combined != "[SEP]" else front_text or back_text
        else:
            raise ValueError(f"Unknown embedding type: {embedding_type}")
    
    @staticmethod
    def create_content_hash(text: str) -> str:
        """Create hash of text content for caching"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

class EmbeddingGenerator:
    """Main class for generating embeddings using sentence transformers"""
    
    def __init__(self, config: EmbeddingConfig = None):
        self.config = config or EmbeddingConfig()
        self.model: Optional[SentenceTransformer] = None
        self.device = self._get_device()
        self.embedding_cache: Dict[str, List[float]] = {}
        
        logger.info(f"Initialized EmbeddingGenerator with model: {self.config.model_name}")
        logger.info(f"Using device: {self.device}")
    
    def _get_device(self) -> str:
        """Determine the best device for inference"""
        if self.config.device == "auto":
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return "mps"  # Apple Silicon
            else:
                return "cpu"
        return self.config.device
    
    async def load_model(self) -> bool:
        """Load the sentence transformer model"""
        try:
            logger.info(f"Loading model: {self.config.model_name}")
            
            # Create cache directory
            Path(self.config.cache_dir).mkdir(exist_ok=True)
            
            # Load model in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                self.model = await loop.run_in_executor(
                    executor,
                    self._load_model_sync
                )
            
            logger.info(f"Model loaded successfully. Embedding dimension: {self.model.get_sentence_embedding_dimension()}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
    
    def _load_model_sync(self) -> SentenceTransformer:
        """Synchronous model loading"""
        model = SentenceTransformer(
            self.config.model_name,
            cache_folder=self.config.cache_dir,
            device=self.device
        )
        
        # Set max sequence length
        model.max_seq_length = self.config.max_seq_length
        
        return model
    
    def _generate_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a batch of texts (synchronous)"""
        if not self.model:
            raise ValueError("Model not loaded. Call load_model() first.")
        
        # Filter out empty texts
        valid_texts = [text if text.strip() else "empty" for text in texts]
        
        # Generate embeddings
        embeddings = self.model.encode(
            valid_texts,
            batch_size=self.config.batch_size,
            normalize_embeddings=self.config.normalize_embeddings,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        
        return embeddings
    
    async def generate_embedding_single(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if not text or not text.strip():
            # Return zero vector for empty text
            dim = self.model.get_sentence_embedding_dimension() if self.model else 384
            return [0.0] * dim
        
        # Check cache first
        text_hash = TextProcessor.create_content_hash(text)
        if text_hash in self.embedding_cache:
            return self.embedding_cache[text_hash]
        
        # Generate embedding
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            embeddings = await loop.run_in_executor(
                executor,
                self._generate_embeddings_batch,
                [text]
            )
        
        embedding = embeddings[0].tolist()
        
        # Cache result
        self.embedding_cache[text_hash] = embedding
        
        return embedding
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if not texts:
            return []
        
        # Split into batches
        all_embeddings = []
        
        for i in range(0, len(texts), self.config.batch_size):
            batch_texts = texts[i:i + self.config.batch_size]
            
            # Generate embeddings for batch
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                batch_embeddings = await loop.run_in_executor(
                    executor,
                    self._generate_embeddings_batch,
                    batch_texts
                )
            
            # Convert to list and add to results
            for embedding in batch_embeddings:
                all_embeddings.append(embedding.tolist())
        
        return all_embeddings
    
    async def process_card(self, card: AnkiCard, embedding_type: str) -> EmbeddingResult:
        """Process a single card to generate embeddings"""
        start_time = time.time()
        
        try:
            # Extract text content
            text_content = TextProcessor.extract_text_content(card, embedding_type)
            
            if not text_content.strip():
                logger.warning(f"Empty content for card {card.id}, type {embedding_type}")
                # Return zero embedding for empty content
                dim = self.model.get_sentence_embedding_dimension() if self.model else 384
                embedding = [0.0] * dim
            else:
                # Generate embedding
                embedding = await self.generate_embedding_single(text_content)
            
            processing_time = time.time() - start_time
            
            return EmbeddingResult(
                card_id=card.id,
                embedding_type=embedding_type,
                embedding=embedding,
                text_content=text_content,
                processing_time=processing_time,
                success=True
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Error processing card {card.id}, type {embedding_type}: {e}"
            logger.error(error_msg)
            
            return EmbeddingResult(
                card_id=card.id,
                embedding_type=embedding_type,
                embedding=[],
                text_content="",
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )

class EmbeddingManager:
    """High-level manager for embedding operations"""
    
    def __init__(self, config: EmbeddingConfig = None):
        self.config = config or EmbeddingConfig()
        self.generator = EmbeddingGenerator(self.config)
        self.db_manager = DatabaseManager()
        
    async def initialize(self) -> bool:
        """Initialize the embedding manager"""
        success = await self.generator.load_model()
        if success:
            logger.info("EmbeddingManager initialized successfully")
        else:
            logger.error("Failed to initialize EmbeddingManager")
        return success
    
    async def generate_embeddings_for_deck(self, deck_name: str, 
                                         embedding_types: List[str] = None,
                                         force_regenerate: bool = False) -> Dict[str, Any]:
        """Generate embeddings for all cards in a deck"""
        if embedding_types is None:
            embedding_types = self.config.embedding_types
        
        logger.info(f"Starting embedding generation for deck: {deck_name}")
        logger.info(f"Embedding types: {embedding_types}")
        
        # Get cards from deck - fix: make this sync since get_cards_by_deck is sync
        cards = await self.db_manager.get_cards_by_deck(deck_name)
        
        if not cards:
            return {
                "message": f"No cards found in deck '{deck_name}'",
                "processed_count": 0,
                "results": {}
            }
        
        total_tasks = len(cards) * len(embedding_types)
        logger.info(f"Processing {len(cards)} cards with {len(embedding_types)} embedding types each")
        logger.info(f"Total tasks: {total_tasks}")
        
        results = {
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "total_processing_time": 0,
            "details": []
        }
        
        # Process cards with progress tracking
        with tqdm(total=total_tasks, desc=f"Processing {deck_name}") as pbar:
            for card in cards:
                for embedding_type in embedding_types:
                    try:
                        # Check if embedding already exists (simple approach - no regeneration)
                        if not force_regenerate:
                            existing = self._get_existing_embedding(card.id, embedding_type)
                            if existing:
                                results["skipped"] += 1
                                pbar.update(1)
                                continue
                        
                        # Generate embedding
                        result = await self.generator.process_card(card, embedding_type)
                        results["total_processing_time"] += result.processing_time
                        
                        if result.success:
                            try:
                                # Store in database (sequential to avoid lock issues)
                                await self.db_manager.store_vector_embedding(
                                    card_id=result.card_id,
                                    embedding=result.embedding,
                                    embedding_type=result.embedding_type
                                )
                                results["successful"] += 1
                            except Exception as e:
                                results["failed"] += 1
                                logger.error(f"Failed to store embedding for card {card.id}, type {embedding_type}: {e}")
                        else:
                            results["failed"] += 1
                            # Simple error handling - just log and continue
                            logger.error(f"Failed task: card {card.id}, type {embedding_type} - {result.error_message}")
                        
                        results["details"].append({
                            "card_id": result.card_id,
                            "embedding_type": result.embedding_type,
                            "success": result.success,
                            "processing_time": result.processing_time,
                            "text_length": len(result.text_content),
                            "error": result.error_message
                        })
                        
                    except Exception as e:
                        # Simple error handling - throw with task information
                        error_msg = f"Failed task: card {card.id}, embedding_type {embedding_type}, deck {deck_name}: {e}"
                        logger.error(error_msg)
                        raise Exception(error_msg) from e
                    
                    pbar.update(1)
        
        logger.info(f"Embedding generation completed for deck '{deck_name}'")
        logger.info(f"Results: {results['successful']} successful, {results['failed']} failed, {results['skipped']} skipped")
        
        return {
            "message": f"Embedding generation completed for deck '{deck_name}'",
            "deck_name": deck_name,
            "cards_processed": len(cards),
            "embedding_types": embedding_types,
            "results": results
        }
    
    async def generate_embeddings_for_all_decks(self, 
                                              embedding_types: List[str] = None,
                                              force_regenerate: bool = False) -> Dict[str, Any]:
        """Generate embeddings for all cards in all decks"""
        logger.info("Starting embedding generation for all decks")
        
        # Get all unique deck names
        with self.db_manager.get_session() as session:
            deck_names = [deck[0] for deck in session.query(AnkiCard.deck_name).distinct().all()]
        
        if not deck_names:
            return {
                "message": "No decks found in database",
                "processed_decks": 0,
                "results": {}
            }
        
        logger.info(f"Found {len(deck_names)} decks: {deck_names}")
        
        all_results = {}
        total_successful = 0
        total_failed = 0
        total_skipped = 0
        total_processing_time = 0
        
        for deck_name in deck_names:
            try:
                deck_result = await self.generate_embeddings_for_deck(
                    deck_name, embedding_types, force_regenerate
                )
                all_results[deck_name] = deck_result
                
                # Aggregate results
                if "results" in deck_result:
                    total_successful += deck_result["results"]["successful"]
                    total_failed += deck_result["results"]["failed"]
                    total_skipped += deck_result["results"]["skipped"]
                    total_processing_time += deck_result["results"]["total_processing_time"]
                
            except Exception as e:
                # Simple error handling - throw with deck information
                error_msg = f"Failed to process deck '{deck_name}': {e}"
                logger.error(error_msg)
                raise Exception(error_msg) from e
        
        return {
            "message": f"Embedding generation completed for all decks",
            "processed_decks": len(deck_names),
            "total_results": {
                "successful": total_successful,
                "failed": total_failed,
                "skipped": total_skipped,
                "total_processing_time": total_processing_time
            },
            "deck_results": all_results
        }
    
    def _get_existing_embedding(self, card_id: int, embedding_type: str) -> Optional[VectorEmbedding]:
        """Check if embedding already exists for card (sync method)"""
        with self.db_manager.get_session() as session:
            return session.query(VectorEmbedding).filter_by(
                card_id=card_id,
                embedding_type=embedding_type
            ).first()
    
    async def search_similar_cards(self, 
                                 query_text: str,
                                 embedding_type: str = "combined",
                                 top_k: int = 10,
                                 deck_name: Optional[str] = None,
                                 similarity_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Search for similar cards using semantic similarity"""
        logger.info(f"Searching for similar cards: '{query_text}' (top_k={top_k})")
        
        try:
            # Generate embedding for query
            query_embedding = await self.generator.generate_embedding_single(query_text)
            
            # Get all embeddings from database
            with self.db_manager.get_session() as session:
                query = session.query(VectorEmbedding, AnkiCard).join(
                    AnkiCard, VectorEmbedding.card_id == AnkiCard.id
                ).filter(VectorEmbedding.embedding_type == embedding_type)
                
                if deck_name:
                    query = query.filter(AnkiCard.deck_name == deck_name)
                
                embeddings_data = query.all()
            
            if not embeddings_data:
                return []
            
            # Calculate similarities
            similarities = []
            
            for embedding_obj, card in embeddings_data:
                try:
                    # Handle both string and list formats for backward compatibility
                    if isinstance(embedding_obj.vector_data, str):
                        stored_embedding = json.loads(embedding_obj.vector_data)
                    else:
                        stored_embedding = embedding_obj.vector_data
                    
                    # Calculate cosine similarity
                    similarity = util.cos_sim(query_embedding, stored_embedding).item()
                    
                    if similarity >= similarity_threshold:
                        similarities.append({
                            "card_id": card.id,
                            "anki_note_id": card.anki_note_id,
                            "deck_name": card.deck_name,
                            "front_text": card.front_text,
                            "back_text": card.back_text,
                            "tags": json.loads(card.tags) if card.tags else [],
                            "similarity_score": float(similarity),
                            "embedding_type": embedding_type
                        })
                        
                except Exception as e:
                    logger.warning(f"Error processing embedding for card {card.id}: {e}")
                    continue
            
            # Sort by similarity and return top_k
            similarities.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            logger.info(f"Found {len(similarities)} similar cards (threshold: {similarity_threshold})")
            
            return similarities[:top_k]
        
        except Exception as e:
            error_msg = f"Failed to search similar cards for query '{query_text}': {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
    
    async def get_embedding_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored embeddings"""
        try:
            with self.db_manager.get_session() as session:
                # Count embeddings by type
                embedding_counts = {}
                for embedding_type in self.config.embedding_types:
                    count = session.query(VectorEmbedding).filter_by(
                        embedding_type=embedding_type
                    ).count()
                    embedding_counts[embedding_type] = count
                
                # Count total cards
                total_cards = session.query(AnkiCard).count()
                
                # Count cards with embeddings
                cards_with_embeddings = session.query(VectorEmbedding.card_id).distinct().count()
                
                # Get deck statistics
                deck_stats = {}
                deck_names = [deck[0] for deck in session.query(AnkiCard.deck_name).distinct().all()]
                
                for deck_name in deck_names:
                    cards_in_deck = session.query(AnkiCard).filter_by(deck_name=deck_name).count()
                    embeddings_in_deck = session.query(VectorEmbedding).join(
                        AnkiCard, VectorEmbedding.card_id == AnkiCard.id
                    ).filter(AnkiCard.deck_name == deck_name).count()
                    
                    deck_stats[deck_name] = {
                        "total_cards": cards_in_deck,
                        "total_embeddings": embeddings_in_deck,
                        "completion_rate": embeddings_in_deck / (cards_in_deck * len(self.config.embedding_types)) if cards_in_deck > 0 else 0
                    }
            
            return {
                "total_cards": total_cards,
                "cards_with_embeddings": cards_with_embeddings,
                "completion_rate": cards_with_embeddings / total_cards if total_cards > 0 else 0,
                "embedding_counts_by_type": embedding_counts,
                "deck_statistics": deck_stats,
                "model_info": {
                    "model_name": self.config.model_name,
                    "embedding_dimension": self.generator.model.get_sentence_embedding_dimension() if self.generator.model else None,
                    "device": self.generator.device
                }
            }
        except Exception as e:
            error_msg = f"Failed to get embedding statistics: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

# CLI Interface for embedding operations
async def main():
    """Main CLI function for embedding operations"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Anki Vector Embedding Generator")
    parser.add_argument("--deck", type=str, help="Generate embeddings for specific deck")
    parser.add_argument("--all-decks", action="store_true", help="Generate embeddings for all decks")
    parser.add_argument("--search", type=str, help="Search for similar cards")
    parser.add_argument("--embedding-type", type=str, default="combined", 
                       choices=["front", "back", "combined"], help="Embedding type for search")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results for search")
    parser.add_argument("--stats", action="store_true", help="Show embedding statistics")
    parser.add_argument("--force", action="store_true", help="Force regenerate existing embeddings")
    parser.add_argument("--model", type=str, default=settings.embedding_model, help="Sentence transformer model")
    parser.add_argument("--batch-size", type=int, default=settings.embedding_batch_size, help="Batch size for processing")
    
    args = parser.parse_args()
    
    # Create configuration
    config = EmbeddingConfig(
        model_name=args.model,
        batch_size=args.batch_size
    )
    
    # Initialize embedding manager
    manager = EmbeddingManager(config)
    
    if not await manager.initialize():
        print("Failed to initialize embedding manager")
        return
    
    try:
        if args.deck:
            result = await manager.generate_embeddings_for_deck(args.deck, force_regenerate=args.force)
            print(json.dumps(result, indent=2))
            
        elif args.all_decks:
            result = await manager.generate_embeddings_for_all_decks(force_regenerate=args.force)
            print(json.dumps(result, indent=2))
            
        elif args.search:
            results = await manager.search_similar_cards(
                query_text=args.search,
                embedding_type=args.embedding_type,
                top_k=args.top_k
            )
            
            if results:
                print(f"\nFound {len(results)} similar cards:")
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. Card {result['card_id']} (Similarity: {result['similarity_score']:.3f})")
                    print(f"   Deck: {result['deck_name']}")
                    print(f"   Front: {result['front_text'][:100]}...")
                    if result['back_text']:
                        print(f"   Back: {result['back_text'][:100]}...")
            else:
                print("No similar cards found")
        
        elif args.stats:
            stats = await manager.get_embedding_statistics()
            print(json.dumps(stats, indent=2))
            
        else:
            parser.print_help()
    
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 
