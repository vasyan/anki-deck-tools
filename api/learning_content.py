from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from database.manager import DatabaseManager
import logging

from services.learning_content_service import LearningContentService
from services.fragment_service import FragmentService
from models.schemas import ContentFragmentSearchRow, LearningContentFilter

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

db_manager = DatabaseManager()

router = APIRouter()

@router.get("/learning-content/stats")
async def get_learning_content_stats():
    """Get learning content statistics"""
    try:
        learning_service = LearningContentService()

        try:
            content_types = learning_service.get_content_types()
            languages = learning_service.get_languages()

            return {
                'content_types': content_types,
                'languages': languages
            }
        except Exception as db_error:
            # If there's a database error (e.g., table doesn't exist), return empty results
            logger.warning(f"Database query error for stats: {db_error}")

            # Return empty result
            return {
                'content_types': [],
                'languages': []
            }
    except Exception as e:
        logger.error(f"Error getting learning content stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/learning-content")
async def get_learning_content(
    page: int = 1,
    page_size: int = 20,
    content_type: Optional[str] = None,
    language: Optional[str] = None,
    search: Optional[str] = None,
    min_fragments_count: Optional[int] = None,
    max_fragments_count: Optional[int] = None,
    cursor: Optional[int] = None
):
    """Get learning content with filtering and pagination"""
    try:
        learning_service = LearningContentService()

        filters = LearningContentFilter()
        if content_type:
            filters.content_type = content_type
        if language:
            filters.language = language
        if search:
            filters.text_search = search
        if min_fragments_count:
            filters.min_fragments_count = min_fragments_count
        if max_fragments_count:
            filters.max_fragments_count = max_fragments_count
        if cursor:
            filters.cursor = cursor

        try:
            result = learning_service.find_content(filters=filters, page=page, page_size=page_size)
            return result
        except Exception as db_error:
            # If there's a database error (e.g., table doesn't exist), return empty results
            logger.warning(f"Database query error: {db_error}")

            # Return empty result with valid pagination structure
            return {
                'content': [],
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': 0,
                    'total_pages': 0,
                    'has_next': False,
                    'has_prev': False
                },
                'filters_applied': filters
            }
    except Exception as e:
        logger.error(f"Error getting learning content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/learning-content/next-review")
async def get_next_review_content():
    """Get the next most suitable learning content for review"""
    try:
        learning_service = LearningContentService()
        content = learning_service.get_next_review_content()
        
        if not content:
            raise HTTPException(status_code=404, detail="No content available for review")
        
        return content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting next review content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/learning-content/{content_id}")
async def get_learning_content_by_id(content_id: int):
    """Get specific learning content by ID"""
    try:
        learning_service = LearningContentService()
        content = learning_service.get_content(content_id)

        if not content:
            raise HTTPException(status_code=404, detail="Learning content not found")

        return content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting learning content {content_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/learning-content/{content_id}")
async def update_learning_content(content_id: int, updates: Dict[str, Any]):
    """Update learning content"""
    try:
        learning_service = LearningContentService()
        success = learning_service.update_content(content_id, **updates)

        if not success:
            raise HTTPException(status_code=404, detail="Learning content not found")

        return {"success": True, "message": f"Learning content {content_id} updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating learning content {content_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# @router.post("/learning-content/{content_id}/export/{format}")
# async def export_learning_content(content_id: int, format: str):
#     """Deprecated export endpoint"""
#     raise HTTPException(status_code=501, detail="Export endpoint deprecated")

@router.get("/learning-content/{content_id}/fragments")
async def get_learning_content_fragments(content_id: int, order_by: str = "avg_rank_score"):
    """Get fragments related to specific learning content"""
    try:
        fragment_service = FragmentService()

        # Create a ContentFragmentSearchRow instance with learning_content_id
        search_params = ContentFragmentSearchRow(learning_content_id=content_id)

        # Get fragments with assets and rankings
        fragments = fragment_service.find_fragments(
            input=search_params,
            with_assets=True,
            with_rankings=True,
            order_by=order_by
        )

        return fragments
    except Exception as e:
        logger.error(f"Error getting fragments for content {content_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
