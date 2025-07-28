from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from database.manager import DatabaseManager
from services.export_service import ExportService
import logging

from services.learning_content_service import LearningContentService

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

db_manager = DatabaseManager()

router = APIRouter()

@router.get("/learning-content/stats")
async def get_learning_content_stats():
    """Get learning content statistics"""
    try:
        learning_service = LearningContentService()

        content_types = learning_service.get_content_types()
        languages = learning_service.get_languages()

        return {
            'content_types': content_types,
            'languages': languages
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

        result = learning_service.search_content(filters, page, page_size)
        return result
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

@router.post("/learning-content/{content_id}/export/{format}")
async def export_learning_content(content_id: int, format: str):
    """Export learning content to different formats"""
    try:
        export_service = ExportService()

        if format == 'anki':
            result = export_service.get_anki_content(content_id)
        elif format == 'api-json':
            result = export_service.export_to_api_json(content_id)
        elif format == 'html':
            result = export_service.export_to_html(content_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported export format: {format}")

        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting learning content {content_id} to {format}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
