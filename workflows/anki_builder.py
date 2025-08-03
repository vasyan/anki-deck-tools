import hashlib
import json
import os
import re
import traceback
from typing import Any, Dict, List
import logging
import uuid
from models.schemas import ContentFragmentCreate, ContentFragmentWithAssetsRowSchema, LearningContentRowSchema
from services.card_service import CardService, SyncLearningContentToAnkiInputSchema
from services.card_template_service import CardTemplateService, RenderCardInputSchema
from services.learning_content_service import LearningContentService
from services.fragment_manager import FragmentManager
from services.fragment_asset_manager import FragmentAssetManager
from services.llm_service import LLMService
import asyncio
from config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

DEFAULT_DECK = "top-thai-2000"

os.environ['LM_STUDIO_API_BASE'] = "http://127.0.0.1:1234/v1"

class AnkiBuilder:
    def __init__(
            self,
            deck_name: str | None = DEFAULT_DECK
        ) -> None:
        self.card_service = CardService()
        self.deck_name = deck_name
        self.lc_service = LearningContentService()
        self.fragment_service = FragmentManager()
        self.card_template_service = CardTemplateService()
        self.fragment_asset_service = FragmentAssetManager()
        self.llm_service = LLMService(model=settings.local_model_thai)

    def _calculate_content_hash(self, content: Dict[str, Any]) -> str:
        hash_data = {
            'title': content.get('title', ''),
            'front': content.get('front', ''),
            'back': content.get('back', ''),
        }

        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.md5(hash_string.encode()).hexdigest()

    async def updload_content(self, learning_content_id: int):
        try:
            lc_data= self.lc_service.get_content(learning_content_id)
            related_fragments = self.fragment_service.get_top_rated_fragments_by_learning_content_id(learning_content_id, limit=2)

            if not lc_data or not related_fragments:
                raise ValueError("Learning content or related fragments not found")

            # TODO: join table right in `get_top_fragments`
            fragments_with_assets: List[ContentFragmentWithAssetsRowSchema] = []

            for fragment in related_fragments:
                audio_asset = await self.fragment_asset_service.get_asset_by_fragment_id(fragment.id, 'audio', generate_if_not_found=False)
                fragments_with_assets.append(ContentFragmentWithAssetsRowSchema(
                    **fragment.model_dump(),
                    audio_asset=audio_asset
                ))

            render_results = self.card_template_service.render_card(RenderCardInputSchema(
                native_text=lc_data.native_text,
                fragments=fragments_with_assets
            ))

            # print(f"render_results: {render_results}")

            content_hash = self._calculate_content_hash(render_results.model_dump())
            assets_to_sync = [asset.audio_asset for asset in fragments_with_assets if asset.audio_asset]

            await self.card_service.sync_learning_content_to_anki(SyncLearningContentToAnkiInputSchema(
                learning_content_id=learning_content_id,
                front=render_results.front,
                back=render_results.back,
                content_hash=content_hash,
                assets_to_sync=assets_to_sync
            ), force_update=True)
            # return {
            #     "learning_content": lc_data,
            #     # "fragments": [frag.model_dump(mode="json") for frag in fragments_with_assets],
            #     # "fragments": [frag.id for frag in fragments_with_assets],
            #     "render_results": render_results,
            #     "content_hash": content_hash,
            #     # "sync_result": sync_result
            # }
        except Exception as e:
            logger.error(f"Error uploading content {learning_content_id}: {e}")
            logger.error(traceback.format_exc())
            return

    def populate_content_with_example(self, learning_content_id: int):
        try:
            lc_data = LearningContentRowSchema.model_validate(
                self.lc_service.get_content(learning_content_id),
                from_attributes=True
            )
            if not lc_data:
                raise ValueError("Learning content not found")

            TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "instructions", "content-sections", "typhoon_example.txt")

            with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
                template_str = f.read()

            llm_response = self.llm_service.call_llm(
                system_prompt=template_str,
                user_prompt=re.sub(r'\w?\(.+', ' ', lc_data.title)
            )
            llm_response = llm_response.replace("```json", "").replace("```", "")

            # print(f"llm_response: {llm_response}")

            try:
                examples_json = json.loads(llm_response)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response: {llm_response}")
                return

            # print(f"examples_json: {examples_json}")

            for example in examples_json:
                self.fragment_service.create_fragment(
                    learning_content_id=learning_content_id,
                    input=ContentFragmentCreate(
                        native_text=example['native_text'],
                        ipa=example['ipa'],
                        body_text=example['body_text'],
                        fragment_type='real_life_example',
                        extra=example['extra'],
                        fragment_metadata={
                            'job_id': uuid.uuid4().hex,
                        }
                    ))
        except Exception as e:
            logger.error(f"Error populating content with example: {e}")
            logger.error(traceback.format_exc())
            return

    def process_contents(self):
        for i in range(65, 80):
            self.populate_content_with_example(i)

    async def process_fragments(self):
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent operations

        async def process_single_fragment(fragment_id: int):
            async with semaphore:
                try:
                    await self.fragment_asset_service.generate_asset_for_fragment(fragment_id, 'audio')
                    logger.info(f"Successfully processed fragment {fragment_id}")
                except Exception as e:
                    logger.error(f"Error processing fragment {fragment_id}: {e}")

        # Create tasks for all fragments
        tasks = [process_single_fragment(i) for i in range(47, 49)]

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

    async def process_uploading(self):
        # for i in range(15, 100):
        #     await self.updload_content(i)
        await self.updload_content(100)

