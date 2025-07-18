"""
Service class for managing many-to-many relationship between AnkiCard and ExampleAudio.

This service provides methods to:
1. Associate existing audio examples with cards
2. Create new audio examples and associate them with cards
3. Reorder audio examples within a card
4. Find reusable audio examples
5. Manage the audio example "bank"
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from database.manager import DatabaseManager
from models.database import AnkiCard, ExampleAudio, CardExampleAudioAssociation


class ExampleAudioManager:
    """Manager for many-to-many relationship between cards and example audios"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
    
    def associate_audio_with_card(self, card_id: int, audio_id: int, order_index: int = None) -> int:
        """
        Associate an existing audio example with a card.
        
        Args:
            card_id: ID of the card
            audio_id: ID of the audio example
            order_index: Position in the card's audio list (auto-calculated if None)
            
        Returns:
            ID of the association record
        """
        with self.db_manager.get_session() as session:
            # Check if association already exists
            existing = session.query(CardExampleAudioAssociation).filter_by(
                card_id=card_id, 
                example_audio_id=audio_id
            ).first()
            
            if existing:
                # Update order_index if provided
                if order_index is not None:
                    existing.order_index = order_index
                    session.commit()
                return existing.id
            
            # Calculate order_index if not provided
            if order_index is None:
                max_order = session.query(func.max(CardExampleAudioAssociation.order_index))\
                    .filter_by(card_id=card_id).scalar() or -1
                order_index = max_order + 1
            
            # Create new association
            association = CardExampleAudioAssociation(
                card_id=card_id,
                example_audio_id=audio_id,
                order_index=order_index
            )
            session.add(association)
            session.commit()
            return association.id
    
    def create_audio_and_associate(self, card_id: int, example_text: str, audio_blob: bytes, 
                                 tts_model: str = None, order_index: int = None) -> Tuple[int, int]:
        """
        Create a new audio example and associate it with a card.
        
        Args:
            card_id: ID of the card
            example_text: Thai text for the audio
            audio_blob: Audio data
            tts_model: TTS model used to generate the audio
            order_index: Position in the card's audio list
            
        Returns:
            Tuple of (audio_id, association_id)
        """
        with self.db_manager.get_session() as session:
            # Check if identical audio already exists
            existing_audio = session.query(ExampleAudio).filter_by(
                example_text=example_text,
                tts_model=tts_model
            ).first()
            
            if existing_audio:
                # Reuse existing audio
                audio_id = existing_audio.id
            else:
                # Create new audio
                audio = ExampleAudio(
                    example_text=example_text,
                    audio_blob=audio_blob,
                    tts_model=tts_model
                )
                session.add(audio)
                session.flush()  # Get the ID
                audio_id = audio.id
            
            # Associate with card
            association_id = self.associate_audio_with_card(card_id, audio_id, order_index)
            session.commit()
            
            return audio_id, association_id
    
    def get_card_audio_examples(self, card_id: int) -> List[Dict]:
        """
        Get all audio examples associated with a card, ordered by order_index.
        
        Args:
            card_id: ID of the card
            
        Returns:
            List of audio example dictionaries
        """
        with self.db_manager.get_session() as session:
            results = session.query(ExampleAudio, CardExampleAudioAssociation)\
                .join(CardExampleAudioAssociation)\
                .filter(CardExampleAudioAssociation.card_id == card_id)\
                .order_by(CardExampleAudioAssociation.order_index)\
                .all()
            
            return [
                {
                    "audio_id": audio.id,
                    "association_id": assoc.id,
                    "example_text": audio.example_text,
                    "audio_blob": audio.audio_blob,
                    "tts_model": audio.tts_model,
                    "order_index": assoc.order_index,
                    "created_at": audio.created_at
                }
                for audio, assoc in results
            ]
    
    def find_reusable_audio(self, text: str, tts_model: str = None) -> Optional[Dict]:
        """
        Find existing audio example that can be reused.
        
        Args:
            text: Thai text to search for
            tts_model: TTS model to match (optional)
            
        Returns:
            Audio example dictionary if found, None otherwise
        """
        with self.db_manager.get_session() as session:
            query = session.query(ExampleAudio).filter_by(example_text=text)
            
            if tts_model:
                query = query.filter_by(tts_model=tts_model)
            
            audio = query.first()
            
            if audio:
                return {
                    "audio_id": audio.id,
                    "example_text": audio.example_text,
                    "audio_blob": audio.audio_blob,
                    "tts_model": audio.tts_model,
                    "created_at": audio.created_at
                }
            
            return None
    
    def search_audio_examples(self, text_patterns: List[str] = None, tts_model: str = None, 
                            limit: int = 50) -> List[Dict]:
        """
        Search for audio examples by text patterns and/or TTS model.
        
        This method is useful for finding existing audio before making TTS API calls.
        
        Args:
            text_patterns: List of Thai text patterns to search for (supports partial matches)
            tts_model: TTS model to filter by (optional)
            limit: Maximum number of results to return
            
        Returns:
            List of matching audio examples with usage statistics
        """
        with self.db_manager.get_session() as session:
            query = session.query(
                ExampleAudio,
                func.count(CardExampleAudioAssociation.id).label('usage_count')
            ).outerjoin(CardExampleAudioAssociation).group_by(ExampleAudio.id)
            
            # Apply text pattern filters
            if text_patterns:
                text_conditions = []
                for pattern in text_patterns:
                    text_conditions.append(ExampleAudio.example_text.like(f'%{pattern}%'))
                query = query.filter(or_(*text_conditions))
            
            # Apply TTS model filter
            if tts_model:
                query = query.filter(ExampleAudio.tts_model == tts_model)
            
            # Order by usage count (most used first) and creation date
            query = query.order_by(
                func.count(CardExampleAudioAssociation.id).desc(),
                ExampleAudio.created_at.desc()
            ).limit(limit)
            
            results = query.all()
            
            return [
                {
                    "audio_id": audio.id,
                    "example_text": audio.example_text,
                    "audio_blob": audio.audio_blob,
                    "tts_model": audio.tts_model,
                    "usage_count": usage_count,
                    "created_at": audio.created_at
                }
                for audio, usage_count in results
            ]
    
    def batch_find_or_create_audio(self, thai_texts: List[str], tts_model: str = None) -> List[Dict]:
        """
        Batch operation to find existing audio or identify which texts need TTS generation.
        
        This is optimized for the use case where we have multiple Thai texts and want to
        avoid unnecessary TTS API calls by reusing existing audio.
        
        Args:
            thai_texts: List of Thai text strings
            tts_model: Preferred TTS model (optional)
            
        Returns:
            List of dictionaries with 'text', 'existing_audio' (if found), and 'needs_generation' flag
        """
        with self.db_manager.get_session() as session:
            # Get all existing audio for these texts
            existing_audios = session.query(ExampleAudio).filter(
                ExampleAudio.example_text.in_(thai_texts)
            )
            
            if tts_model:
                existing_audios = existing_audios.filter_by(tts_model=tts_model)
            
            existing_audios = existing_audios.all()
            
            # Create lookup map
            audio_lookup = {audio.example_text: audio for audio in existing_audios}
            
            # Build result list
            results = []
            for text in thai_texts:
                existing_audio = audio_lookup.get(text)
                
                result = {
                    "text": text,
                    "needs_generation": existing_audio is None,
                    "existing_audio": None
                }
                
                if existing_audio:
                    result["existing_audio"] = {
                        "audio_id": existing_audio.id,
                        "example_text": existing_audio.example_text,
                        "audio_blob": existing_audio.audio_blob,
                        "tts_model": existing_audio.tts_model,
                        "created_at": existing_audio.created_at
                    }
                
                results.append(result)
            
            return results
    
    def reorder_card_audio_examples(self, card_id: int, audio_order: List[int]) -> None:
        """
        Reorder audio examples for a card.
        
        Args:
            card_id: ID of the card
            audio_order: List of audio IDs in desired order
        """
        with self.db_manager.get_session() as session:
            for i, audio_id in enumerate(audio_order):
                session.query(CardExampleAudioAssociation)\
                    .filter_by(card_id=card_id, example_audio_id=audio_id)\
                    .update({"order_index": i})
            session.commit()
    
    def remove_audio_from_card(self, card_id: int, audio_id: int) -> bool:
        """
        Remove association between a card and an audio example.
        
        Args:
            card_id: ID of the card
            audio_id: ID of the audio example
            
        Returns:
            True if association was removed, False if not found
        """
        with self.db_manager.get_session() as session:
            association = session.query(CardExampleAudioAssociation).filter_by(
                card_id=card_id, 
                example_audio_id=audio_id
            ).first()
            
            if association:
                session.delete(association)
                session.commit()
                return True
            
            return False
    
    def get_audio_usage_stats(self, audio_id: int) -> Dict:
        """
        Get usage statistics for an audio example.
        
        Args:
            audio_id: ID of the audio example
            
        Returns:
            Dictionary with usage statistics
        """
        with self.db_manager.get_session() as session:
            audio = session.query(ExampleAudio).get(audio_id)
            if not audio:
                return None
            
            # Count how many cards use this audio
            card_count = session.query(CardExampleAudioAssociation)\
                .filter_by(example_audio_id=audio_id)\
                .count()
            
            # Get list of card IDs using this audio
            card_ids = session.query(CardExampleAudioAssociation.card_id)\
                .filter_by(example_audio_id=audio_id)\
                .all()
            
            return {
                "audio_id": audio_id,
                "example_text": audio.example_text,
                "tts_model": audio.tts_model,
                "used_by_cards": card_count,
                "card_ids": [card_id[0] for card_id in card_ids],
                "created_at": audio.created_at
            }
    
    def get_audio_bank(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Get all audio examples in the "bank" with usage statistics.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of audio examples with usage stats
        """
        with self.db_manager.get_session() as session:
            # Get audio examples with usage counts
            results = session.query(
                ExampleAudio,
                func.count(CardExampleAudioAssociation.id).label('usage_count')
            ).outerjoin(CardExampleAudioAssociation)\
            .group_by(ExampleAudio.id)\
            .order_by(ExampleAudio.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()
            
            return [
                {
                    "audio_id": audio.id,
                    "example_text": audio.example_text,
                    "tts_model": audio.tts_model,
                    "usage_count": usage_count,
                    "created_at": audio.created_at
                }
                for audio, usage_count in results
            ]
    
    def cleanup_unused_audio(self) -> int:
        """
        Remove audio examples that are not associated with any cards.
        
        Returns:
            Number of audio examples removed
        """
        with self.db_manager.get_session() as session:
            # Find audio examples with no associations
            unused_audio_ids = session.query(ExampleAudio.id)\
                .outerjoin(CardExampleAudioAssociation)\
                .filter(CardExampleAudioAssociation.example_audio_id.is_(None))\
                .all()
            
            if not unused_audio_ids:
                return 0
            
            # Delete unused audio examples
            ids_to_delete = [audio_id[0] for audio_id in unused_audio_ids]
            deleted_count = session.query(ExampleAudio)\
                .filter(ExampleAudio.id.in_(ids_to_delete))\
                .delete(synchronize_session=False)
            
            session.commit()
            return deleted_count 
