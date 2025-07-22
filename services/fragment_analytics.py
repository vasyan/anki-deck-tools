"""
Fragment Analytics Service
On-demand analysis of fragment usage without maintaining separate tables
"""
from typing import Dict, List, Any
from sqlalchemy import text
from database.manager import DatabaseManager


class FragmentAnalytics:
    """Service for analyzing fragment usage on-demand"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
    
    def get_fragment_dependencies(self, fragment_id: int) -> List[Dict[str, Any]]:
        """
        Get all learning content that depends on a specific fragment
        
        Args:
            fragment_id: ID of fragment to analyze
            
        Returns:
            List of learning content items using this fragment
        """
        with self.db_manager.get_session() as session:
            pattern = f'%{{{{fragment:{fragment_id}}}}}%'
            
            results = session.execute(text('''
                SELECT id, title, content_type, language,
                       CASE WHEN front_template LIKE :pattern THEN 'front' ELSE NULL END as front_usage,
                       CASE WHEN back_template LIKE :pattern THEN 'back' ELSE NULL END as back_usage,
                       CASE WHEN example_template LIKE :pattern THEN 'example' ELSE NULL END as example_usage,
                       created_at, updated_at
                FROM learning_content 
                WHERE front_template LIKE :pattern 
                   OR back_template LIKE :pattern 
                   OR example_template LIKE :pattern
                ORDER BY updated_at DESC
            '''), {'pattern': pattern}).fetchall()
            
            dependencies = []
            for row in results:
                content_id, title, content_type, language, front, back, example, created_at, updated_at = row
                contexts = [ctx for ctx in [front, back, example] if ctx]
                
                dependencies.append({
                    'learning_content_id': content_id,
                    'title': title,
                    'content_type': content_type,
                    'language': language,
                    'contexts': contexts,
                    'created_at': created_at,
                    'updated_at': updated_at
                })
            
            return dependencies
    
    def get_fragment_usage_summary(self, fragment_id: int) -> Dict[str, Any]:
        """
        Get summary statistics for fragment usage
        
        Args:
            fragment_id: ID of fragment to analyze
            
        Returns:
            Summary statistics and usage details
        """
        dependencies = self.get_fragment_dependencies(fragment_id)
        
        if not dependencies:
            return {
                'fragment_id': fragment_id,
                'is_used': False,
                'total_learning_content': 0,
                'contexts': [],
                'content_types': [],
                'languages': []
            }
        
        # Aggregate statistics
        contexts = set()
        content_types = set()
        languages = set()
        
        for dep in dependencies:
            contexts.update(dep['contexts'])
            content_types.add(dep['content_type'])
            languages.add(dep['language'])
        
        return {
            'fragment_id': fragment_id,
            'is_used': True,
            'total_learning_content': len(dependencies),
            'contexts': list(contexts),
            'content_types': list(content_types),
            'languages': list(languages),
            'dependencies': dependencies
        }
    
    def find_unused_fragments(self) -> List[Dict[str, Any]]:
        """
        Find fragments that are not used in any learning content
        
        Returns:
            List of unused fragments
        """
        with self.db_manager.get_session() as session:
            # Get all fragments
            all_fragments = session.execute(text('''
                SELECT id, text, fragment_type, created_at
                FROM content_fragments
                ORDER BY created_at DESC
            ''')).fetchall()
            
            unused_fragments = []
            
            for fragment in all_fragments:
                fragment_id, fragment_text, fragment_type, created_at = fragment
                
                # Check if this fragment is used
                dependencies = self.get_fragment_dependencies(fragment_id)
                
                if not dependencies:
                    unused_fragments.append({
                        'fragment_id': fragment_id,
                        'text': fragment_text,
                        'fragment_type': fragment_type,
                        'created_at': created_at
                    })
            
            return unused_fragments
    
    def get_most_used_fragments(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get fragments ordered by usage frequency
        
        Args:
            limit: Maximum number of fragments to return
            
        Returns:
            List of most used fragments with usage counts
        """
        with self.db_manager.get_session() as session:
            # Get all fragments
            all_fragments = session.execute(text('''
                SELECT id, text, fragment_type
                FROM content_fragments
            ''')).fetchall()
            
            fragment_usage = []
            
            for fragment in all_fragments:
                fragment_id, fragment_text, fragment_type = fragment
                dependencies = self.get_fragment_dependencies(fragment_id)
                
                if dependencies:  # Only include used fragments
                    fragment_usage.append({
                        'fragment_id': fragment_id,
                        'text': fragment_text,
                        'fragment_type': fragment_type,
                        'usage_count': len(dependencies),
                        'contexts': list(set(ctx for dep in dependencies for ctx in dep['contexts']))
                    })
            
            # Sort by usage count and return top fragments
            fragment_usage.sort(key=lambda x: x['usage_count'], reverse=True)
            return fragment_usage[:limit]
    
    def analyze_content_fragment_usage(self, learning_content_id: int) -> Dict[str, Any]:
        """
        Analyze which fragments a specific learning content uses
        
        Args:
            learning_content_id: ID of learning content to analyze
            
        Returns:
            Analysis of fragment usage in this content
        """
        import re
        
        with self.db_manager.get_session() as session:
            # Get learning content
            result = session.execute(text('''
                SELECT id, title, front_template, back_template, example_template
                FROM learning_content
                WHERE id = :content_id
            '''), {'content_id': learning_content_id}).fetchone()
            
            if not result:
                return {'error': f'Learning content {learning_content_id} not found'}
            
            content_id, title, front_template, back_template, example_template = result
            
            # Extract fragment tokens from each template
            fragment_pattern = r'\{\{fragment:(\d+)\}\}'
            
            fragments_used = {
                'front': [],
                'back': [],
                'example': []
            }
            
            if front_template:
                fragments_used['front'] = [int(match) for match in re.findall(fragment_pattern, front_template)]
            
            if back_template:
                fragments_used['back'] = [int(match) for match in re.findall(fragment_pattern, back_template)]
            
            if example_template:
                fragments_used['example'] = [int(match) for match in re.findall(fragment_pattern, example_template)]
            
            # Get unique fragment IDs
            all_fragment_ids = set()
            for context_fragments in fragments_used.values():
                all_fragment_ids.update(context_fragments)
            
            return {
                'learning_content_id': content_id,
                'title': title,
                'fragments_by_context': fragments_used,
                'total_unique_fragments': len(all_fragment_ids),
                'fragment_ids': list(all_fragment_ids)
            } 
