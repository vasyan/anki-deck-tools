from typing import Dict, List, Optional, Any
import logging

from database.manager import DatabaseManager
from models.database import ContentFragment
from models.schemas import ContentFragmentCreate, ContentFragmentRowSchema, ContentFragmentUpdate, ContentFragmentSearchRow
from models.schemas import FragmentAssetRowSchema

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class FragmentManager:
    # Supported fragment types
    FRAGMENT_TYPES = {
        'basic_meaning': 'Basic meaning',
        'pronunciation_and_tone': 'Pronunciation and tone',
        'real_life_example': 'Real life example',
        'usage_tip': 'Usage tip'
    }

    def __init__(self):
        self.db_manager = DatabaseManager()

    def get_fragment(self, fragment_id: int) -> Optional[ContentFragmentRowSchema]:
        with self.db_manager.get_session() as session:
            fragment = session.get(ContentFragment, fragment_id)
            if not fragment:
                return None

            return ContentFragmentRowSchema.model_validate(fragment, from_attributes=True)

    def get_top_rated_fragments_by_learning_content_id(self, learning_content_id: int, limit: int = 10) -> List[ContentFragmentRowSchema]:
        with self.db_manager.get_session() as session:
            fragments = session.query(ContentFragment).filter(ContentFragment.learning_content_id == learning_content_id).order_by(ContentFragment.created_at.desc()).limit(limit)
            return [ContentFragmentRowSchema.model_validate(fragment, from_attributes=True) for fragment in fragments]

    def update_fragment(self, fragment_id: int, input: ContentFragmentUpdate) -> bool:
        with self.db_manager.get_session() as session:
            fragment = session.get(ContentFragment, fragment_id)
            if not fragment:
                return False

            fragment.model_validate(input)

            session.commit()
            return True

    # TODO: Add check for fragment usage when usage tracking is implemented
    def delete_fragment(self, fragment_id: int) -> bool:
        with self.db_manager.get_session() as session:
            fragment = session.get(ContentFragment, fragment_id)
            if not fragment:
                return False

            session.delete(fragment)
            session.commit()
            return True

    def find_fragments(self,
                       input: ContentFragmentSearchRow,
                       with_assets: bool = False
                       ) -> List[ContentFragmentRowSchema]:
        with self.db_manager.get_session() as session:
            query = session.query(ContentFragment)

            if input.learning_content_id:
                query = query.filter(ContentFragment.learning_content_id == input.learning_content_id)

            if input.text_search:
                # Use LIKE for case-insensitive text search
                query = query.filter(ContentFragment.native_text.ilike(f'%{input.text_search}%'))

            if input.fragment_type:
                query = query.filter(ContentFragment.fragment_type == input.fragment_type)

            if input.has_assets is not None:
                if input.has_assets:
                    query = query.filter(ContentFragment.assets.any())
                else:
                    query = query.filter(~ContentFragment.assets.any())

            logger.debug(f"filters: {input.model_dump()}")

            query = query.order_by(ContentFragment.created_at.desc()).offset(input.offset).limit(input.limit)
            fragments = query.all()

            # Process results and conditionally include assets
            result: List[ContentFragmentRowSchema] = []
            for fragment in fragments:
                fragment_data = ContentFragmentRowSchema.model_validate(fragment, from_attributes=True)

                # Conditionally include assets
                if with_assets:
                    # Create a new model with assets included
                    assets_data = [
                        FragmentAssetRowSchema.model_validate(asset, from_attributes=True)
                        for asset in fragment.assets
                    ]
                    fragment_data.assets = assets_data

                result.append(fragment_data)

            return result

    def get_fragment_types(self) -> Dict[str, str]:
        return self.FRAGMENT_TYPES.copy()

    def get_fragment_statistics(self) -> Dict[str, Any]:
        with self.db_manager.get_session() as session:
            total_fragments = session.query(ContentFragment).count()

            # Count by type
            type_counts = {}
            for fragment_type in self.FRAGMENT_TYPES.keys():
                count = session.query(ContentFragment).filter(
                    ContentFragment.fragment_type == fragment_type
                ).count()
                type_counts[fragment_type] = count

            # Count fragments with assets
            fragments_with_assets = session.query(ContentFragment).filter(
                ContentFragment.assets.any()
            ).count()

            # Count fragments in use - TODO: Implement when usage tracking is available
            fragments_in_use = 0

            return {
                'total_fragments': total_fragments,
                'type_counts': type_counts,
                'fragments_with_assets': fragments_with_assets,
                'fragments_in_use': fragments_in_use
            }

    def create_fragment(self,
                        learning_content_id: int,
                        input: ContentFragmentCreate) -> ContentFragmentRowSchema:
        with self.db_manager.get_session() as session:
            # Create the content fragment
            fragment = ContentFragment(
                learning_content_id=learning_content_id,
                **input.model_dump()
            )
            session.add(fragment)
            session.flush()  # Get the fragment ID

            session.commit()

            return ContentFragmentRowSchema.model_validate(fragment, from_attributes=True)

    def get_fragment_learning_content(self, fragment_id: int) -> List[Dict[str, Any]]:
        """Get learning content related to a fragment"""
        with self.db_manager.get_session() as session:
            fragment = session.get(ContentFragment, fragment_id)
            if not fragment:
                return []

            # Get the learning content by ID
            from models.database import LearningContent
            learning_content = session.query(LearningContent).filter(
                LearningContent.id == fragment.learning_content_id
            ).first()

            if not learning_content:
                return []

            # Return a serializable dictionary
            return [{
                "id": learning_content.id,
                "title": learning_content.title,
                "content_type": learning_content.content_type,
                "difficulty_level": learning_content.difficulty_level,
                "language": learning_content.language,
                "tags": learning_content.tags,
                "native_text": learning_content.native_text,
                "back_template": learning_content.back_template,
                "created_at": learning_content.created_at,
                "updated_at": learning_content.updated_at
            }]
