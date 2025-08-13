from fastapi import HTTPException
from typing import Dict, List, Optional, Any
import logging
from sqlalchemy import func

from database.manager import DatabaseManager
from models.database import ContentFragment, Ranking
from models.schemas import ContentFragmentCreate, ContentFragmentRowSchema, ContentFragmentUpdate, ContentFragmentSearchRow
from models.schemas import FragmentAssetRowSchema, FragmentRankingInput

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class FragmentService:
    # Supported fragment types
    FRAGMENT_TYPES = {
        'basic_meaning': 'Basic meaning',
        'pronunciation_and_tone': 'Pronunciation and tone',
        'real_life_example': 'Real life example',
        'usage_tip': 'Usage tip'
    }

    def __init__(self):
        self.db_manager = DatabaseManager()

    def get_fragment(self, fragment_id: int, fragment_type: Optional[str] = 'real_life_example') -> Optional[Dict[str, Any]]:
        with self.db_manager.get_session() as session:
            # Query with ranking aggregation
            result = session.query(
                ContentFragment,
                func.avg(Ranking.rank_score).label("avg_rank_score"),
                func.count(Ranking.id).label("ranking_count")
            ).outerjoin(
                Ranking,
                (ContentFragment.id == Ranking.fragment_id) & (Ranking.asset_id.is_(None))
            ).filter(
                ContentFragment.id == fragment_id,
                ContentFragment.fragment_type == fragment_type
            ).group_by(ContentFragment).first()

            if not result:
                return None

            fragment, avg_rank_score, ranking_count = result

            # Build response dict
            fragment_dict = {
                "id": fragment.id,
                "native_text": fragment.native_text,
                "body_text": fragment.body_text,
                "ipa": fragment.ipa,
                "extra": fragment.extra,
                "fragment_type": fragment.fragment_type,
                "learning_content_id": fragment.learning_content_id,
                "created_at": fragment.created_at,
                "updated_at": fragment.updated_at,
                "avg_rank_score": float(avg_rank_score) if avg_rank_score else None,
                "ranking_count": ranking_count or 0
            }

            return fragment_dict

    def get_top_rated_fragments_by_learning_content_id(self, learning_content_id: int, limit: int = 10, min_rank_score: Optional[float] = None, fragment_type: Optional[str] = None) -> List[ContentFragmentRowSchema]:
        with self.db_manager.get_session() as session:
            # Query with ranking aggregation (same pattern as find_fragments)
            query = session.query(
                ContentFragment,
                func.avg(Ranking.rank_score).label("avg_rank_score")
            ).outerjoin(
                Ranking,
                (ContentFragment.id == Ranking.fragment_id) & (Ranking.asset_id.is_(None))
            ).filter(
                ContentFragment.learning_content_id == learning_content_id,
                ContentFragment.fragment_type == fragment_type
            ).group_by(ContentFragment).having(
                func.avg(Ranking.rank_score) >= min_rank_score if min_rank_score else True
            ).order_by(
                func.avg(Ranking.rank_score).desc(),
                ContentFragment.created_at.desc()
            ).limit(limit)

            results = query.all()

            # Extract just the ContentFragment objects from the query results
            fragments = [fragment for fragment, _ in results]
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
                       with_assets: bool = False,
                       with_rankings: bool = True,
                       order_by: str = "avg_rank_score",
                       ) -> List[Dict[str, Any]]:
        with self.db_manager.get_session() as session:
            # Build query with ranking aggregations
            query = session.query(
                ContentFragment,
                func.avg(Ranking.rank_score).label("avg_rank_score"),
                func.count(Ranking.id).label("ranking_count")
            ).outerjoin(
                Ranking,
                (ContentFragment.id == Ranking.fragment_id) & (Ranking.asset_id.is_(None))
            )

            if input.learning_content_id:
                query = query.filter(ContentFragment.learning_content_id == input.learning_content_id)

            if input.text_search:
                query = query.filter(ContentFragment.native_text.ilike(f'%{input.text_search}%'))

            if input.fragment_type:
                query = query.filter(ContentFragment.fragment_type == input.fragment_type)

            if input.has_assets is not None:
                if input.has_assets:
                    query = query.filter(ContentFragment.assets.any())
                else:
                    query = query.filter(~ContentFragment.assets.any())

            if input.min_rating is not None:
                query = query.having(func.avg(Ranking.rank_score) >= input.min_rating)

            # logger.debug(f"filters: {input.model_dump()}")

            # Group by fragment to get aggregates
            query = query.group_by(ContentFragment)

            # Order by average ranking (highest first), then by creation date
            query = query.order_by(
                func.avg(Ranking.rank_score).desc().nullslast() if order_by == "avg_rank_score" else ContentFragment.created_at.desc()
            ).offset(input.offset).limit(input.limit)

            results = query.all()

            # Process results
            fragments_with_rankings = []
            for fragment, avg_rank_score, ranking_count in results:
                fragment_dict = {
                    "id": fragment.id,
                    "native_text": fragment.native_text,
                    "body_text": fragment.body_text,
                    "ipa": fragment.ipa,
                    "extra": fragment.extra,
                    "fragment_type": fragment.fragment_type,
                    "learning_content_id": fragment.learning_content_id,
                    "created_at": fragment.created_at,
                    "updated_at": fragment.updated_at
                }

                # Add ranking info if requested
                if with_rankings:
                    fragment_dict["avg_rank_score"] = float(avg_rank_score) if avg_rank_score else None
                    fragment_dict["ranking_count"] = ranking_count or 0

                # Add assets if requested
                if with_assets and fragment.assets:
                    fragment_dict["assets"] = [
                        {
                            "id": asset.id,
                            "fragment_id": asset.fragment_id,
                            "asset_type": asset.asset_type,
                            "created_by": asset.created_by,
                            "created_at": asset.created_at
                        }
                        for asset in fragment.assets
                    ]

                fragments_with_rankings.append(fragment_dict)

            return fragments_with_rankings

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
                "translation": learning_content.translation,
                "ipa": learning_content.ipa,
                "created_at": learning_content.created_at,
                "updated_at": learning_content.updated_at
            }]

    def set_fragment_ranking(self, fragment_id: int, ranking_data: FragmentRankingInput):
        with self.db_manager.get_session() as session:
            fragment = session.get(ContentFragment, fragment_id)
            if not fragment:
                raise HTTPException(status_code=404, detail="Fragment not found")

            # Get or create ranking
            existing_ranking = session.query(Ranking).filter(
                Ranking.fragment_id == fragment_id
            ).first()

            if existing_ranking:
                # Update existing ranking using setattr instead of direct assignment
                setattr(existing_ranking, "rank_score", ranking_data.rank_score)
                setattr(existing_ranking, "assessment_notes", ranking_data.assessment_notes)
                setattr(existing_ranking, "assessed_by", ranking_data.assessed_by)
                ranking_id = existing_ranking.id
            else:
                # Create new ranking
                new_ranking = Ranking(
                    fragment_id=fragment_id,
                    rank_score=ranking_data.rank_score,
                    assessment_notes=ranking_data.assessment_notes,
                    assessed_by=ranking_data.assessed_by
                )
                session.add(new_ranking)
                session.flush()
                ranking_id = new_ranking.id

            session.commit()

            # Retrieve the ranking after commit to get fresh data
            result = session.query(Ranking).get(ranking_id)

            if not result:
                raise HTTPException(status_code=404, detail="Ranking not found after creation")

            return {
                "id": result.id,
                "fragment_id": result.fragment_id,
                "rank_score": result.rank_score,
                "assessed_by": result.assessed_by,
                "assessment_notes": result.assessment_notes
            }
