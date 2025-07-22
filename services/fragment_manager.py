"""
Fragment Management Service
Handles CRUD operations for content fragments
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from database.manager import DatabaseManager
from models.database import ContentFragment, FragmentAsset, FragmentAssetRanking


class FragmentManager:
    """Service for managing content fragments"""
    
    # Supported fragment types
    FRAGMENT_TYPES = {
        'thai_word': 'Single Thai word',
        'thai_phrase': 'Thai phrase or compound',
        'english_explanation': 'English explanation or translation',
        'romanization': 'Romanized pronunciation',
        'example_sentence': 'Complete example sentence',
        'idiom': 'Idiomatic expression',
        'grammar_note': 'Grammar explanation'
    }
    
    def __init__(self):
        self.db_manager = DatabaseManager()
    
    def create_fragment(self, text: str, fragment_type: str, metadata: Dict = None) -> int:
        """Create a new content fragment"""
        if fragment_type not in self.FRAGMENT_TYPES:
            raise ValueError(f"Invalid fragment type: {fragment_type}. Must be one of: {list(self.FRAGMENT_TYPES.keys())}")
        
        if not text or not text.strip():
            raise ValueError("Fragment text cannot be empty")
        
        with self.db_manager.get_session() as session:
            fragment = ContentFragment(
                text=text.strip(),
                fragment_type=fragment_type,
                fragment_metadata=metadata or {}
            )
            session.add(fragment)
            session.commit()
            return fragment.id
    
    def get_fragment(self, fragment_id: int) -> Optional[Dict]:
        """Get a fragment by ID"""
        with self.db_manager.get_session() as session:
            fragment = session.get(ContentFragment, fragment_id)
            if not fragment:
                return None
            
            return {
                'id': fragment.id,
                'text': fragment.text,
                'fragment_type': fragment.fragment_type,
                'fragment_metadata': fragment.fragment_metadata,
                'created_at': fragment.created_at,
                'updated_at': fragment.updated_at,
                'assets_count': len(fragment.assets),
                'usage_count': 0  # TODO: Implement usage tracking when needed
            }
    
    def update_fragment(self, fragment_id: int, text: str = None, fragment_type: str = None, metadata: Dict = None) -> bool:
        """Update an existing fragment"""
        with self.db_manager.get_session() as session:
            fragment = session.get(ContentFragment, fragment_id)
            if not fragment:
                return False
            
            if text is not None:
                fragment.text = text.strip()
            if fragment_type is not None:
                if fragment_type not in self.FRAGMENT_TYPES:
                    raise ValueError(f"Invalid fragment type: {fragment_type}")
                fragment.fragment_type = fragment_type
            if metadata is not None:
                fragment.fragment_metadata = metadata
                
            fragment.updated_at = datetime.utcnow()
            session.commit()
            return True
    
    def delete_fragment(self, fragment_id: int) -> bool:
        """Delete a fragment"""
        with self.db_manager.get_session() as session:
            fragment = session.get(ContentFragment, fragment_id)
            if not fragment:
                return False
            
            # TODO: Add check for fragment usage when usage tracking is implemented
            # if fragment.card_usages:
            #     raise ValueError(f"Cannot delete fragment {fragment_id}: it's being used by {len(fragment.card_usages)} cards")
            
            session.delete(fragment)
            session.commit()
            return True
    
    def find_fragments(self,
                       text_search: str = None,
                       fragment_type: str = None,
                       has_assets: bool = None,
                       limit: int = 50,
                       offset: int = 0) -> List[Dict]:
        """Find fragments matching criteria"""
        with self.db_manager.get_session() as session:
            query = session.query(ContentFragment)
            
            if text_search:
                # Use LIKE for case-insensitive text search
                query = query.filter(ContentFragment.text.ilike(f'%{text_search}%'))
            
            if fragment_type:
                query = query.filter(ContentFragment.fragment_type == fragment_type)
            
            if has_assets is not None:
                if has_assets:
                    query = query.filter(ContentFragment.assets.any())
                else:
                    query = query.filter(~ContentFragment.assets.any())
            
            query = query.offset(offset).limit(limit)
            fragments = query.all()
            
            return [{
                'id': fragment.id,
                'text': fragment.text,
                'fragment_type': fragment.fragment_type,
                'fragment_metadata': fragment.fragment_metadata,
                'created_at': fragment.created_at,
                'updated_at': fragment.updated_at,
                'assets_count': len(fragment.assets),
                'usage_count': 0  # TODO: Implement usage tracking when needed
            } for fragment in fragments]
    
    def find_by_text_and_type(self, text: str, fragment_type: str = None) -> Optional[Dict]:
        """Find a fragment by exact text match and optional type"""
        with self.db_manager.get_session() as session:
            query = session.query(ContentFragment).filter(ContentFragment.text == text.strip())
            
            if fragment_type:
                query = query.filter(ContentFragment.fragment_type == fragment_type)
            
            fragment = query.first()
            if not fragment:
                return None
            
            return {
                'id': fragment.id,
                'text': fragment.text,
                'fragment_type': fragment.fragment_type,
                'fragment_metadata': fragment.fragment_metadata,
                'created_at': fragment.created_at,
                'updated_at': fragment.updated_at,
                'assets_count': len(fragment.assets),
                'usage_count': 0  # TODO: Implement usage tracking when needed
            }
    
    def get_fragment_types(self) -> Dict[str, str]:
        """Get all supported fragment types"""
        return self.FRAGMENT_TYPES.copy()
    
    def get_fragment_statistics(self) -> Dict[str, Any]:
        """Get statistics about fragments"""
        with self.db_manager.get_session() as session:
            total_fragments = session.query(ContentFragment).count()
            
            # Count by type
            type_counts = {}
            for fragment_type in self.FRAGMENT_TYPES.keys():
                count = session.query(ContentFragment).filter(
                    ContentFragment.fragment_type == fragment_type
                ).count()
                type_counts[fragment_type] = count
            
            # Count fragments with assets
            fragments_with_assets = session.query(ContentFragment).filter(
                ContentFragment.assets.any()
            ).count()
            
            # Count fragments in use - TODO: Implement when usage tracking is available
            fragments_in_use = 0
            
            return {
                'total_fragments': total_fragments,
                'type_counts': type_counts,
                'fragments_with_assets': fragments_with_assets,
                'fragments_in_use': fragments_in_use
            } 
