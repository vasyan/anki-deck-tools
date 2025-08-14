"""
Smart tag management utility for Anki card synchronization
"""
import re
import logging
from typing import List, Dict, Optional, Literal

logger = logging.getLogger(__name__)

SyncStatus = Literal["success", "skipped", "error", "new", "updated", "failed", "partial"]

class TagManager:
    """Manages tags during Anki card synchronization with smart preservation logic"""
    
    def __init__(self, sync_tag_prefix: str = "sync::"):
        self.sync_tag_prefix = sync_tag_prefix
        self.sync_pattern = re.compile(f"^{re.escape(sync_tag_prefix)}")
    
    def is_sync_tag(self, tag: str) -> bool:
        """Check if a tag is a sync-related tag"""
        return bool(self.sync_pattern.match(tag))
    
    def clean_sync_tags(self, existing_tags: List[str]) -> List[str]:
        """Remove all sync tags from the existing tag list"""
        cleaned_tags = [tag for tag in existing_tags if not self.is_sync_tag(tag)]
        logger.debug(f"Cleaned sync tags: {existing_tags} -> {cleaned_tags}")
        return cleaned_tags
    
    def preserve_user_tags(self, existing_tags: List[str]) -> List[str]:
        """Extract user-defined tags (non-sync tags) from existing tags"""
        user_tags = self.clean_sync_tags(existing_tags)
        logger.debug(f"Preserved user tags: {user_tags}")
        return user_tags
    
    def create_sync_tag(self, status: SyncStatus) -> str:
        """Create a sync tag for the given status"""
        return f"{self.sync_tag_prefix}{status}"
    
    def create_sync_tags(self, statuses: List[SyncStatus]) -> List[str]:
        """Create multiple sync tags"""
        return [self.create_sync_tag(status) for status in statuses]
    
    def merge_tags(
        self, 
        existing_tags: List[str], 
        sync_status: SyncStatus,
        additional_sync_tags: Optional[List[SyncStatus]] = None
    ) -> List[str]:
        """
        Smart tag merging: preserve user tags and add sync status tags
        
        Args:
            existing_tags: Current tags on the Anki note
            sync_status: Primary sync status (success, error, etc.)
            additional_sync_tags: Optional additional sync status tags
            
        Returns:
            Merged tag list with user tags preserved and sync tags updated
        """
        # Preserve all user tags (non-sync tags)
        user_tags = self.preserve_user_tags(existing_tags)
        
        # Create sync tags
        sync_tags = [self.create_sync_tag(sync_status)]
        if additional_sync_tags:
            sync_tags.extend(self.create_sync_tags(additional_sync_tags))
        
        # Combine and deduplicate
        merged_tags = list(dict.fromkeys(user_tags + sync_tags))
        
        logger.info(f"Tag merge: {existing_tags} + {sync_status} -> {merged_tags}")
        return merged_tags
    
    def get_sync_status_from_tags(self, tags: List[str]) -> Optional[SyncStatus]:
        """Extract the current sync status from tags"""
        sync_statuses: List[SyncStatus] = []
        for tag in tags:
            if self.is_sync_tag(tag):
                status = tag.replace(self.sync_tag_prefix, "")
                if status in ["success", "skipped", "error", "new", "updated", "failed", "partial"]:
                    sync_statuses.append(status)  # type: ignore
        
        # Return the most recent/relevant status
        status_priority: List[SyncStatus] = ["error", "failed", "partial", "success", "updated", "new", "skipped"]
        for status in status_priority:
            if status in sync_statuses:
                return status
        
        return None
    
    def analyze_tag_changes(self, old_tags: List[str], new_tags: List[str]) -> Dict[str, List[str]]:
        """
        Analyze what changed between old and new tag sets
        
        Returns:
            Dictionary with 'added', 'removed', 'user_added', 'user_removed', 'sync_changed'
        """
        old_set = set(old_tags)
        new_set = set(new_tags)
        
        old_user_tags = set(self.preserve_user_tags(old_tags))
        new_user_tags = set(self.preserve_user_tags(new_tags))
        
        old_sync_tags = old_set - old_user_tags
        new_sync_tags = new_set - new_user_tags
        
        return {
            "added": list(new_set - old_set),
            "removed": list(old_set - new_set),
            "user_added": list(new_user_tags - old_user_tags),
            "user_removed": list(old_user_tags - new_user_tags),
            "sync_changed": list((new_sync_tags - old_sync_tags) | (old_sync_tags - new_sync_tags))
        }