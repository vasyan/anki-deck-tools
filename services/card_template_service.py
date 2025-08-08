from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from database.manager import DatabaseManager
from typing import Any, List, Dict, cast, Optional
from jinja2 import Template as JinjaTemplate

from models.schemas import ContentFragmentRowSchema

templates = Jinja2Templates(directory="templates/card")

class RenderCardInputSchema(BaseModel):
    native_text: str
    back_template: str
    fragments: List[ContentFragmentRowSchema]

class RenderCardOutputSchema(BaseModel):
    front: str
    back: str
    examples: Optional[List[ContentFragmentRowSchema]] = None

class CardTemplateService:
    def __init__(self):
        self.db_manager = DatabaseManager()

    def render_card(self, input: RenderCardInputSchema, format: str = "anki") -> RenderCardOutputSchema:
        context = input.model_dump()
        if format == "anki":
            front_template = cast(JinjaTemplate, templates.get_template("front.jinja"))  # type: ignore[no-any-return]
            back_template = cast(JinjaTemplate, templates.get_template("back.jinja"))  # type: ignore[no-any-return]

            return RenderCardOutputSchema(
                front=front_template.render(context),
                back=back_template.render(context),
            )
        elif format == "json":
            return RenderCardOutputSchema(
                front=context["native_text"],
                back=context["back_template"],
                examples=context["fragments"]
            )
        raise ValueError(f"Invalid format: {format}")

