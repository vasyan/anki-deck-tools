"""
Template Parser Service
Handles parsing and rendering of {{fragment:123}} tokens in card content
"""
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from database.manager import DatabaseManager
from models.database import ContentFragment, FragmentAsset, FragmentAssetRanking


class TemplateParser:
    """Service for parsing and rendering fragment templates"""
    
    # Regex pattern to match {{fragment:123}} tokens
    FRAGMENT_TOKEN_PATTERN = re.compile(r'\{\{fragment:(\d+)\}\}')
    
    def __init__(self):
        self.db_manager = DatabaseManager()
    
    def parse_template(self, template_content: str) -> List[Dict]:
        """Parse template content and extract fragment tokens"""
        if not template_content:
            return []
        
        tokens = []
        for match in self.FRAGMENT_TOKEN_PATTERN.finditer(template_content):
            fragment_id = int(match.group(1))
            tokens.append({
                'fragment_id': fragment_id,
                'token': match.group(0),
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        return tokens
    
    def render_template(self, 
                       template_content: str, 
                       output_format: str = 'html',
                       card_id: int = None,
                       track_usage: bool = True) -> str:
        """
        Render template content by replacing fragment tokens with actual content
        
        Args:
            template_content: The template content with {{fragment:123}} tokens
            output_format: 'html', 'anki', 'text'
            card_id: Optional card ID for tracking usage
            track_usage: Whether to track fragment usage
        """
        if not template_content:
            return template_content
        
        tokens = self.parse_template(template_content)
        if not tokens:
            return template_content
        
        # Get fragment data for all tokens
        fragment_ids = [token['fragment_id'] for token in tokens]
        fragment_data = self._get_fragments_with_assets(fragment_ids)
        
        # Track usage if requested
        if track_usage and card_id:
            self._track_fragment_usage(card_id, fragment_ids, 'template_render')
        
        # Replace tokens from end to start to maintain positions
        result = template_content
        for token in reversed(tokens):
            fragment_id = token['fragment_id']
            fragment_info = fragment_data.get(fragment_id)
            
            if fragment_info:
                rendered_content = self._render_fragment(fragment_info, output_format)
            else:
                # Fragment not found, keep token or show error
                rendered_content = f"[Fragment {fragment_id} not found]"
            
            result = result[:token['start_pos']] + rendered_content + result[token['end_pos']:]
        
        return result
    
    def _get_fragments_with_assets(self, fragment_ids: List[int]) -> Dict[int, Dict]:
        """Get fragments and their active assets"""
        fragments = {}
        
        with self.db_manager.get_session() as session:
            # Get fragments
            query = session.query(ContentFragment).filter(
                ContentFragment.id.in_(fragment_ids)
            )
            
            for fragment in query.all():
                fragments[fragment.id] = {
                    'fragment': fragment,
                    'assets': []
                }
            
            # Get active assets for these fragments
            asset_query = session.query(FragmentAsset, FragmentAssetRanking).join(
                FragmentAssetRanking, FragmentAsset.id == FragmentAssetRanking.asset_id
            ).filter(
                FragmentAsset.fragment_id.in_(fragment_ids),
                FragmentAssetRanking.is_active == True
            )
            
            for asset, ranking in asset_query.all():
                if asset.fragment_id in fragments:
                    fragments[asset.fragment_id]['assets'].append({
                        'asset': asset,
                        'ranking': ranking
                    })
        
        return fragments
    
    def _render_fragment(self, fragment_info: Dict, output_format: str) -> str:
        """Render a single fragment with its assets"""
        fragment = fragment_info['fragment']
        assets = fragment_info['assets']
        
        # Base text content
        text_content = fragment.text
        
        if output_format == 'text':
            return text_content
        
        # HTML/Anki rendering
        if fragment.fragment_type == 'thai_word' or fragment.fragment_type == 'thai_phrase':
            html_content = f"<strong>{text_content}</strong>"
        else:
            html_content = text_content
        
        # Add assets
        for asset_info in assets:
            asset = asset_info['asset']
            
            if asset.asset_type == 'audio':
                if output_format == 'anki':
                    # Use Anki sound format
                    audio_filename = f"fragment_{fragment.id}_{asset.id}.mp3"
                    html_content += f"[sound:{audio_filename}]"
                elif output_format == 'html':
                    # Use HTML audio tag
                    audio_data_url = f"data:audio/mp3;base64,{self._encode_asset_data(asset.asset_data)}"
                    html_content += f'<audio controls style="margin-left: 5px; width: 100px; height: 20px;"><source src="{audio_data_url}" type="audio/mp3"></audio>'
            
            elif asset.asset_type == 'image':
                if output_format in ['anki', 'html']:
                    image_data_url = f"data:image/jpeg;base64,{self._encode_asset_data(asset.asset_data)}"
                    html_content += f'<img src="{image_data_url}" style="max-width: 100px; margin-left: 5px;" alt="Fragment image">'
        
        return html_content
    
    def _encode_asset_data(self, asset_data: bytes) -> str:
        """Encode asset data to base64 for data URLs"""
        import base64
        return base64.b64encode(asset_data).decode('utf-8')
    

    
    def validate_template(self, template_content: str) -> Dict[str, Any]:
        """Validate template content and return validation results"""
        tokens = self.parse_template(template_content)
        
        if not tokens:
            return {
                'valid': True,
                'tokens': [],
                'errors': [],
                'warnings': []
            }
        
        fragment_ids = [token['fragment_id'] for token in tokens]
        fragment_data = self._get_fragments_with_assets(fragment_ids)
        
        errors = []
        warnings = []
        
        for token in tokens:
            fragment_id = token['fragment_id']
            
            if fragment_id not in fragment_data:
                errors.append(f"Fragment {fragment_id} not found")
            else:
                fragment_info = fragment_data[fragment_id]
                if not fragment_info['assets']:
                    warnings.append(f"Fragment {fragment_id} has no assets")
        
        return {
            'valid': len(errors) == 0,
            'tokens': tokens,
            'errors': errors,
            'warnings': warnings,
            'fragment_count': len(set(fragment_ids))
        }
    
    def extract_fragments_from_template(self, template_content: str) -> List[int]:
        """Extract unique fragment IDs from template content"""
        tokens = self.parse_template(template_content)
        return list(set(token['fragment_id'] for token in tokens))
    
    def replace_fragment_in_template(self, template_content: str, old_fragment_id: int, new_fragment_id: int) -> str:
        """Replace one fragment ID with another in template content"""
        old_token = f"{{{{fragment:{old_fragment_id}}}}}"
        new_token = f"{{{{fragment:{new_fragment_id}}}}}"
        return template_content.replace(old_token, new_token)
    
    def get_fragment_usage_stats(self, fragment_id: int) -> Dict[str, Any]:
        """Get usage statistics for a specific fragment (on-demand analysis)"""
        from sqlalchemy import text
        
        with self.db_manager.get_session() as session:
            # Find learning content using this fragment
            pattern = f'%{{{{fragment:{fragment_id}}}}}%'
            
            results = session.execute(text('''
                SELECT id, title, content_type,
                       CASE WHEN front_template LIKE :pattern THEN 'front' ELSE NULL END as front_usage,
                       CASE WHEN back_template LIKE :pattern THEN 'back' ELSE NULL END as back_usage,
                       CASE WHEN example_template LIKE :pattern THEN 'example' ELSE NULL END as example_usage
                FROM learning_content 
                WHERE front_template LIKE :pattern 
                   OR back_template LIKE :pattern 
                   OR example_template LIKE :pattern
            '''), {'pattern': pattern}).fetchall()
            
            # Process results
            contexts = set()
            content_types = set()
            usage_details = []
            
            for row in results:
                content_id, title, content_type, front, back, example = row
                used_contexts = [ctx for ctx in [front, back, example] if ctx]
                contexts.update(used_contexts)
                content_types.add(content_type)
                
                usage_details.append({
                    'learning_content_id': content_id,
                    'title': title,
                    'content_type': content_type,
                    'contexts': used_contexts
                })
            
            return {
                'fragment_id': fragment_id,
                'total_learning_content': len(results),
                'contexts': list(contexts),
                'content_types': list(content_types),
                'usage_details': usage_details
            } 
