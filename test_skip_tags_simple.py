#!/usr/bin/env python3
"""
Simple test script for skip tag functionality - works with main api.py
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_skip_tags():
    """Test the skip tag functionality in main api.py"""
    print("🧪 Testing Skip Tag Functionality (Simple Version)")
    print("=" * 60)
    
    # Example learning content IDs to test
    test_content_ids = [1, 2, 3]
    
    print(f"📋 Testing with learning content IDs: {test_content_ids}")
    print()
    
    # 1. Check sync status overview
    print("1️⃣ Checking overall sync status...")
    try:
        response = requests.get(f"{BASE_URL}/sync/analyze-status")
        if response.status_code == 200:
            result = response.json()
            summary = result['summary']
            print(f"   Total learning content: {result['total_learning_content']}")
            print(f"   Synced: {summary['synced_count']}")
            print(f"   Skipped: {summary['skipped_count']}")
            print(f"   Needs update: {summary['needs_update_count']}")
            print(f"   Not synced: {summary['not_synced_count']}")
            print(f"   Failed: {summary['failed_count']}")
        else:
            print(f"   ❌ Error: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    
    # 2. Test specific cards for skip tags
    print("2️⃣ Testing specific cards for skip tags...")
    try:
        response = requests.post(f"{BASE_URL}/sync/test-skip-tags", 
                               json=test_content_ids)
        if response.status_code == 200:
            result = response.json()
            print(f"   Should skip: {len(result['summary']['should_skip'])}")
            print(f"   Should process: {len(result['summary']['should_process'])}")
            print(f"   No card found: {len(result['summary']['no_card'])}")
            
            if result['details']['should_skip']:
                print("   Cards with skip tags:")
                for card in result['details']['should_skip']:
                    print(f"     - ID {card['learning_content_id']}: {card['tags']}")
        else:
            print(f"   ❌ Error: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    
    # 3. Set a skip tag (if we have test content)
    if test_content_ids:
        content_id = test_content_ids[0]
        print(f"3️⃣ Setting skip tag on learning content {content_id}...")
        try:
            response = requests.post(f"{BASE_URL}/sync/set-skip-tag", 
                                   json={"learning_content_id": content_id, "skip_tag": "sync::skip"})
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ {result['message']}")
                print(f"   Updated tags: {result.get('updated_tags', result.get('current_tags'))}")
            else:
                print(f"   ❌ Error: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print()
    
    # 4. Test actual sync behavior
    if test_content_ids:
        content_id = test_content_ids[0]
        print(f"4️⃣ Testing sync with skip tag (content {content_id})...")
        try:
            response = requests.post(f"{BASE_URL}/sync/learning-content", 
                                   json={"learning_content_id": content_id, "deck_name": "test-deck"})
            if response.status_code == 200:
                result = response.json()
                status = result.get('status', 'unknown')
                print(f"   Status: {status}")
                if status == 'skipped':
                    print(f"   ✅ Card correctly skipped due to skip tag!")
                    print(f"   Tags: {result.get('tags', [])}")
                else:
                    print(f"   ⚠️  Expected 'skipped' status, got '{status}'")
            else:
                print(f"   ❌ Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print()
    print("✅ Simple skip tag testing completed!")
    print()
    print("🎯 All endpoints now in main api.py:")
    print("   GET  /sync/analyze-status")
    print("   POST /sync/test-skip-tags")
    print("   POST /sync/set-skip-tag")
    print("   POST /sync/remove-skip-tag")
    print("   POST /sync/batch-hash-check")
    print("   POST /sync/learning-content (improved with skip tags)")

if __name__ == "__main__":
    test_skip_tags() 
