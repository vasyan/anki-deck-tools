
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List
from core.app import AnkiVectorApp
from database.manager import DatabaseManager
from models.schemas import LearningContentWebExportDTO
from workflows.anki_builder import AnkiBuilder
from services.learning_content_service import LearningContentService

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

db_manager = DatabaseManager()

anki_vector_instance = AnkiVectorApp(db_manager)

router = APIRouter()

@router.post("/web/json/{learning_content_id}")
async def render_to_json(learning_content_id: int) -> LearningContentWebExportDTO:
    try:
        rendered_content = await AnkiBuilder().get_rendered_content(learning_content_id)
        if rendered_content is None:
            raise ValueError(f"Failed to get rendered content for learning_content_id: {learning_content_id}")
        return rendered_content
    except Exception as e:
        logger.error(f"Error on web json export of learning content {learning_content_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/web/thai/list")
async def get_thai_word_list(
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page")
) -> Dict[str, Any]:
    try:
        learning_content_service = LearningContentService()
        return learning_content_service.find_content(filters={
        }, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"Error on web thai word list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/web/thai/ids")
async def get_thai_word_list_ids() -> List[int]:
    try:
        learning_content_service = LearningContentService()
        contents = learning_content_service.find_content(filters={
        })

        # print(contents)

        return [content["id"]  for content in contents["content"]]
    except Exception as e:
        logger.error(f"Error on web thai word list ids: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/web/thai/content/{id}")
async def get_thai_word_list_by_id(id: int) -> LearningContentWebExportDTO:
    try:
        rendered_content = await AnkiBuilder().get_rendered_content(id, format="json")
        if rendered_content is None:
            raise ValueError(f"Failed to get content for id: {id}")
        return rendered_content
    except Exception as e:
        logger.error(f"Error on web thai word list by id: {e}")
        raise HTTPException(status_code=500, detail=str(e))

