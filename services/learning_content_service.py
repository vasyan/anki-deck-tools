import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any, cast, TypeVar

from database.manager import DatabaseManager
from models.database import LearningContent, ContentFragment
from models.schemas import LearningContentRowSchema, LearningContentUpdate
from models.schemas import LearningContentCreate
from models.schemas import LearningContentSearchRow, LearningContentFilter
from sqlalchemy import text, or_, func
from sqlalchemy.orm import Query

# Define type variable for LearningContent
T = TypeVar('T')

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

    def _apply_filters(self, query: Query[T], filters: LearningContentFilter) -> Query[T]:
        """
        Apply filters to a query based on a filter model

        Args:
            query: SQLAlchemy query object
            filters: Pydantic filter model with search criteria

        Returns:
            Updated query with filters applied
        """
        filter_data = filters.model_dump(exclude_unset=True, exclude_none=True)

        if 'content_type' in filter_data:
            query = query.filter(LearningContent.content_type == filter_data['content_type'])

        if 'language' in filter_data:
            query = query.filter(LearningContent.language == filter_data['language'])

        if 'difficulty_level' in filter_data:
            query = query.filter(LearningContent.difficulty_level == filter_data['difficulty_level'])

        if 'tags' in filter_data and filter_data['tags']:
            tag_conditions: List[Any] = []
            for tag in filter_data['tags']:
                tag_conditions.append(text(f"JSON_EXTRACT(tags, '$') LIKE '%{tag}%'"))
            if tag_conditions:
                query = query.filter(or_(*tag_conditions))

        if 'text_search' in filter_data and filter_data['text_search']:
            search_term = f"%{filter_data['text_search']}%"
            query = query.filter(or_(
                LearningContent.title.like(search_term),
                LearningContent.native_text.like(search_term),
                LearningContent.translation.like(search_term),
                # LearningContent.example_template.like(search_term)
            ))

        if 'has_fragments' in filter_data:
            if filter_data['has_fragments']:
                query = query.filter(LearningContent.fragments.any())
            else:
                query = query.filter(~LearningContent.fragments.any())

        if 'min_fragments_count' in filter_data:
            query = query.join(ContentFragment, LearningContent.id == ContentFragment.learning_content_id)\
                         .group_by(LearningContent.id)\
                         .having(func.count(ContentFragment.id) >= filter_data['min_fragments_count'])

        if 'max_fragments_count' in filter_data:
            query = query.join(ContentFragment, LearningContent.id == ContentFragment.learning_content_id)\
                         .group_by(LearningContent.id)\
                         .having(func.count(ContentFragment.id) <= filter_data['max_fragments_count'])

        if 'has_lack_of_good_examples' in filter_data and filter_data['has_lack_of_good_examples']:
            # Subquery to find learning_content_ids with fewer than 3 good examples (rank_score >= 3)
            from models.database import Ranking
            from sqlalchemy import select
            
            # Create subquery that counts fragments with good rankings (>= 3) for each learning_content
            good_examples_subq = select(
                ContentFragment.learning_content_id,
                func.count(Ranking.id).label('good_count')
            ).select_from(ContentFragment)\
             .outerjoin(Ranking, Ranking.fragment_id == ContentFragment.id)\
             .where(Ranking.rank_score >= 3)\
             .group_by(ContentFragment.learning_content_id)\
             .having(func.count(Ranking.id) >= 3)\
             .subquery()
            
            # Filter to exclude learning_content that has 3 or more good examples
            query = query.filter(~LearningContent.id.in_(
                select(good_examples_subq.c.learning_content_id)
            ))

        if 'cursor' in filter_data:
            query = query.filter(LearningContent.id > filter_data['cursor'])

        return query

    def find_content(self,
                      filters: Optional[Dict[str, Any] | LearningContentFilter] = None,
                      page: int = 1,
                      page_size: int = 20) -> Dict[str, Any]:
        """
        Search learning content with filters and pagination

        Args:
            filters: Search filters as dict or LearningContentFilter instance
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Dictionary with results, pagination info
        """
        if filters is None:
            filters = LearningContentFilter()
        elif isinstance(filters, dict):
            filters = LearningContentFilter(**filters)

        offset = (page - 1) * page_size

        with self.db_manager.get_session() as session:
            query: Query[LearningContent] = session.query(LearningContent)

            # Apply filters
            query = self._apply_filters(query, filters)

            # Get total count
            total_count = query.count()

            # Apply pagination and ordering
            # results = query.order_by(LearningContent.updated_at.desc())\
            results = query.order_by(LearningContent.id.asc())\
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
                'filters_applied': filters.model_dump(exclude_unset=True, exclude_none=True)
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

    def get_next_review_content(self) -> Optional[LearningContentRowSchema]:
        """
        Get the next most suitable content for review based on:
        1. Not reviewed in last 5 minutes
        2. Content with no rated fragments (highest priority)
        3. Content with lowest percentage of rated fragments
        4. Content with oldest last_review_at
        5. Lowest ID as fallback

        Also updates the selected content's last_review_at timestamp.
        """
        with self.db_manager.get_session() as session:
            # Calculate threshold for recent reviews (5 minutes ago)
            review_threshold = datetime.now(UTC) - timedelta(minutes=5)

            # Complex query to find the best content for review
            result = session.execute(text("""
                WITH fragment_stats AS (
                    SELECT
                        lc.id,
                        lc.title,
                        lc.content_type,
                        lc.language,
                        lc.native_text,
                        lc.translation,
                        lc.ipa,
                        lc.difficulty_level,
                        lc.tags,
                        lc.content_metadata,
                        lc.created_at,
                        lc.updated_at,
                        lc.last_review_at,
                        COUNT(cf.id) as total_fragments,
                        COUNT(CASE WHEN r.id IS NOT NULL THEN 1 END) as rated_fragments
                    FROM learning_content lc
                    LEFT JOIN content_fragments cf ON lc.id = cf.learning_content_id
                    LEFT JOIN rankings r ON cf.id = r.fragment_id
                    WHERE lc.last_review_at IS NULL
                       OR lc.last_review_at < :review_threshold
                    GROUP BY lc.id
                )
                SELECT *,
                    CASE
                        WHEN total_fragments = 0 THEN 999  -- Content with no fragments gets lowest priority
                        WHEN rated_fragments = 0 THEN 0     -- Highest priority: has fragments but none rated
                        ELSE CAST(rated_fragments AS FLOAT) / total_fragments
                    END as rating_percentage
                FROM fragment_stats
                WHERE total_fragments > 0  -- Must have at least one fragment
                ORDER BY
                    rating_percentage ASC,      -- Prioritize lower percentage of rated fragments
                    last_review_at ASC NULLS FIRST,  -- Then oldest reviewed (NULL first)
                    id ASC                      -- Finally by ID
                LIMIT 1
            """), {"review_threshold": review_threshold}).fetchone()

            if not result:
                return None

            # Convert row to dict for LearningContent object creation
            import json
            content_dict = {
                'id': result[0],
                'title': result[1],
                'content_type': result[2],
                'language': result[3],
                'native_text': result[4],
                'translation': result[5],
                'ipa': result[6],
                'difficulty_level': result[7],
                'tags': json.loads(result[8]) if result[8] else None,
                'content_metadata': json.loads(result[9]) if result[9] else None,
                'created_at': result[10],
                'updated_at': result[11],
                'last_review_at': result[12]
            }

            # Update the last_review_at timestamp for this content
            session.execute(
                text("UPDATE learning_content SET last_review_at = :now WHERE id = :id"),
                {"now": datetime.now(UTC), "id": content_dict['id']}
            )
            session.commit()

            # Return as schema object
            return LearningContentRowSchema(**content_dict)
