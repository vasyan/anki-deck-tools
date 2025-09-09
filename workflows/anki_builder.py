import hashlib
import json
import os
import re
import traceback
from typing import Any, Dict, List
import logging
import uuid
from models.schemas import (
    ContentFragmentCreate,
    ContentFragmentRowSchema,
    ContentFragmentSearchRow,
    LearningContentRowSchema,
    LearningContentWebExportDTO,
    SyncLearningContentToAnkiInputSchema,
    RenderCardInputSchema
)
from services.card_service import CardService
from services.card_template_service import CardTemplateService
from services.learning_content_service import LearningContentService
from services.fragment_service import FragmentService
from services.fragment_asset_manager import FragmentAssetManager
from services.llm_service import LLMService
import asyncio
from config import settings
from utils.logging import log_json

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
        self.fragment_service = FragmentService()
        self.card_template_service = CardTemplateService()
        self.fragment_asset_service = FragmentAssetManager()
        self.llm_service = LLMService(model=settings.local_model_thai)
        self.job_id = uuid.uuid4().hex

    def calculate_content_hash(self, content: Dict[str, Any]) -> str:
        hash_data = {
            'title': content.get('title', ''),
            'front': content.get('front', ''),
            'back': content.get('back', ''),
        }

        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.md5(hash_string.encode()).hexdigest()

    async def get_rendered_content(self, learning_content_id: int, format: str = "anki") -> LearningContentWebExportDTO | None:
        # logger.debug(f"get_rendered_content: {learning_content_id}")
        try:
            lc_data= self.lc_service.get_content(learning_content_id)
            top_rated_fragments = self.fragment_service.get_top_rated_fragments_by_learning_content_id(learning_content_id, limit=3, min_rank_score=None, fragment_type='real_life_example')
            target_item_fragment = self.fragment_service.get_top_rated_fragments_by_learning_content_id(learning_content_id, limit=1, fragment_type='target_learning_item')

            if not lc_data:
                raise ValueError("Learning content not found")

            if not lc_data.native_text:
                raise ValueError("Learning content native text not found")
            if not lc_data.translation:
                raise ValueError("Learning content translation not found")
            if not lc_data.ipa:
                raise ValueError("Learning content ipa not found")

            # TODO: join table right in `get_top_fragments`
            fragments_with_assets: List[ContentFragmentRowSchema] = []

            # logger.debug(f"related_fragments: {related_fragments}")
            # log_json(logger, fragments_with_assets, max_str=80, max_items=10)

            for fragment in top_rated_fragments:
                # audio_asset = await self.fragment_asset_service.get_asset_by_fragment_id(fragment.id, 'audio', generate_if_not_found=False)
                fragments_with_assets.append(ContentFragmentRowSchema(
                    **fragment.model_dump(),
                    # audio_asset=audio_asset
                ))

            if len(target_item_fragment) > 0:
                # audio_asset = await self.fragment_asset_service.get_asset_by_fragment_id(target_item_fragment[0].id, 'audio', generate_if_not_found=False)
                fragments_with_assets.append(ContentFragmentRowSchema(
                    **target_item_fragment[0].model_dump(),
                    # audio_asset=audio_asset
                ))

            # logger.debug(f"fragments_with_assets: {target_item_fragment}")

            render_results = self.card_template_service.render_card(RenderCardInputSchema(
                native_text=lc_data.native_text,
                translation=lc_data.translation,
                ipa=lc_data.ipa,
                fragments=fragments_with_assets
            ), format=format)

            # print(f"render_results: {render_results}")

            return LearningContentWebExportDTO(
                front=render_results.front,
                back=render_results.back,
                examples=render_results.examples
            )

        except Exception as e:
            logger.error(f"Error uploading content {learning_content_id}: {e}")
            logger.error(traceback.format_exc())
            return None

    async def process_sync(self, learning_content_id: int):
        # Get rendered content with proper typing
        rendered_content = await self.get_rendered_content(learning_content_id)
        if not rendered_content:
            logger.error(f"Failed to get rendered content for learning_content_id: {learning_content_id}")
            return

        content_hash = self.calculate_content_hash(rendered_content.model_dump())
        assets_to_sync = [fragment.assets[0] for fragment in rendered_content.examples if fragment.assets] if rendered_content.examples else []

        # logger.debug(f"result: {rendered_content}")
        # log_json(logger, rendered_content.model_dump(), max_str=80, max_items=10)
        # logger.debug(f"assets_to_sync: {assets_to_sync}")
        # log_json(logger, len(assets_to_sync), max_str=80, max_items=10)
        # return

        await self.card_service.sync_learning_content_to_anki(
            SyncLearningContentToAnkiInputSchema(
                learning_content_id=learning_content_id,
                front=rendered_content.front,
                back=rendered_content.back,
                content_hash=content_hash,
                assets_to_sync=assets_to_sync,
                force_update=True
            ),
        )

    def populate_content_with_target_learning_fragment(self, learning_content_id: int):
        lc_data = LearningContentRowSchema.model_validate(
            self.lc_service.get_content(learning_content_id),
            from_attributes=True
        )
        if not lc_data or not lc_data.native_text:
            raise ValueError("Learning content not found")

        self.fragment_service.create_fragment(
            learning_content_id=learning_content_id,
            input=ContentFragmentCreate(
                native_text=lc_data.native_text,
                body_text=lc_data.title,
                fragment_type='target_learning_item',
                fragment_metadata={
                    'job_id': self.job_id
                }
            ))

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

            # target_word = re.sub(r'\w?\(.+', ' ', lc_data.title)
            target_word = lc_data.title

            user_promt = f"""
            {{
                "input": "{target_word}",
            }}
            """

            llm_response = self.llm_service.call_llm(
                system_prompt=template_str,
                # user_prompt=re.sub(r'\w?\(.+', ' ', lc_data.title)
                user_prompt=user_promt
            )
            llm_response = self.clean_json_like_string(llm_response)

            # print(f"llm_response: {llm_response}")

            try:
                examples_json = json.loads(llm_response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {llm_response}")
                logger.error(f"JSON error at line {e.lineno}: {e.msg}")
                return

            # print(f"examples_json: {examples_json}")

            # return

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
                            'job_id': self.job_id
                        }
                    ))
        except Exception as e:
            logger.error(f"Error populating content with example: {e}")
            logger.error(traceback.format_exc())
            return

    def process_content_and_populate_with_target_learning_fragment(self):
        contents = self.lc_service.find_content(filters={
            'has_target_learning_fragment': False
        },
        page=1,
        page_size=50
        )['content']
        ids = [content['id'] for content in contents]
        print(f"ids: {ids}")
        # for i in ids:
        #     self.populate_content_with_target_learning_fragment(i)

        print(f"Finished populating content with target learning fragment")

    def process_contents(self):
        # for i in range(65, 80):
        #     self.populate_content_with_example(i)
        # for i in range(270, 350):
        #     try:
        #         self.populate_content_with_target_learning_fragment(i)
        #     except Exception as e:
        #         logger.error(f"Error populating content with target learning fragment: {e}")
        #         logger.error(traceback.format_exc())
        #         continue
        # return
        contents = self.lc_service.find_content(filters={
            # 'has_fragments': False
            # 'max_fragments_count': 3,
            # 'cursor': 270,
            'has_lack_of_good_examples': True
        },
        page=1,
        page_size=50
        )['content']
        ids = [content['id'] for content in contents]
        # ids = range(270, 350)
        print(f"ids: {ids}")
        for i in ids:
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

        fragments_withouth_assets = self.fragment_service.find_fragments(ContentFragmentSearchRow(
            fragment_type='target_learning_item',
            has_assets=False,
            limit=100
        ))
        ids = [fragment['id'] for fragment in fragments_withouth_assets]

        print(f"ids: {ids}")

        tasks = [process_single_fragment(i) for i in ids]

        # # Create tasks for all fragments
        # tasks = [process_single_fragment(i) for i in range(47, 60)]

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

    async def sync_to_anki(self, filters: Dict[str, Any] | None = None, page_size: int = 50) -> Dict[str, Any]:
        logger.info(f"syncing to anki with filters: {filters}")

        contents = self.lc_service.find_content(page_size=page_size, filters=filters or {})

        ids = [content["id"]  for content in contents["content"]]

        logger.info(f"syncing to anki: {len(ids)} contents")

        success_count = 0
        error_count = 0
        errors = []

        for i in ids:
            try:
                await self.process_sync(i)
                success_count += 1
            except Exception as e:
                error_count += 1
                errors.append({"id": i, "error": str(e)})
                logger.error(f"Error syncing content {i}: {e}")

        return {
            "processed_count": len(ids),
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors
        }

    def clean_json_like_string(self, raw_text: str) -> str:
        text = raw_text.replace("```json", "")
        text = text.replace("```", "")

        # remove all unnecesary intros from LLM like `User input: blabalbal` before json started with `[`
        # text = re.sub(r'^.*?\[', '[', text)
        # Fix smart quotes
        text = text.replace("“", '"').replace("”", '"').replace("’", "'")
        # replace γ with y
        text = re.sub(r'γ', 'y', text)
        # Balance brackets (roughly) NOT SURE IF THIS IS NEEDED
        # text = re.sub(r'\[([^\[\]]*)\)', r'[\1]', text)  # Fix ) in place of ]
        return text
