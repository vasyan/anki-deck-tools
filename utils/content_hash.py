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
    """
    Represents detected changes in Anki note content
    
    This class tracks modifications made by Anki users (learners) to exported cards.
    There are two types of users in this system:
    
    1. **Content Designer/Admin**: Manages learning content in the database and exports cards
    2. **Anki User/Learner**: Studies with imported cards and may manually edit them in Anki
    
    The "anki_user" terminology refers to the learner who studies with the cards,
    not the content designer who manages the database.
    
    Flow:
    - Content designer creates/updates content in database
    - System exports cards to Anki via AnkiConnect
    - Anki user imports and may customize cards (add notes, fix typos, etc.)
    - When content designer updates database, system detects anki user modifications
    - Smart update preserves anki user customizations while applying content updates
    """
    anki_user_modified_fields: List[str]  # Fields modified by the Anki learner
    anki_user_modified_tags: bool  # Whether Anki learner modified non-sync tags
    field_diffs: Dict[str, Dict[str, Any]]  # field_name -> {original, current, changed}
    safe_to_update: bool  # True if no anki user modifications detected

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
    
    def _extract_field_value(self, field_data: Any) -> str:
        """
        Extract field value from AnkiConnect format or simple string format
        
        Args:
            field_data: Either a string or dict in format {"value": str, "order": int}
            
        Returns:
            The field value as a string
        """
        if isinstance(field_data, dict):
            return field_data.get("value", "")
        elif isinstance(field_data, str):
            return field_data
        else:
            logger.warning(f"Unexpected field data type: {type(field_data)}, value: {field_data}")
            return str(field_data) if field_data is not None else ""

    def detect_field_changes(
        self,
        expected_fields: Dict[str, str],
        actual_fields: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect which fields have been modified by user

        Returns:
            Dict mapping field_name to {original, current, changed}
        """
        changes = {}

        print(f"expected_fields: { type(expected_fields)}")

        # Check all expected fields
        for field_name, expected_value in expected_fields.items():
            actual_field_data = actual_fields.get(field_name, "")
            actual_value = self._extract_field_value(actual_field_data)

            if expected_value.strip() != actual_value.strip():
                changes[field_name] = {
                    "original": expected_value,
                    "current": actual_value,
                    "changed": True
                }
                logger.debug(f"Field '{field_name}' changed: '{expected_value}' -> '{actual_value}'")

        # Check for new fields added by user
        for field_name, actual_field_data in actual_fields.items():
            actual_value = self._extract_field_value(actual_field_data)
            if field_name not in expected_fields and actual_value.strip():
                changes[field_name] = {
                    "original": "",
                    "current": actual_value,
                    "changed": True
                }
                logger.debug(f"New field '{field_name}' added by user: '{actual_value}'")

        return changes

    def detect_anki_user_modifications(
        self,
        expected_fields: Dict[str, str],
        expected_anki_user_tags: List[str],
        actual_note_info: Dict[str, Any]
    ) -> ContentChanges:
        """
        Detect modifications made by Anki users (learners) to exported cards
        
        This method compares what we expect the card to contain (from our database)
        with what's actually in Anki. Differences indicate the Anki user has
        customized the card.
        
        Example scenario:
        - Expected (from database): {"Front": "สวัสดี", "Back": "Hello"}
        - Actual (in Anki): {"Front": "สวัสดี (greeting)", "Back": "Hello - common"}
        - Result: anki_user_modified_fields = ["Front", "Back"]

        Args:
            expected_fields: Fields we expect based on database content
            expected_anki_user_tags: Non-sync tags we expect (usually empty)
            actual_note_info: Current note info from AnkiConnect

        Returns:
            ContentChanges object with detailed modification information
        """
        actual_fields = actual_note_info.get("fields", {})
        actual_tags = actual_note_info.get("tags", [])

        # Detect field changes made by Anki user
        field_diffs = self.detect_field_changes(expected_fields, actual_fields)
        anki_user_modified_fields = [name for name, diff in field_diffs.items() if diff["changed"]]

        # Detect tag changes (non-sync tags only) made by Anki user
        from utils.tag_manager import TagManager
        tag_manager = TagManager()
        actual_anki_user_tags = tag_manager.preserve_user_tags(actual_tags)

        expected_anki_user_tags_set = set(expected_anki_user_tags)
        actual_anki_user_tags_set = set(actual_anki_user_tags)
        anki_user_modified_tags = expected_anki_user_tags_set != actual_anki_user_tags_set

        if anki_user_modified_tags:
            logger.debug(f"Anki user tag changes: {expected_anki_user_tags_set} vs {actual_anki_user_tags_set}")

        # Determine if safe to update
        # Safe if no anki user modifications detected
        safe_to_update = (
            len(anki_user_modified_fields) == 0 and
            not anki_user_modified_tags
        )

        return ContentChanges(
            anki_user_modified_fields=anki_user_modified_fields,
            anki_user_modified_tags=anki_user_modified_tags,
            field_diffs=field_diffs,
            safe_to_update=safe_to_update
        )

    def should_skip_update(
        self,
        changes: ContentChanges,
        force_update: bool = False,
        preserve_anki_user_modifications: bool = True
    ) -> bool:
        """
        Determine whether to skip the update based on detected Anki user changes
        
        This respects modifications made by Anki users (learners) to preserve
        their personal customizations while allowing content updates.

        Args:
            changes: Detected content changes
            force_update: Whether to force update regardless of anki user changes
            preserve_anki_user_modifications: Whether to preserve anki user changes

        Returns:
            True if update should be skipped to preserve anki user modifications
        """
        if force_update:
            return False

        if preserve_anki_user_modifications:
            return not changes.safe_to_update

        return False
