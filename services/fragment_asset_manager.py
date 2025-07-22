"""
Fragment Asset Management Service
Handles assets, rankings, and quality assessment for content fragments
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from database.manager import DatabaseManager
from models.database import ContentFragment, FragmentAsset, FragmentAssetRanking


class FragmentAssetManager:
    """Service for managing fragment assets and their rankings"""
    
    SUPPORTED_ASSET_TYPES = ['audio', 'image', 'video']
    
    def __init__(self):
        self.db_manager = DatabaseManager()
    
    def add_asset(self, 
                  fragment_id: int, 
                  asset_type: str, 
                  asset_data: bytes, 
                  asset_metadata: Dict = None, 
                  created_by: str = None,
                  auto_activate: bool = True) -> int:
        """Add a new asset to a fragment"""
        if asset_type not in self.SUPPORTED_ASSET_TYPES:
            raise ValueError(f"Invalid asset type: {asset_type}. Must be one of: {self.SUPPORTED_ASSET_TYPES}")
        
        if not asset_data:
            raise ValueError("Asset data cannot be empty")
        
        with self.db_manager.get_session() as session:
            # Check if fragment exists
            fragment = session.get(ContentFragment, fragment_id)
            if not fragment:
                raise ValueError(f"Fragment {fragment_id} not found")
            
            # Create asset
            asset = FragmentAsset(
                fragment_id=fragment_id,
                asset_type=asset_type,
                asset_data=asset_data,
                asset_metadata=asset_metadata or {},
                created_by=created_by
            )
            session.add(asset)
            session.flush()  # Get the asset ID
            
            # Create ranking record
            ranking = FragmentAssetRanking(
                fragment_id=fragment_id,
                asset_id=asset.id,
                is_active=auto_activate,
                rank_score=0.0,
                assessed_by=created_by
            )
            session.add(ranking)
            
            # If auto_activate is True, deactivate other assets of the same type
            if auto_activate:
                session.query(FragmentAssetRanking).filter(
                    and_(
                        FragmentAssetRanking.fragment_id == fragment_id,
                        FragmentAssetRanking.asset_id != asset.id,
                        FragmentAssetRanking.is_active == True
                    )
                ).filter(
                    FragmentAssetRanking.asset_id.in_(
                        session.query(FragmentAsset.id).filter(
                            and_(
                                FragmentAsset.fragment_id == fragment_id,
                                FragmentAsset.asset_type == asset_type
                            )
                        )
                    )
                ).update({FragmentAssetRanking.is_active: False})
            
            session.commit()
            return asset.id
    
    def get_fragment_assets(self, fragment_id: int, asset_type: str = None, active_only: bool = False) -> List[Dict]:
        """Get all assets for a fragment"""
        with self.db_manager.get_session() as session:
            query = session.query(FragmentAsset, FragmentAssetRanking).join(
                FragmentAssetRanking, FragmentAsset.id == FragmentAssetRanking.asset_id
            ).filter(FragmentAsset.fragment_id == fragment_id)
            
            if asset_type:
                query = query.filter(FragmentAsset.asset_type == asset_type)
            
            if active_only:
                query = query.filter(FragmentAssetRanking.is_active == True)
            
            query = query.order_by(desc(FragmentAssetRanking.rank_score))
            
            results = query.all()
            
            return [{
                'asset_id': asset.id,
                'fragment_id': asset.fragment_id,
                'asset_type': asset.asset_type,
                'asset_data': asset.asset_data,
                'asset_metadata': asset.asset_metadata,
                'created_at': asset.created_at,
                'created_by': asset.created_by,
                'is_active': ranking.is_active,
                'rank_score': ranking.rank_score,
                'assessed_by': ranking.assessed_by,
                'assessment_notes': ranking.assessment_notes,
                'ranking_updated_at': ranking.updated_at
            } for asset, ranking in results]
    
    def get_active_assets(self, fragment_id: int, asset_type: str = None) -> List[Dict]:
        """Get only active assets for a fragment"""
        return self.get_fragment_assets(fragment_id, asset_type, active_only=True)
    
    def set_asset_active(self, asset_id: int, is_active: bool = True) -> bool:
        """Set an asset as active or inactive"""
        with self.db_manager.get_session() as session:
            asset = session.get(FragmentAsset, asset_id)
            if not asset:
                return False
            
            ranking = session.query(FragmentAssetRanking).filter(
                FragmentAssetRanking.asset_id == asset_id
            ).first()
            
            if not ranking:
                return False
            
            # If activating, deactivate others of the same type
            if is_active:
                session.query(FragmentAssetRanking).filter(
                    and_(
                        FragmentAssetRanking.fragment_id == asset.fragment_id,
                        FragmentAssetRanking.asset_id != asset_id,
                        FragmentAssetRanking.is_active == True
                    )
                ).filter(
                    FragmentAssetRanking.asset_id.in_(
                        session.query(FragmentAsset.id).filter(
                            and_(
                                FragmentAsset.fragment_id == asset.fragment_id,
                                FragmentAsset.asset_type == asset.asset_type
                            )
                        )
                    )
                ).update({FragmentAssetRanking.is_active: False})
            
            ranking.is_active = is_active
            ranking.updated_at = datetime.utcnow()
            session.commit()
            return True
    
    def assess_asset(self, 
                     asset_id: int, 
                     rank_score: float, 
                     assessed_by: str, 
                     assessment_notes: str = None,
                     set_active: bool = None) -> bool:
        """Assess an asset quality and update ranking"""
        with self.db_manager.get_session() as session:
            ranking = session.query(FragmentAssetRanking).filter(
                FragmentAssetRanking.asset_id == asset_id
            ).first()
            
            if not ranking:
                return False
            
            ranking.rank_score = rank_score
            ranking.assessed_by = assessed_by
            ranking.assessment_notes = assessment_notes
            ranking.updated_at = datetime.utcnow()
            
            if set_active is not None:
                ranking.is_active = set_active
                
                # If setting as active, deactivate others of the same type
                if set_active:
                    asset = session.get(FragmentAsset, asset_id)
                    if asset:
                        session.query(FragmentAssetRanking).filter(
                            and_(
                                FragmentAssetRanking.fragment_id == asset.fragment_id,
                                FragmentAssetRanking.asset_id != asset_id,
                                FragmentAssetRanking.is_active == True
                            )
                        ).filter(
                            FragmentAssetRanking.asset_id.in_(
                                session.query(FragmentAsset.id).filter(
                                    and_(
                                        FragmentAsset.fragment_id == asset.fragment_id,
                                        FragmentAsset.asset_type == asset.asset_type
                                    )
                                )
                            )
                        ).update({FragmentAssetRanking.is_active: False})
            
            session.commit()
            return True
    
    def delete_asset(self, asset_id: int) -> bool:
        """Delete an asset and its ranking"""
        with self.db_manager.get_session() as session:
            asset = session.get(FragmentAsset, asset_id)
            if not asset:
                return False
            
            # Delete rankings first (should cascade, but being explicit)
            session.query(FragmentAssetRanking).filter(
                FragmentAssetRanking.asset_id == asset_id
            ).delete()
            
            session.delete(asset)
            session.commit()
            return True
    
    def find_reusable_asset(self, fragment_text: str, asset_type: str, fragment_type: str = None) -> Optional[Dict]:
        """Find an existing asset that can be reused for similar content"""
        with self.db_manager.get_session() as session:
            query = session.query(FragmentAsset, FragmentAssetRanking, ContentFragment).join(
                ContentFragment, FragmentAsset.fragment_id == ContentFragment.id
            ).join(
                FragmentAssetRanking, FragmentAsset.id == FragmentAssetRanking.asset_id
            ).filter(
                and_(
                    ContentFragment.text == fragment_text,
                    FragmentAsset.asset_type == asset_type,
                    FragmentAssetRanking.is_active == True
                )
            )
            
            if fragment_type:
                query = query.filter(ContentFragment.fragment_type == fragment_type)
            
            query = query.order_by(desc(FragmentAssetRanking.rank_score))
            
            result = query.first()
            if not result:
                return None
            
            asset, ranking, fragment = result
            
            return {
                'asset_id': asset.id,
                'fragment_id': asset.fragment_id,
                'asset_type': asset.asset_type,
                'asset_data': asset.asset_data,
                'asset_metadata': asset.asset_metadata,
                'created_at': asset.created_at,
                'created_by': asset.created_by,
                'is_active': ranking.is_active,
                'rank_score': ranking.rank_score,
                'fragment_text': fragment.text,
                'fragment_type': fragment.fragment_type
            }
    
    def get_asset_statistics(self) -> Dict[str, Any]:
        """Get statistics about fragment assets"""
        with self.db_manager.get_session() as session:
            # Total assets
            total_assets = session.query(FragmentAsset).count()
            
            # Assets by type
            asset_type_counts = {}
            for asset_type in self.SUPPORTED_ASSET_TYPES:
                count = session.query(FragmentAsset).filter(
                    FragmentAsset.asset_type == asset_type
                ).count()
                asset_type_counts[asset_type] = count
            
            # Assets needing assessment (no rankings)
            assets_needing_assessment = session.query(FragmentAsset).filter(
                ~FragmentAsset.rankings.any()
            ).count()
            
            # Active assets
            active_assets = session.query(FragmentAssetRanking).filter(
                FragmentAssetRanking.is_active == True
            ).count()
            
            return {
                'total_assets': total_assets,
                'asset_type_counts': asset_type_counts,
                'assets_needing_assessment': assets_needing_assessment,
                'active_assets': active_assets
            }
    
    def get_assets_needing_assessment(self, limit: int = 20) -> List[Dict]:
        """Get assets that need quality assessment"""
        with self.db_manager.get_session() as session:
            query = session.query(FragmentAsset, FragmentAssetRanking, ContentFragment).join(
                FragmentAssetRanking, FragmentAsset.id == FragmentAssetRanking.asset_id
            ).join(
                ContentFragment, FragmentAsset.fragment_id == ContentFragment.id
            ).filter(
                or_(
                    FragmentAssetRanking.rank_score == 0,
                    FragmentAssetRanking.assessed_by.is_(None)
                )
            ).order_by(FragmentAsset.created_at.desc()).limit(limit)
            
            results = query.all()
            
            return [{
                'asset_id': asset.id,
                'fragment_id': asset.fragment_id,
                'fragment_text': fragment.text,
                'fragment_type': fragment.fragment_type,
                'asset_type': asset.asset_type,
                'asset_metadata': asset.asset_metadata,
                'created_at': asset.created_at,
                'created_by': asset.created_by,
                'current_rank_score': ranking.rank_score,
                'is_active': ranking.is_active
            } for asset, ranking, fragment in results] 
