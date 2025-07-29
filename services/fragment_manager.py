from typing import Dict, List, Optional, Any
import logging

from database.manager import DatabaseManager
from models.database import ContentFragment
from models.schemas import ContentFragmentCreate, ContentFragmentRowSchema, ContentFragmentUpdate

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

    def get_fragments_by_learning_content_id(self, learning_content_id: int) -> List[ContentFragmentRowSchema]:
        with self.db_manager.get_session() as session:
            fragments = session.query(ContentFragment).filter(ContentFragment.learning_content_id == learning_content_id).all()
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
                       text_search: Optional[str] = None,
                       fragment_type: Optional[str] = None,
                       has_assets: Optional[bool] = None,
                       limit: int = 50,
                       offset: int = 0) -> List[ContentFragmentRowSchema]:
        with self.db_manager.get_session() as session:
            query = session.query(ContentFragment)

            if text_search:
                # Use LIKE for case-insensitive text search
                query = query.filter(ContentFragment.text.ilike(f'%{text_search}%'))

            if fragment_type:
                query = query.filter(ContentFragment.fragment_type == fragment_type)

            if has_assets is not None:
                if has_assets:
                    query = query.filter(ContentFragment.assets.any())
                else:
                    query = query.filter(~ContentFragment.assets.any())

            query = query.offset(offset).limit(limit)
            fragments = query.all()

            return [ContentFragmentRowSchema.model_validate(fragment, from_attributes=True) for fragment in fragments]

    def find_by_text_and_type(self, text: str, fragment_type: Optional[str] = None) -> Optional[ContentFragmentRowSchema]:
        with self.db_manager.get_session() as session:
            query = session.query(ContentFragment).filter(ContentFragment.text == text.strip())

            if fragment_type:
                query = query.filter(ContentFragment.fragment_type == fragment_type)

            fragment = query.first()
            if not fragment:
                return None

            return ContentFragmentRowSchema.model_validate(fragment, from_attributes=True)

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

    # def get_fragment_with_assets(self, fragment_id: int) -> Optional[ContentFragmentRowSchema]:
    #     # we have to check if there is at least one audio aseet
    #     # if none found, have to create it with
