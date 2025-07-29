## TODO: remove this file and it's usage
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

from database.manager import DatabaseManager
from models.database import AnkiCard, ContentFragment
from services.fragment_manager import FragmentManager
from services.fragment_asset_manager import FragmentAssetManager
from services.template_parser import TemplateParser

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ContentRenderer:
    """High-level service for rendering card content with fragments"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.fragment_manager = FragmentManager()
        self.asset_manager = FragmentAssetManager()
        self.template_parser = TemplateParser()

    def render_card_content(self,
                           card_id: int,
                           output_format: str = 'html',
                           include_assets: bool = True) -> Dict[str, Any]:
        """
        Render all content for a card (front, back, example)

        Args:
            card_id: ID of the card to render
            output_format: 'html', 'anki', 'text'
            include_assets: Whether to include asset data in output

        Returns:
            Dictionary with rendered content and metadata
        """
        with self.db_manager.get_session() as session:
            card = session.get(AnkiCard, card_id)
            if not card:
                return {'error': f'Card {card_id} not found'}

            result = {
                'card_id': card_id,
                'rendered_content': {},
                'fragments_used': [],
                'validation_issues': [],
                'render_timestamp': datetime.utcnow().isoformat()
            }

            # Render each field that might contain fragments
            fields_to_render = ['front_text', 'back_text', 'example']

            for field_name in fields_to_render:
                field_content = getattr(card, field_name, None)
                if field_content:
                    rendered_field = self._render_field_content(
                        field_content,
                        output_format,
                        card_id,
                        field_name
                    )
                    result['rendered_content'][field_name] = rendered_field

                    # Collect fragments used
                    if 'fragments_used' in rendered_field:
                        result['fragments_used'].extend(rendered_field['fragments_used'])

                    # Collect validation issues
                    if 'validation_issues' in rendered_field:
                        result['validation_issues'].extend(rendered_field['validation_issues'])

            # Remove duplicates from fragments_used
            result['fragments_used'] = list(set(result['fragments_used']))

            return result

    def _render_field_content(self,
                             field_content: str,
                             output_format: str,
                             card_id: int,
                             field_name: str) -> Dict[str, Any]:
        """Render content for a specific field"""
        # Validate template first
        validation = self.template_parser.validate_template(field_content)

        # Render the content
        rendered_content = self.template_parser.render_template(
            field_content,
            output_format,
            card_id,
            track_usage=True
        )

        # Extract fragments used
        fragments_used = self.template_parser.extract_fragments_from_template(field_content)

        return {
            'original_content': field_content,
            'rendered_content': rendered_content,
            'fragments_used': fragments_used,
            'validation_issues': validation['errors'] + validation['warnings'],
            'is_valid': validation['valid'],
            'field_name': field_name
        }

    def create_fragment_from_text(self,
                                 text: str,
                                 fragment_type: str,
                                 auto_generate_audio: bool = False,
                                 tts_service = None) -> int:
        """
        Create a new fragment from text and optionally generate audio

        Args:
            text: The fragment text
            fragment_type: Type of fragment
            auto_generate_audio: Whether to auto-generate audio
            tts_service: TTS service instance for audio generation

        Returns:
            Fragment ID
        """
        # Check if fragment already exists
        existing_fragment = self.fragment_manager.get_fragment_by_text(text, fragment_type)
        if existing_fragment:
            return existing_fragment['id']

        # Create new fragment
        fragment_id = self.fragment_manager.create_fragment(text, fragment_type)

        # Generate audio if requested
        if auto_generate_audio and tts_service and fragment_type in ['thai_word', 'thai_phrase']:
            try:
                result = tts_service.synthesize(text)
                audio_blob = result['audio']
                tts_model = result['tts_model']

                self.asset_manager.add_asset(
                    fragment_id=fragment_id,
                    asset_type='audio',
                    asset_data=audio_blob,
                    asset_metadata={'tts_model': tts_model},
                    created_by='system',
                    auto_activate=True
                )
            except Exception as e:
                # Log error but don't fail fragment creation
                print(f"Failed to generate audio for fragment {fragment_id}: {e}")

        return fragment_id

    def convert_legacy_examples(self,
                               card_id: int,
                               auto_generate_audio: bool = False,
                               tts_service = None) -> Dict[str, Any]:
        """
        Convert legacy example content with <strong> tags to fragment system

        Args:
            card_id: ID of the card to convert
            auto_generate_audio: Whether to auto-generate audio for fragments
            tts_service: TTS service instance for audio generation

        Returns:
            Conversion results
        """
        with self.db_manager.get_session() as session:
            card = session.get(AnkiCard, card_id)
            if not card or not card.example:
                return {'error': 'Card not found or no example content'}

            # Parse existing strong tags
            import re
            strong_pattern = re.compile(r'<strong>(.*?)</strong>', re.DOTALL)
            matches = list(strong_pattern.finditer(card.example))

            if not matches:
                return {'message': 'No <strong> tags found to convert'}

            # Create fragments and build new template
            conversion_results = {
                'fragments_created': [],
                'fragments_reused': [],
                'new_template': card.example
            }

            # Process matches from end to start to maintain positions
            for match in reversed(matches):
                strong_content = match.group(1).strip()

                # Determine fragment type (simple heuristic)
                if self._is_thai_text(strong_content):
                    fragment_type = 'thai_word' if len(strong_content.split()) == 1 else 'thai_phrase'
                else:
                    fragment_type = 'english_explanation'

                # Create or find fragment
                fragment_id = self.create_fragment_from_text(
                    strong_content,
                    fragment_type,
                    auto_generate_audio,
                    tts_service
                )

                # Check if this was a new fragment
                fragment_info = self.fragment_manager.get_fragment(fragment_id)
                if fragment_info:
                    if fragment_info['usage_count'] == 0:
                        conversion_results['fragments_created'].append(fragment_id)
                    else:
                        conversion_results['fragments_reused'].append(fragment_id)

                # Replace <strong> tag with fragment token
                fragment_token = f"{{{{fragment:{fragment_id}}}}}"
                conversion_results['new_template'] = (
                    conversion_results['new_template'][:match.start()] +
                    fragment_token +
                    conversion_results['new_template'][match.end():]
                )

            # Update card with new template
            card.example = conversion_results['new_template']
            session.commit()

            return conversion_results

    def _is_thai_text(self, text: str) -> bool:
        """Check if text contains Thai characters"""
        import re
        thai_pattern = re.compile(r'[\u0E00-\u0E7F]')
        return bool(thai_pattern.search(text))

    def get_card_fragments_summary(self, card_id: int) -> Dict[str, Any]:
        """Get summary of fragments used by a card"""
        with self.db_manager.get_session() as session:
            card = session.get(AnkiCard, card_id)
            if not card:
                return {'error': f'Card {card_id} not found'}

            # Extract fragments from all fields
            all_fragments = []
            fields_to_check = ['front_text', 'back_text', 'example']

            for field_name in fields_to_check:
                field_content = getattr(card, field_name, None)
                if field_content:
                    fragments = self.template_parser.extract_fragments_from_template(field_content)
                    for fragment_id in fragments:
                        all_fragments.append({
                            'fragment_id': fragment_id,
                            'field': field_name
                        })

            # Get fragment details
            unique_fragment_ids = list(set(f['fragment_id'] for f in all_fragments))
            fragment_details = []

            for fragment_id in unique_fragment_ids:
                fragment_info = self.fragment_manager.get_fragment(fragment_id)
                if fragment_info:
                    assets = self.asset_manager.get_active_assets(fragment_id)
                    fragment_details.append({
                        'fragment_id': fragment_id,
                        'text': fragment_info['text'],
                        'fragment_type': fragment_info['fragment_type'],
                        'assets_count': len(assets),
                        'fields_used': [f['field'] for f in all_fragments if f['fragment_id'] == fragment_id]
                    })

            return {
                'card_id': card_id,
                'total_fragments': len(unique_fragment_ids),
                'fragment_details': fragment_details,
                'usage_by_field': {
                    field: len([f for f in all_fragments if f['field'] == field])
                    for field in fields_to_check
                }
            }

    def preview_card_rendering(self, card_id: int) -> Dict[str, Any]:
        """Preview how a card would render in different formats"""
        formats = ['html', 'anki', 'text']
        previews = {}

        for format_name in formats:
            try:
                rendered = self.render_card_content(card_id, format_name)
                previews[format_name] = rendered
            except Exception as e:
                previews[format_name] = {'error': str(e)}

        return {
            'card_id': card_id,
            'previews': previews,
            'preview_timestamp': datetime.utcnow().isoformat()
        }
