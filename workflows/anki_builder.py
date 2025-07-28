import hashlib
import json
from typing import Any, Dict
from services.card_service import CardService, SyncLearningContentToAnkiInputSchema
from services.card_template_service import CardTemplateService, RenderCardInputSchema
from services.learning_content_service import LearningContentService
from services.fragment_manager import FragmentManager

DEFAULT_DECK = "top-thai-2000"

class AnkiBuilder:
    def __init__(
            self,
            deck_name: str = DEFAULT_DECK
        ) -> None:
        self.card_service = CardService()
        self.deck_name = deck_name
        self.lc_service = LearningContentService()
        self.fragment_service = FragmentManager()
        self.card_template_service = CardTemplateService()

    async def get_materials(self, learning_content_id: int):
        lc_data= self.lc_service.get_content(learning_content_id)
        related_fragments = self.fragment_service.get_fragments_by_learning_content_id(learning_content_id)

        if not lc_data or not related_fragments:
            raise ValueError("Learning content or related fragments not found")

        # TODO: ranking system
        top_rated_fragments = related_fragments[:10]

        render_results = self.card_template_service.render_card(RenderCardInputSchema(
            title=lc_data.title,
            fragments=top_rated_fragments
        ))

        content_hash = self._calculate_content_hash(render_results.model_dump())

        sync_result = await self.card_service.sync_learning_content_to_anki(SyncLearningContentToAnkiInputSchema(
            lc_data=lc_data,
            front=render_results.front,
            back=render_results.back,
            content_hash=content_hash
        ))
        return {
            "learning_content": lc_data,
            "fragments": [frag.model_dump() for frag in related_fragments],
            "render_results": render_results,
            "content_hash": content_hash,
            "sync_result": sync_result
        }


    def _calculate_content_hash(self, content: Dict[str, Any]) -> str:
        hash_data = {
            'title': content.get('title', ''),
            'front': content.get('front', ''),
            'back': content.get('back', ''),
        }

        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.md5(hash_string.encode()).hexdigest()
