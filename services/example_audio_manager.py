"""
Service class for managing examples and audio assets in the fragment system.

This service provides the same functionality as the legacy ExampleAudioManager
but uses the new fragment architecture with ContentFragment, FragmentAsset, and FragmentAssetRanking.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from database.manager import DatabaseManager
from models.database import AnkiCard, ContentFragment, FragmentAsset, FragmentAssetRanking
from services.fragment_manager import FragmentManager
from services.fragment_asset_manager import FragmentAssetManager
from services.template_parser import TemplateParser


class ExampleAudioManager:
    """Manager for examples and audio assets in the fragment system"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.fragment_manager = FragmentManager()
        self.asset_manager = FragmentAssetManager()
        self.template_parser = TemplateParser()
    
    def associate_audio_with_card(self, card_id: int, audio_id: int, order_index: int = None) -> int:
        """
        Associate an existing audio with a card.
        
        In the new system, this means:
        1. Get the fragment ID for this asset
        2. Update the card's example field to include the fragment token
        
        Args:
            card_id: ID of the card
            audio_id: ID of the audio asset (FragmentAsset)
            order_index: Position in the card's examples (used for insertion position)
            
        Returns:
            ID of the fragment that was added to the card
        """
        with self.db_manager.get_session() as session:
            # Get the asset and its fragment
            asset = session.get(FragmentAsset, audio_id)
            if not asset:
                raise ValueError(f"Audio asset with ID {audio_id} not found")
                
            fragment_id = asset.fragment_id
            
            # Get the card
            card = session.get(AnkiCard, card_id)
            if not card:
                raise ValueError(f"Card with ID {card_id} not found")
            
            # Update card example to include fragment token
            fragment_token = f"{{{{fragment:{fragment_id}}}}}"
            
            # Simple append if no order_index provided or no example
            if order_index is None or not card.example:
                if not card.example:
                    card.example = fragment_token
                else:
                    card.example = f"{card.example} {fragment_token}"
            else:
                # Try to insert at specific position
                # This is approximate since fragments may not align with the old order_index concept
                existing_fragments = self.template_parser.extract_fragments_from_template(card.example)
                if not existing_fragments:
                    card.example = fragment_token
                elif order_index >= len(existing_fragments):
                    card.example = f"{card.example} {fragment_token}"
                else:
                    # Insert before existing fragment at order_index
                    target_fragment_token = f"{{{{fragment:{existing_fragments[order_index]}}}}}"
                    card.example = card.example.replace(
                        target_fragment_token, 
                        f"{fragment_token} {target_fragment_token}"
                    )
            
            session.commit()
            return fragment_id
    
    def create_audio_and_associate(self, card_id: int, example_text: str, audio_blob: bytes, 
                                 tts_model: str = None, order_index: int = None) -> Tuple[int, int]:
        """
        Create a new audio example and associate it with a card.
        
        In the new system:
        1. Create or find a fragment for the text
        2. Add an asset to the fragment
        3. Update the card to include the fragment token
        
        Args:
            card_id: ID of the card
            example_text: Thai text for the audio
            audio_blob: Audio data
            tts_model: TTS model used to generate the audio
            order_index: Position in the card's examples
            
        Returns:
            Tuple of (asset_id, fragment_id)
        """
        # Determine fragment type based on text
        fragment_type = self._determine_fragment_type(example_text)
        
        # Create or find fragment
        fragment = self.fragment_manager.find_by_text_and_type(example_text, fragment_type)
        if fragment:
            fragment_id = fragment['id']
        else:
            fragment_id = self.fragment_manager.create_fragment(
                example_text,
                fragment_type,
                metadata={'source': 'example_audio_manager'}
            )
        
        # Add asset to fragment
        asset_metadata = {'tts_model': tts_model} if tts_model else {}
        asset_id = self.asset_manager.add_asset(
            fragment_id=fragment_id,
            asset_type='audio',
            asset_data=audio_blob,
            asset_metadata=asset_metadata,
            created_by='example_audio_manager',
            auto_activate=True  # Make this the active asset for the fragment
        )
        
        # Associate fragment with card
        self.associate_audio_with_card(card_id, asset_id, order_index)
        
        return asset_id, fragment_id
    
    def get_card_audio_examples(self, card_id: int) -> List[Dict]:
        """
        Get all audio examples associated with a card, ordered by order_index.
        
        In the new system:
        1. Extract fragment IDs from card example field
        2. Get fragments and their assets
        
        Args:
            card_id: ID of the card
            
        Returns:
            List of audio example dictionaries
        """
        with self.db_manager.get_session() as session:
            card = session.get(AnkiCard, card_id)
            if not card or not card.example:
                return []
            
            # Extract fragment IDs from card
            fragment_ids = self.template_parser.extract_fragments_from_template(card.example)
            if not fragment_ids:
                return []
            
            # Build list of examples with their audio assets
            result = []
            for i, fragment_id in enumerate(fragment_ids):
                fragment = self.fragment_manager.get_fragment(fragment_id)
                if not fragment:
                    continue
                
                # Get active audio assets for this fragment
                assets = self.asset_manager.get_active_assets(fragment_id, asset_type='audio')
                if not assets:
                    # Include fragment even without audio
                    result.append({
                        "fragment_id": fragment_id,
                        "audio_id": None,
                        "example_text": fragment['text'],
                        "audio_blob": None,
                        "tts_model": None,
                        "order_index": i,
                        "created_at": fragment['created_at']
                    })
                    continue
                
                # Use first active asset
                asset = assets[0]
                result.append({
                    "fragment_id": fragment_id,
                    "audio_id": asset['asset_id'],
                    "example_text": fragment['text'],
                    "audio_blob": asset['asset_data'],
                    "tts_model": asset['asset_metadata'].get('tts_model'),
                    "order_index": i,
                    "created_at": fragment['created_at']
                })
            
            return result
    
    def find_reusable_audio(self, text: str, tts_model: str = None) -> Optional[Dict]:
        """
        Find existing audio example that can be reused.
        
        Args:
            text: Thai text to search for
            tts_model: TTS model to match (optional)
            
        Returns:
            Audio example dictionary if found, None otherwise
        """
        # Find fragment with this text
        fragment = self.fragment_manager.find_by_text_and_type(text)
        if not fragment:
            return None
        
        fragment_id = fragment['id']
        
        # Find active audio assets for this fragment
        assets = self.asset_manager.get_active_assets(fragment_id, asset_type='audio')
        if not assets:
            return None
        
        # Filter by TTS model if specified
        if tts_model:
            matching_assets = [a for a in assets if a['asset_metadata'].get('tts_model') == tts_model]
            if matching_assets:
                assets = matching_assets
        
        # Use the first/active asset
        asset = assets[0]
        
        return {
            "fragment_id": fragment_id,
            "audio_id": asset['asset_id'],
            "example_text": fragment['text'],
            "audio_blob": asset['asset_data'],
            "tts_model": asset['asset_metadata'].get('tts_model'),
            "created_at": asset['created_at']
        }
    
    def search_audio_examples(self, text_patterns: List[str] = None, tts_model: str = None, 
                            limit: int = 50) -> List[Dict]:
        """
        Search for audio examples by text patterns and/or TTS model.
        
        Args:
            text_patterns: List of Thai text patterns to search for (supports partial matches)
            tts_model: TTS model to filter by (optional)
            limit: Maximum number of results to return
            
        Returns:
            List of matching audio examples with usage statistics
        """
        results = []
        
        # Search fragments by text
        if text_patterns:
            for pattern in text_patterns:
                fragments = self.fragment_manager.find_fragments(
                    text_search=pattern,
                    has_assets=True,
                    limit=limit
                )
                
                for fragment in fragments:
                    # Get active audio assets
                    assets = self.asset_manager.get_active_assets(fragment['id'], asset_type='audio')
                    if not assets:
                        continue
                    
                    # Filter by TTS model if specified
                    if tts_model:
                        assets = [a for a in assets if a['asset_metadata'].get('tts_model') == tts_model]
                        if not assets:
                            continue
                    
                    # Use the first/active asset
                    asset = assets[0]
                    
                    results.append({
                        "fragment_id": fragment['id'],
                        "audio_id": asset['asset_id'],
                        "example_text": fragment['text'],
                        "audio_blob": asset['asset_data'],
                        "tts_model": asset['asset_metadata'].get('tts_model'),
                        "usage_count": fragment.get('usage_count', 0),
                        "created_at": fragment['created_at']
                    })
                
                # Don't exceed limit across all patterns
                if len(results) >= limit:
                    break
        
        # If no text patterns or no results, return top fragments with audio assets
        if not results:
            fragments = self.fragment_manager.find_fragments(
                has_assets=True,
                limit=limit
            )
            
            for fragment in fragments:
                # Get active audio assets
                assets = self.asset_manager.get_active_assets(fragment['id'], asset_type='audio')
                if not assets:
                    continue
                
                # Filter by TTS model if specified
                if tts_model:
                    assets = [a for a in assets if a['asset_metadata'].get('tts_model') == tts_model]
                    if not assets:
                        continue
                
                # Use the first/active asset
                asset = assets[0]
                
                results.append({
                    "fragment_id": fragment['id'],
                    "audio_id": asset['asset_id'],
                    "example_text": fragment['text'],
                    "audio_blob": asset['asset_data'],
                    "tts_model": asset['asset_metadata'].get('tts_model'),
                    "usage_count": fragment.get('usage_count', 0),
                    "created_at": fragment['created_at']
                })
        
        # Sort by usage count and creation date
        results.sort(key=lambda x: (-x['usage_count'], x['created_at']), reverse=True)
        
        # Limit results
        return results[:limit]
    
    def batch_find_or_create_audio(self, thai_texts: List[str], tts_model: str = None) -> List[Dict]:
        """
        Batch operation to find existing audio or identify which texts need TTS generation.
        
        Args:
            thai_texts: List of Thai text strings
            tts_model: Preferred TTS model (optional)
            
        Returns:
            List of dictionaries with 'text', 'existing_audio' (if found), and 'needs_generation' flag
        """
        results = []
        
        for text in thai_texts:
            # Try to find existing audio
            audio = self.find_reusable_audio(text, tts_model)
            
            results.append({
                'text': text,
                'existing_audio': audio,
                'needs_generation': audio is None
            })
        
        return results
    
    def reorder_card_audio_examples(self, card_id: int, fragment_order: List[int]) -> None:
        """
        Reorder fragments in a card's example field
        
        Args:
            card_id: ID of the card
            fragment_order: List of fragment IDs in desired order
        """
        with self.db_manager.get_session() as session:
            card = session.get(AnkiCard, card_id)
            if not card or not card.example:
                return
            
            # Extract current fragments
            current_fragments = self.template_parser.extract_fragments_from_template(card.example)
            if not current_fragments:
                return
            
            # Verify all fragments exist in the current list
            if set(fragment_order) != set(current_fragments):
                raise ValueError("Fragment order list must contain exactly the same fragments as the card")
            
            # Build new example with reordered fragments
            new_example = ""
            for fragment_id in fragment_order:
                new_example += f"{{{{fragment:{fragment_id}}}}} "
            
            card.example = new_example.strip()
            session.commit()
    
    def remove_audio_from_card(self, card_id: int, fragment_id: int) -> bool:
        """
        Remove a fragment from a card's example
        
        Args:
            card_id: ID of the card
            fragment_id: ID of the fragment to remove
            
        Returns:
            True if successful, False otherwise
        """
        with self.db_manager.get_session() as session:
            card = session.get(AnkiCard, card_id)
            if not card or not card.example:
                return False
            
            # Remove fragment token from example
            fragment_token = f"{{{{fragment:{fragment_id}}}}}"
            if fragment_token in card.example:
                card.example = card.example.replace(fragment_token, "").strip()
                # Clean up multiple spaces
                while "  " in card.example:
                    card.example = card.example.replace("  ", " ")
                session.commit()
                return True
            
            return False
    
    def get_audio_usage_stats(self, fragment_id: int) -> Dict:
        """
        Get usage statistics for a fragment
        
        Args:
            fragment_id: ID of the fragment
            
        Returns:
            Dictionary with usage statistics
        """
        with self.db_manager.get_session() as session:
            fragment = self.fragment_manager.get_fragment(fragment_id)
            if not fragment:
                return {'error': f"Fragment {fragment_id} not found"}
            
            # Count cards using this fragment
            card_count = 0
            card_ids = []
            
            # This is an approximation - in real use you might want to implement a proper
            # fragment usage tracker in the database
            all_cards = session.query(AnkiCard).filter(AnkiCard.example.like(f"%fragment:{fragment_id}%")).all()
            card_count = len(all_cards)
            card_ids = [card.id for card in all_cards]
            
            return {
                'fragment_id': fragment_id,
                'example_text': fragment['text'],
                'fragment_type': fragment['fragment_type'],
                'card_count': card_count,
                'card_ids': card_ids,
                'created_at': fragment['created_at'],
                'assets_count': fragment['assets_count']
            }
    
    def get_audio_bank(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Get paginated list of audio examples for management
        
        Args:
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of audio examples with usage statistics
        """
        fragments = self.fragment_manager.find_fragments(
            has_assets=True,
            limit=limit,
            offset=offset
        )
        
        results = []
        for fragment in fragments:
            # Get active audio assets
            assets = self.asset_manager.get_active_assets(fragment['id'], asset_type='audio')
            if not assets:
                continue
            
            # Use the first/active asset
            asset = assets[0]
            
            results.append({
                "fragment_id": fragment['id'],
                "audio_id": asset['asset_id'],
                "example_text": fragment['text'],
                "audio_blob": asset['asset_data'],
                "tts_model": asset['asset_metadata'].get('tts_model'),
                "usage_count": fragment.get('usage_count', 0),
                "created_at": fragment['created_at']
            })
        
        return results
    
    def cleanup_unused_audio(self) -> int:
        """
        Delete unused audio assets (those not referenced by any card)
        
        Returns:
            Number of deleted assets
        """
        # This requires a more sophisticated approach in the fragment system
        # because fragments can be used in multiple places
        # Instead, we'll just remove assets without active rankings
        
        with self.db_manager.get_session() as session:
            # Find assets without active rankings
            from sqlalchemy.sql.expression import exists
            
            unused_asset_ids = session.query(FragmentAsset.id).filter(
                ~exists().where(
                    and_(
                        FragmentAssetRanking.asset_id == FragmentAsset.id,
                        FragmentAssetRanking.is_active == True
                    )
                )
            ).all()
            
            if not unused_asset_ids:
                return 0
                
            ids_to_delete = [id[0] for id in unused_asset_ids]
            
            # Delete assets
            deleted_count = 0
            for asset_id in ids_to_delete:
                if self.asset_manager.delete_asset(asset_id):
                    deleted_count += 1
            
            return deleted_count
    
    def _determine_fragment_type(self, text: str) -> str:
        """Determine the fragment type for given text"""
        # Simple heuristic to determine fragment type
        import re
        
        thai_pattern = re.compile(r'[\u0E00-\u0E7F]')
        has_thai = bool(thai_pattern.search(text))
        
        if has_thai:
            words = text.split()
            if len(words) == 1:
                return 'thai_word'
            else:
                return 'thai_phrase'
        else:
            return 'english_explanation' 
