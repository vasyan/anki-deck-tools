from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
from database.manager import DatabaseManager
import logging

from services.learning_content_service import LearningContentService
from services.fragment_manager import FragmentManager
from models.schemas import ContentFragmentSearchRow, ContentFragmentRowSchema

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
    search: Optional[str] = None
):
    """Get learning content with filtering and pagination"""
    try:
        learning_service = LearningContentService()

        filters = {}
        if content_type:
            filters['content_type'] = content_type
        if language:
            filters['language'] = language
        if search:
            filters['text_search'] = search

        try:
            result = learning_service.find_content(filters, page, page_size)
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

@router.get("/learning-content/{content_id}/fragments", response_model=List[ContentFragmentRowSchema])
async def get_learning_content_fragments(content_id: int):
    """Get fragments related to specific learning content"""
    try:
        fragment_service = FragmentManager()

        # Create a ContentFragmentSearchRow instance with learning_content_id
        search_params = ContentFragmentSearchRow(learning_content_id=content_id)

        fragments = fragment_service.find_fragments(input=search_params)

        return fragments
    except Exception as e:
        logger.error(f"Error getting fragments for content {content_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
