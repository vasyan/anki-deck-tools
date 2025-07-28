from fastapi import APIRouter, Form, HTTPException
from services.template_parser import TemplateParser
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter()

@router.post("/templates/parse")
async def parse_template(template_content: str = Form(...)):
    """Parse template content and extract fragment tokens"""
    try:
        parser = TemplateParser()
        tokens = parser.parse_template(template_content)
        
        return {
            "tokens": tokens,
            "fragment_count": len(set(token['fragment_id'] for token in tokens))
        }
    except Exception as e:
        logger.error(f"Error parsing template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates/render")
async def render_template(
    template_content: str = Form(...),
    output_format: str = Form("html"),
    card_id: int = Form(None),
    track_usage: bool = Form(True)
):
    """Render template content"""
    try:
        parser = TemplateParser()
        rendered_content = parser.render_template(template_content, output_format, card_id, track_usage)
        
        return {
            "rendered_content": rendered_content,
            "original_content": template_content,
            "output_format": output_format
        }
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates/validate")
async def validate_template(template_content: str = Form(...)):
    """Validate template content"""
    try:
        parser = TemplateParser()
        validation = parser.validate_template(template_content)
        
        return validation
    except Exception as e:
        logger.error(f"Error validating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))
