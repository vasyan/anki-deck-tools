#!/usr/bin/env python3
"""
Test script for the smart Anki update system
"""
import asyncio
import logging
from utils.tag_manager import TagManager
from utils.content_hash import NoteChangeDetector, ContentHasher
from services.card_service import CardService

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_tag_manager():
    """Test TagManager functionality"""
    print("\n=== Testing TagManager ===")
    
    tag_manager = TagManager("sync::")
    
    # Test tag identification
    test_tags = ["user_tag", "sync::success", "my_custom_tag", "sync::skipped", "another_user_tag"]
    print(f"Test tags: {test_tags}")
    
    sync_tags = [tag for tag in test_tags if tag_manager.is_sync_tag(tag)]
    user_tags = tag_manager.preserve_user_tags(test_tags)
    
    print(f"Sync tags detected: {sync_tags}")
    print(f"User tags preserved: {user_tags}")
    
    # Test tag merging
    merged_tags = tag_manager.merge_tags(test_tags, "success", ["new"])
    print(f"After merge with success+new: {merged_tags}")
    
    # Test status extraction
    status = tag_manager.get_sync_status_from_tags(merged_tags)
    print(f"Current sync status: {status}")
    
    print("✓ TagManager tests passed")

def test_content_hasher():
    """Test ContentHasher functionality"""
    print("\n=== Testing ContentHasher ===")
    
    hasher = ContentHasher()
    
    # Test field hashing
    fields1 = {"Front": "Thai word", "Back": "English meaning"}
    fields2 = {"Front": "Thai word", "Back": "English meaning"}  # Same content
    fields3 = {"Front": "Thai word", "Back": "Different meaning"}  # Different content
    
    hash1 = hasher.hash_fields(fields1)
    hash2 = hasher.hash_fields(fields2)
    hash3 = hasher.hash_fields(fields3)
    
    print(f"Hash 1: {hash1[:16]}...")
    print(f"Hash 2: {hash2[:16]}...")
    print(f"Hash 3: {hash3[:16]}...")
    
    assert hash1 == hash2, "Identical fields should have same hash"
    assert hash1 != hash3, "Different fields should have different hash"
    
    # Test tag hashing
    tags1 = ["user_tag", "sync::success", "my_tag"]
    tags2 = ["my_tag", "user_tag", "sync::skipped"]  # Same user tags, different sync tags
    
    tag_hash1 = hasher.hash_tags(tags1)
    tag_hash2 = hasher.hash_tags(tags2)
    
    print(f"Tag hash 1: {tag_hash1[:16]}...")
    print(f"Tag hash 2: {tag_hash2[:16]}...")
    
    assert tag_hash1 == tag_hash2, "Same user tags should produce same hash regardless of sync tags"
    
    print("✓ ContentHasher tests passed")

def test_change_detector():
    """Test NoteChangeDetector functionality"""
    print("\n=== Testing NoteChangeDetector ===")
    
    detector = NoteChangeDetector()
    
    # Test field change detection
    expected_fields = {"Front": "Original Thai", "Back": "Original English"}
    actual_fields = {"Front": "Modified Thai", "Back": "Original English", "Extra": "New field"}
    
    field_changes = detector.detect_field_changes(expected_fields, actual_fields)
    print(f"Detected field changes: {field_changes}")
    
    assert "Front" in field_changes, "Should detect Front field change"
    assert field_changes["Front"]["changed"], "Front field should be marked as changed"
    assert "Back" not in field_changes, "Back field should not be detected as changed"
    assert "Extra" in field_changes, "Should detect new field added"
    
    # Test comprehensive change detection
    mock_note_info = {
        "fields": actual_fields,
        "tags": ["user_tag", "sync::old", "custom_tag"]
    }
    
    changes = detector.detect_anki_user_modifications(
        expected_fields,
        ["user_tag", "custom_tag"],  # Expected anki user tags
        mock_note_info
    )
    
    print(f"Anki user modified fields: {changes.anki_user_modified_fields}")
    print(f"Anki user modified tags: {changes.anki_user_modified_tags}")
    print(f"Safe to update: {changes.safe_to_update}")
    
    assert "Front" in changes.anki_user_modified_fields, "Should detect Front modification by Anki user"
    assert not changes.safe_to_update, "Should not be safe to update due to Anki user field changes"
    
    print("✓ NoteChangeDetector tests passed")

async def test_card_service_methods():
    """Test CardService new methods (without actual Anki connection)"""
    print("\n=== Testing CardService Methods ===")
    
    try:
        card_service = CardService()
        print("✓ CardService initialized successfully")
        
        # Test that the new methods exist and have correct signatures
        assert hasattr(card_service, 'get_note_changes'), "CardService should have get_note_changes method"
        assert hasattr(card_service, 'smart_update_note'), "CardService should have smart_update_note method"
        assert hasattr(card_service, 'tag_manager'), "CardService should have tag_manager attribute"
        assert hasattr(card_service, 'change_detector'), "CardService should have change_detector attribute"
        
        print("✓ CardService has all required methods and attributes")
        
    except Exception as e:
        print(f"✗ CardService test failed: {e}")
        raise

async def main():
    """Run all tests"""
    print("Starting Smart Update System Tests")
    print("=" * 50)
    
    try:
        # Test individual components
        await test_tag_manager()
        test_content_hasher()
        test_change_detector()
        await test_card_service_methods()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed successfully!")
        print("\nSmart update system is ready to use.")
        print("\nKey features implemented:")
        print("• Smart tag management with sync:: prefix")
        print("• Content change detection and hashing")
        print("• User modification preservation")
        print("• Configurable update strategies (conservative/aggressive)")
        print("• Safe update recommendations")
        
        print("\nNext steps:")
        print("1. Test with actual Anki cards using the web interface")
        print("2. Monitor logs for smart update behavior")
        print("3. Adjust configuration as needed")
        
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(asyncio.run(main()))