"""
Export Service
Convert learning content to different output formats
"""
import logging
import hashlib
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from database.manager import DatabaseManager
from models.database import LearningContent, AnkiCard
from services.learning_content_service import LearningContentService
from services.content_renderer import ContentRenderer
from services.template_parser import TemplateParser
from sqlalchemy import text

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ExportService:
    """Service for rendering learning content to different formats (READ-ONLY - no database writes)"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.learning_service = LearningContentService()
        self.content_renderer = ContentRenderer()
        self.template_parser = TemplateParser()

    def needs_re_export(self, learning_content_id: int, target_format: str = 'anki') -> bool:
        """
        Check if learning content needs re-export due to changes

        Args:
            learning_content_id: ID of learning content
            target_format: Target export format ('anki', 'api', 'html')

        Returns:
            True if re-export needed
        """
        content = self.learning_service.get_content(learning_content_id)
        if not content:
            return False

        # Calculate content hash
        content_hash = self._calculate_content_hash(content)

        if target_format == 'anki':
            # Check anki_cards export_hash
            with self.db_manager.get_session() as session:
                card = session.execute(text("""
                    SELECT export_hash, last_exported_at
                    FROM anki_cards
                    WHERE learning_content_id = :content_id
                    LIMIT 1
                """), {'content_id': learning_content_id}).fetchone()

                if not card or card[0] != content_hash:
                    return True

                # Also check if content was updated after last export
                if card[1] and content['updated_at'] > card[1]:
                    return True

        return False

    def get_anki_content(self, learning_content_id: int) -> Dict[str, Any]:
        """
        Get learning content rendered for Anki format (no database updates)

        Args:
            learning_content_id: ID of learning content to render

        Returns:
            Dictionary with rendered content and export hash (no database writes)
        """
        content = self.learning_service.get_content(learning_content_id)
        if not content:
            return {'error': f'Learning content {learning_content_id} not found'}

        try:
            # Render templates to HTML using fragment system
            rendered_content = {}

            if content['front_template']:
                front_result = self.template_parser.render_template(
                    content['front_template'],
                    output_format='anki'
                )
                # render_template returns a string directly
                rendered_content['front'] = front_result

            if content['back_template']:
                back_result = self.template_parser.render_template(
                    content['back_template'],
                    output_format='anki'
                )
                rendered_content['back'] = back_result

            if content['example_template']:
                example_result = self.template_parser.render_template(
                    content['example_template'],
                    output_format='anki'
                )
                rendered_content['example'] = example_result

            # Calculate export hash
            content_hash = self._calculate_content_hash(content)

            # Return rendered content and hash - no database operations!
            return {
                'rendered_content': rendered_content,
                'export_hash': content_hash,
                'learning_content_id': learning_content_id,
                'content_title': content.get('title', ''),
                'content_type': content.get('content_type', '')
            }

        except Exception as e:

            logger.error(f"Error exporting learning content {learning_content_id} to Anki: {e}")
            return {'error': str(e)}

    def export_to_api_json(self, learning_content_id: int) -> Dict[str, Any]:
        """
        Export learning content to API JSON format (for mobile apps, web API)

        Args:
            learning_content_id: ID of learning content to export

        Returns:
            JSON-serializable dictionary
        """
        content = self.learning_service.get_content(learning_content_id)
        if not content:
            return {'error': f'Learning content {learning_content_id} not found'}

        try:
            # Render templates for mobile/API consumption
            rendered_templates = {}
            fragment_assets = {}

            for template_type in ['front_template', 'back_template', 'example_template']:
                template_content = content.get(template_type)
                if template_content:
                    # Parse and render for API
                    fragment_tokens = self.template_parser.parse_template(template_content)

                    # For API, we want structured data with fragment references
                    rendered_templates[template_type.replace('_template', '')] = {
                        'raw_template': template_content,
                        'fragment_tokens': fragment_tokens,  # parse_template returns list directly
                        'rendered_text': self.template_parser.render_template(
                            template_content,
                            output_format='text'
                        )  # render_template returns string directly
                    }

                    # Collect fragment assets for this template
                    for token in fragment_tokens:  # fragment_tokens is already a list
                        fragment_id = token['fragment_id']
                        if fragment_id not in fragment_assets:
                            fragment_data = self._get_fragment_assets(fragment_id)
                            if fragment_data:
                                fragment_assets[fragment_id] = fragment_data

            return {
                'id': content['id'],
                'title': content['title'],
                'content_type': content['content_type'],
                'language': content['language'],
                'difficulty_level': content['difficulty_level'],
                'tags': content['tags'],
                'templates': rendered_templates,
                'fragment_assets': fragment_assets,
                'metadata': content['content_metadata'],
                'created_at': content['created_at'].isoformat() if content['created_at'] else None,
                'updated_at': content['updated_at'].isoformat() if content['updated_at'] else None
            }

        except Exception as e:
            logger.error(f"Error exporting learning content {learning_content_id} to API JSON: {e}")
            return {'error': str(e)}

    def export_to_html(self, learning_content_id: int, standalone: bool = False) -> Dict[str, Any]:
        """
        Export learning content to HTML format (for web viewing, static sites)

        Args:
            learning_content_id: ID of learning content to export
            standalone: Whether to include full HTML page structure

        Returns:
            Dictionary with HTML content
        """
        content = self.learning_service.get_content(learning_content_id)
        if not content:
            return {'error': f'Learning content {learning_content_id} not found'}

        try:
            html_parts = []

            # Add title
            html_parts.append(f'<h1>{content["title"]}</h1>')

            # Add metadata
            if content['difficulty_level']:
                html_parts.append(f'<div class="difficulty">Difficulty: {content["difficulty_level"]}/5</div>')

            if content['tags']:
                tags_html = ', '.join([f'<span class="tag">{tag}</span>' for tag in content['tags']])
                html_parts.append(f'<div class="tags">Tags: {tags_html}</div>')

            # Render each template
            if content['front_template']:
                front_result = self.template_parser.render_template(
                    content['front_template'],
                    output_format='html'
                )
                html_parts.append(f'<div class="front-content">{front_result}</div>')  # direct string

            if content['back_template']:
                back_result = self.template_parser.render_template(
                    content['back_template'],
                    output_format='html'
                )
                html_parts.append(f'<div class="back-content">{back_result}</div>')  # direct string

            if content['example_template']:
                example_result = self.template_parser.render_template(
                    content['example_template'],
                    output_format='html'
                )
                html_parts.append(f'<div class="example-content">{example_result}</div>')  # direct string

            content_html = '\n'.join(html_parts)

            if standalone:
                # Wrap in full HTML page
                full_html = f"""
                <!DOCTYPE html>
                <html lang="{content['language']}">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>{content['title']}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                        .difficulty {{ color: #666; margin: 10px 0; }}
                        .tags {{ margin: 10px 0; }}
                        .tag {{ background: #e0e0e0; padding: 2px 6px; border-radius: 3px; margin-right: 5px; }}
                        .front-content, .back-content, .example-content {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; }}
                        .front-content {{ background: #f0f8ff; }}
                        .back-content {{ background: #f8f8f0; }}
                        .example-content {{ background: #fff0f8; }}
                    </style>
                </head>
                <body>
                    {content_html}
                </body>
                </html>
                """
                return {'html': full_html, 'standalone': True}
            else:
                return {'html': content_html, 'standalone': False}

        except Exception as e:
            logger.error(f"Error exporting learning content {learning_content_id} to HTML: {e}")
            return {'error': str(e)}

    def bulk_export(self,
                   content_ids: List[int],
                   export_format: str,
                   **format_options) -> Dict[str, Any]:
        """
        Export multiple learning content items in batch

        Args:
            content_ids: List of learning content IDs
            export_format: 'anki', 'api_json', 'html'
            **format_options: Format-specific options

        Returns:
            Dictionary with batch export results
        """
        results = {
            'successful': [],
            'failed': [],
            'total': len(content_ids)
        }

        for content_id in content_ids:
            try:
                if export_format == 'anki':
                    result = self.get_anki_content(content_id)
                elif export_format == 'api_json':
                    result = self.export_to_api_json(content_id)
                elif export_format == 'html':
                    result = self.export_to_html(content_id, **format_options)
                else:
                    raise ValueError(f"Unsupported export format: {export_format}")

                if 'error' in result:
                    results['failed'].append({'content_id': content_id, 'error': result['error']})
                else:
                    results['successful'].append({'content_id': content_id, 'result': result})

            except Exception as e:
                results['failed'].append({'content_id': content_id, 'error': str(e)})

        return results

    # keep it as reference
    def _calculate_content_hash(self, content: Dict[str, Any]) -> str:
        """Calculate hash of content for change detection"""
        # Include fields that affect export output
        hash_data = {
            'title': content.get('title', ''),
            'front_template': content.get('front_template', ''),
            'back_template': content.get('back_template', ''),
            'example_template': content.get('example_template', ''),
            'content_type': content.get('content_type', ''),
            'language': content.get('language', ''),
            'updated_at': content.get('updated_at', '').isoformat() if content.get('updated_at') else ''
        }

        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.md5(hash_string.encode()).hexdigest()

    def _get_fragment_assets(self, fragment_id: int) -> Optional[Dict[str, Any]]:
        """Get fragment assets for API export"""
        try:
            with self.db_manager.get_session() as session:
                result = session.execute(text("""
                    SELECT
                        cf.text,
                        cf.fragment_type,
                        fa.asset_type,
                        fa.asset_data,
                        fa.asset_metadata,
                        far.is_active
                    FROM content_fragments cf
                    LEFT JOIN fragment_assets fa ON cf.id = fa.fragment_id
                    LEFT JOIN fragment_asset_rankings far ON fa.id = far.asset_id
                    WHERE cf.id = :fragment_id
                    AND (far.is_active = 1 OR far.is_active IS NULL)
                """), {'fragment_id': fragment_id}).fetchall()

                if not result:
                    return None

                # Build fragment data
                fragment_data = {
                    'text': result[0][0],
                    'fragment_type': result[0][1],
                    'assets': []
                }

                for row in result:
                    if row[2]:  # has asset
                        fragment_data['assets'].append({
                            'asset_type': row[2],
                            'has_data': bool(row[3]),  # Don't include binary data in API
                            'metadata': row[4],
                            'is_active': bool(row[5])
                        })

                return fragment_data

        except Exception as e:
            logger.error(f"Error getting fragment assets for {fragment_id}: {e}")
            return None
