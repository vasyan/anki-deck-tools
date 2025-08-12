from fastapi.templating import Jinja2Templates
from database.manager import DatabaseManager
from typing import Any, Dict, cast
from jinja2 import Template as JinjaTemplate
import logging

from models.schemas import RenderCardInputSchema, RenderCardOutputSchema
from utils.logging import log_json

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

templates = Jinja2Templates(directory="templates/card")


class CardTemplateService:
    def __init__(self):
        self.db_manager = DatabaseManager()

    def render_card(self, input: RenderCardInputSchema, format: str = "anki") -> RenderCardOutputSchema:
        context = input.model_dump()
        if format == "anki":
            front_template = cast(JinjaTemplate, templates.get_template("front.jinja"))  # type: ignore[no-any-return]
            back_template = cast(JinjaTemplate, templates.get_template("back.jinja"))  # type: ignore[no-any-return]

            # log_json(logger, context, max_str=80, max_items=10)

            return RenderCardOutputSchema(
                front=front_template.render(context),
                back=back_template.render(context),
                examples=context["fragments"],
            )
        elif format == "json":
            return RenderCardOutputSchema(
                front=context["native_text"],
                back=context["translation"],
                examples=context["fragments"],
            )
        raise ValueError(f"Invalid format: {format}")

