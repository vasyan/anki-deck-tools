"""
Content hashing and change detection utilities for Anki synchronization
"""
import hashlib
import json
import logging
from typing import Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ContentChanges:
    """Represents detected changes in Anki note content"""
    user_modified_fields: List[str]
    user_modified_tags: bool
    field_diffs: Dict[str, Dict[str, Any]]  # field_name -> {original, current, changed}
    safe_to_update: bool

class ContentHasher:
    """Handles content hashing and change detection for Anki notes"""
    
    def __init__(self) -> None:
        self.encoding = 'utf-8'
    
    def hash_content(self, content: str) -> str:
        """Create a SHA256 hash of content"""
        return hashlib.sha256(content.encode(self.encoding)).hexdigest()
    
    def hash_fields(self, fields: Dict[str, str]) -> str:
        """Create a hash of all note fields combined"""
        # Sort fields by key for consistent hashing
        sorted_fields = sorted(fields.items())
        combined_content = json.dumps(sorted_fields, sort_keys=True, ensure_ascii=False)
        return self.hash_content(combined_content)
    
    def hash_tags(self, tags: List[str]) -> str:
        """Create a hash of tags (excluding sync tags)"""
        from utils.tag_manager import TagManager
        tag_manager = TagManager()
        user_tags = tag_manager.preserve_user_tags(tags)
        sorted_tags = sorted(user_tags)
        return self.hash_content(json.dumps(sorted_tags, sort_keys=True))
    
    def create_full_content_hash(self, fields: Dict[str, str], user_tags: List[str]) -> str:
        """Create a comprehensive hash of note content (fields + user tags)"""
        field_hash = self.hash_fields(fields)
        tag_hash = self.hash_tags(user_tags)
        combined_hash = f"{field_hash}|{tag_hash}"
        return self.hash_content(combined_hash)

class NoteChangeDetector:
    """Detects changes between expected and actual Anki note content"""
    
    def __init__(self) -> None:
        self.hasher = ContentHasher()
    
    def detect_field_changes(
        self, 
        expected_fields: Dict[str, str], 
        actual_fields: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect which fields have been modified by user
        
        Returns:
            Dict mapping field_name to {original, current, changed}
        """
        changes = {}
        
        # Check all expected fields
        for field_name, expected_value in expected_fields.items():
            actual_value = actual_fields.get(field_name, "")
            
            if expected_value.strip() != actual_value.strip():
                changes[field_name] = {
                    "original": expected_value,
                    "current": actual_value,
                    "changed": True
                }
                logger.debug(f"Field '{field_name}' changed: '{expected_value}' -> '{actual_value}'")
        
        # Check for new fields added by user
        for field_name, actual_value in actual_fields.items():
            if field_name not in expected_fields and actual_value.strip():
                changes[field_name] = {
                    "original": "",
                    "current": actual_value,
                    "changed": True
                }
                logger.debug(f"New field '{field_name}' added by user: '{actual_value}'")
        
        return changes
    
    def detect_user_modifications(
        self,
        expected_fields: Dict[str, str],
        expected_user_tags: List[str],
        actual_note_info: Dict[str, Any]
    ) -> ContentChanges:
        """
        Comprehensive change detection for an Anki note
        
        Args:
            expected_fields: Fields we expect the note to have
            expected_user_tags: User tags we expect (non-sync tags)
            actual_note_info: Current note info from AnkiConnect
            
        Returns:
            ContentChanges object with detailed change information
        """
        actual_fields = actual_note_info.get("fields", {})
        actual_tags = actual_note_info.get("tags", [])
        
        # Detect field changes
        field_diffs = self.detect_field_changes(expected_fields, actual_fields)
        user_modified_fields = [name for name, diff in field_diffs.items() if diff["changed"]]
        
        # Detect tag changes (user tags only)
        from utils.tag_manager import TagManager
        tag_manager = TagManager()
        actual_user_tags = tag_manager.preserve_user_tags(actual_tags)
        
        expected_user_tags_set = set(expected_user_tags)
        actual_user_tags_set = set(actual_user_tags)
        user_modified_tags = expected_user_tags_set != actual_user_tags_set
        
        if user_modified_tags:
            logger.debug(f"User tag changes: {expected_user_tags_set} vs {actual_user_tags_set}")
        
        # Determine if safe to update
        # Safe if no user modifications, or only sync tags changed
        safe_to_update = (
            len(user_modified_fields) == 0 and 
            not user_modified_tags
        )
        
        return ContentChanges(
            user_modified_fields=user_modified_fields,
            user_modified_tags=user_modified_tags,
            field_diffs=field_diffs,
            safe_to_update=safe_to_update
        )
    
    def should_skip_update(
        self, 
        changes: ContentChanges,
        force_update: bool = False,
        preserve_user_modifications: bool = True
    ) -> bool:
        """
        Determine whether to skip the update based on detected changes
        
        Args:
            changes: Detected content changes
            force_update: Whether to force update regardless of changes
            preserve_user_modifications: Whether to preserve user changes
            
        Returns:
            True if update should be skipped
        """
        if force_update:
            return False
            
        if preserve_user_modifications:
            return not changes.safe_to_update
            
        return False