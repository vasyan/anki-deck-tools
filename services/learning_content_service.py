import logging
from typing import Dict, List, Optional, Any, cast

from database.manager import DatabaseManager
from models.database import LearningContent
from models.schemas import LearningContentRowSchema, LearningContentUpdate
from models.schemas import LearningContentCreate
from models.schemas import LearningContentSearchRow
from sqlalchemy import text, or_

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add a utility function for data extraction
def extract_object_data(obj: Any, columns: List[str]) -> Dict[str, Any]:
    """
    Extract data from an object based on column names

    Args:
        obj: Object to extract data from
        columns: List of column/attribute names to extract

    Returns:
        Dictionary with extracted data
    """
    extracted_data: Dict[str, Any] = {}
    for col in columns:
        if hasattr(obj, col):
            extracted_data[col] = getattr(obj, col)
        else:
            extracted_data[col] = None
    return extracted_data


def format_operation_result(success: bool, data: Dict[str, Any] | None = None, error: str | None = None) -> Dict[str, Any]:
    """
    Standard format for operation results

    Args:
        success: Whether the operation was successful
        data: Data to include in successful responses
        error: Error message for failed responses

    Returns:
        Standardized result dictionary
    """

    result: Dict[str, Any] = {"success": success}

    if data:
        result.update(data)
    if not success:
        result["error"] = error or "Unknown error occurred"

    return result


class LearningContentService:
    """Service for managing learning content abstractions"""

    def __init__(self):
        self.db_manager = DatabaseManager()

    def create_content(self, payload: LearningContentCreate) -> int:
        """
        Create a new learning content record and return its ID.
        """
        with self.db_manager.get_session() as session:
            data = payload.model_dump(exclude_unset=True)
            # Provide defaults for mutable columns
            data.setdefault("tags", [])
            data.setdefault("content_metadata", {})

            learning_content = LearningContent(**data)

            session.add(learning_content)
            session.flush()
            session.commit()

            logger.info(f"Created learning content #{learning_content.id}: '{learning_content.title}'")
            return cast(int, learning_content.id)

    def get_content(self, lc_id: int) -> Optional[LearningContentRowSchema]:
        with self.db_manager.get_session() as session:
            content = session.get(LearningContent, lc_id)
            if not content:
                return None

            # Validate and convert ORM object to Pydantic schema
            # Extra attributes not declared in the schema are ignored by default
            return LearningContentRowSchema.model_validate(content, from_attributes=True)

    def update_content(self, lc_id: int, payload: LearningContentUpdate) -> bool:
        with self.db_manager.get_session() as session:
            content = session.get(LearningContent, lc_id)
            if not content:
                return False

            updates = payload.model_dump(exclude_unset=True)
            if not updates:
                return True  # nothing to change

            for field, value in updates.items():
                setattr(content, field, value)

            session.commit()
            logger.info("Updated learning content #%s: %s", lc_id, list(updates))
            return True

    def delete_content(self, lc_id: int) -> bool:
        with self.db_manager.get_session() as session:
            content = session.get(LearningContent, lc_id)
            if not content:
                return False

            session.execute(text("""
                UPDATE anki_cards
                SET learning_content_id = NULL
                WHERE learning_content_id = :lc_id
            """), {'lc_id': lc_id})

            session.delete(content)
            session.commit()

            logger.info(f"Deleted learning content #{lc_id}")
            return True

    def search_content(self,
                      filters: Optional[Dict[str, Any]] = None,
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
                tag_conditions: List[Any] = []
                for tag in filters['tags']:
                    # JSON contains search - database specific
                    tag_conditions.append(text(f"JSON_EXTRACT(tags, '$') LIKE '%{tag}%'"))
                if tag_conditions:
                    query = query.filter(or_(*tag_conditions))

            if filters.get('text_search'):
                search_term = f"%{filters['text_search']}%"
                query = query.filter(or_(
                    LearningContent.title.like(search_term),
                    LearningContent.native_text.like(search_term),
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

            # Convert ORM objects to search row schema dicts
            content_list = [
                LearningContentSearchRow.model_validate(obj, from_attributes=True).model_dump()
                for obj in results
            ]

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

