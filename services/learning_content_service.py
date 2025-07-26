"""
Learning Content Service
CRUD operations and management for abstract learning content
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from database.manager import DatabaseManager
from models.database import LearningContent, AnkiCard
from sqlalchemy import text, and_, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class LearningContentService:
    """Service for managing learning content abstractions"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
    
    def create_content(self, 
                      title: str,
                      content_type: str,
                      language: str = 'thai',
                      front_template: Optional[str] = None,
                      back_template: Optional[str] = None,
                      example_template: Optional[str] = None,
                      difficulty_level: Optional[int] = None,
                      tags: Optional[List[str]] = None,
                      content_metadata: Optional[Dict] = None) -> int:
        """
        Create a new learning content record
        
        Returns:
            ID of the created learning content
        """
        with self.db_manager.get_session() as session:
            learning_content = LearningContent(
                title=title,
                content_type=content_type,
                language=language,
                front_template=front_template,
                back_template=back_template,
                example_template=example_template,
                difficulty_level=difficulty_level,
                tags=tags or [],
                content_metadata=content_metadata or {}
            )
            
            session.add(learning_content)
            session.flush()
            session.commit()
            
            logger.info(f"Created learning content #{learning_content.id}: '{title}'")
            return learning_content.id
    
    def get_content(self, content_id: int) -> Optional[Dict[str, Any]]:
        """Get learning content by ID"""
        with self.db_manager.get_session() as session:
            content = session.get(LearningContent, content_id)
            if not content:
                return None
            
            return {
                'id': content.id,
                'title': content.title,
                'content_type': content.content_type,
                'language': content.language,
                'front_template': content.front_template,
                'back_template': content.back_template,
                'example_template': content.example_template,
                'difficulty_level': content.difficulty_level,
                'tags': content.tags,
                'content_metadata': content.content_metadata,
                'created_at': content.created_at,
                'updated_at': content.updated_at,
                # Include relationship data
                'linked_anki_cards': [card.id for card in content.anki_cards]
            }
    
    def update_content(self, 
                      content_id: int,
                      **updates) -> bool:
        """
        Update learning content
        
        Args:
            content_id: ID of content to update
            **updates: Fields to update (title, content_type, templates, etc.)
        
        Returns:
            True if updated, False if not found
        """
        with self.db_manager.get_session() as session:
            content = session.get(LearningContent, content_id)
            if not content:
                return False
            
            # Update allowed fields
            allowed_fields = [
                'title', 'content_type', 'language',
                'front_template', 'back_template', 'example_template',
                'difficulty_level', 'tags', 'content_metadata'
            ]
            
            updated_fields = []
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(content, field, value)
                    updated_fields.append(field)
            
            if updated_fields:
                content.updated_at = datetime.utcnow()
                session.commit()
                logger.info(f"Updated learning content #{content_id}: {updated_fields}")
            
            return len(updated_fields) > 0
    
    def delete_content(self, content_id: int) -> bool:
        """
        Delete learning content (and unlink from anki_cards)
        
        Args:
            content_id: ID of content to delete
        
        Returns:
            True if deleted, False if not found
        """
        with self.db_manager.get_session() as session:
            content = session.get(LearningContent, content_id)
            if not content:
                return False
            
            # Unlink from anki_cards first
            session.execute(text("""
                UPDATE anki_cards 
                SET learning_content_id = NULL
                WHERE learning_content_id = :content_id
            """), {'content_id': content_id})
            
            # Delete the content
            session.delete(content)
            session.commit()
            
            logger.info(f"Deleted learning content #{content_id}")
            return True
    
    def search_content(self, 
                      filters: Optional[Dict] = None,
                      page: int = 1,
                      page_size: int = 20) -> Dict[str, Any]:
        """
        Search learning content with filters and pagination
        
        Args:
            filters: Search filters (content_type, language, difficulty_level, tags, text_search)
            page: Page number (1-based)
            page_size: Items per page
        
        Returns:
            Dictionary with results, pagination info
        """
        filters = filters or {}
        offset = (page - 1) * page_size
        
        with self.db_manager.get_session() as session:
            query = session.query(LearningContent)
            
            # Apply filters
            if filters.get('content_type'):
                query = query.filter(LearningContent.content_type == filters['content_type'])
            
            if filters.get('language'):
                query = query.filter(LearningContent.language == filters['language'])
            
            if filters.get('difficulty_level'):
                query = query.filter(LearningContent.difficulty_level == filters['difficulty_level'])
            
            if filters.get('tags'):
                # Search for any of the provided tags
                tag_conditions = []
                for tag in filters['tags']:
                    # JSON contains search - database specific
                    tag_conditions.append(text(f"JSON_EXTRACT(tags, '$') LIKE '%{tag}%'"))
                if tag_conditions:
                    query = query.filter(or_(*tag_conditions))
            
            if filters.get('text_search'):
                search_term = f"%{filters['text_search']}%"
                query = query.filter(or_(
                    LearningContent.title.like(search_term),
                    LearningContent.front_template.like(search_term),
                    LearningContent.back_template.like(search_term),
                    LearningContent.example_template.like(search_term)
                ))
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination and ordering
            results = query.order_by(LearningContent.updated_at.desc())\
                          .offset(offset)\
                          .limit(page_size)\
                          .all()
            
            # Format results
            content_list = []
            for content in results:
                content_list.append({
                    'id': content.id,
                    'title': content.title,
                    'content_type': content.content_type,
                    'language': content.language,
                    'difficulty_level': content.difficulty_level,
                    'tags': content.tags,
                    'created_at': content.created_at,
                    'updated_at': content.updated_at,
                    'has_front_template': bool(content.front_template),
                    'has_back_template': bool(content.back_template),
                    'has_example_template': bool(content.example_template),
                    'linked_anki_cards_count': len(content.anki_cards)
                })
            
            return {
                'content': content_list,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': offset + page_size < total_count,
                    'has_prev': page > 1
                },
                'filters_applied': filters
            }
    
    def get_content_types(self) -> List[Dict[str, Any]]:
        """Get available content types with counts"""
        with self.db_manager.get_session() as session:
            result = session.execute(text("""
                SELECT content_type, COUNT(*) as count
                FROM learning_content
                GROUP BY content_type
                ORDER BY count DESC
            """)).fetchall()
            
            return [
                {'content_type': row[0], 'count': row[1]}
                for row in result
            ]
    
    def get_languages(self) -> List[Dict[str, Any]]:
        """Get available languages with counts"""
        with self.db_manager.get_session() as session:
            result = session.execute(text("""
                SELECT language, COUNT(*) as count
                FROM learning_content
                GROUP BY language
                ORDER BY count DESC
            """)).fetchall()
            
            return [
                {'language': row[0], 'count': row[1]}
                for row in result
            ]
    
    def duplicate_content(self, content_id: int, new_title: Optional[str] = None) -> Optional[int]:
        """
        Duplicate learning content (useful for creating variations)
        
        Args:
            content_id: ID of content to duplicate
            new_title: Title for the new content (auto-generated if None)
        
        Returns:
            ID of the new content, None if original not found
        """
        original = self.get_content(content_id)
        if not original:
            return None
        
        # Remove fields that shouldn't be copied
        del original['id']
        del original['created_at']
        del original['updated_at']
        del original['linked_anki_cards']
        
        # Set new title
        if new_title:
            original['title'] = new_title
        else:
            original['title'] = f"{original['title']} (Copy)"
        
        # Create the duplicate
        return self.create_content(**original) 
