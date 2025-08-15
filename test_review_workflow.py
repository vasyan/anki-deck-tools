#!/usr/bin/env python3
"""
Test script for the new review workflow functionality
"""

import requests

BASE_URL = "http://localhost:8000"

def test_next_review_endpoint():
    """Test the /learning-content/next-review endpoint"""
    print("\n=== Testing Next Review Endpoint ===")
    
    # Test getting next review content
    response = requests.get(f"{BASE_URL}/learning-content/next-review")
    
    if response.status_code == 404:
        print("✓ No content available for review (all reviewed recently or no content with fragments)")
        return None
    elif response.status_code == 200:
        content = response.json()
        print(f"✓ Got next review content: ID={content['id']}, Title={content['title']}")
        print(f"  Last reviewed at: {content.get('last_review_at', 'Never')}")
        return content['id']
    else:
        print(f"✗ Unexpected status code: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def test_concurrent_review():
    """Test that concurrent users don't get the same content"""
    print("\n=== Testing Concurrent Review Protection ===")
    
    # Get first review item
    response1 = requests.get(f"{BASE_URL}/learning-content/next-review")
    if response1.status_code == 200:
        content1 = response1.json()
        print(f"User 1 got: ID={content1['id']}")
        
        # Immediately try to get another review item
        response2 = requests.get(f"{BASE_URL}/learning-content/next-review")
        if response2.status_code == 200:
            content2 = response2.json()
            print(f"User 2 got: ID={content2['id']}")
            
            if content1['id'] != content2['id']:
                print("✓ Different content served to concurrent users")
            else:
                print("✗ Same content served to concurrent users (should be different)")
        elif response2.status_code == 404:
            print("✓ No more content available for User 2 (all locked or reviewed)")
        else:
            print(f"✗ Unexpected response for User 2: {response2.status_code}")
    else:
        print("No content available for testing")

def test_review_page():
    """Test the admin review page loads correctly"""
    print("\n=== Testing Admin Review Page ===")
    
    response = requests.get(f"{BASE_URL}/admin/learning-content/review")
    if response.status_code == 200:
        print("✓ Review page loads successfully")
        # Check if it contains expected elements
        if "Finish Review" in response.text or "finishReview" in response.text:
            print("✓ Review mode UI elements present")
        else:
            print("? Review mode UI elements not detected in HTML")
    else:
        print(f"✗ Failed to load review page: {response.status_code}")

def test_time_based_unlock():
    """Test that content becomes available again after 5 minutes"""
    print("\n=== Testing Time-Based Unlock (Simulated) ===")
    print("Note: In production, content locked for 5 minutes after review")
    print("This would require waiting or database manipulation to test fully")
    
    # Get the SQL query to check
    print("SQL to manually test in database:")
    print("  UPDATE learning_content SET last_review_at = datetime('now', '-6 minutes') WHERE id = ?;")
    print("  Then check if that content appears in next review")

def main():
    print("Starting Review Workflow Tests")
    print("=" * 50)
    print(f"Testing against: {BASE_URL}")
    print("Make sure the server is running!")
    
    try:
        # Test 1: Basic next review functionality
        test_next_review_endpoint()
        
        # Test 2: Concurrent review protection
        test_concurrent_review()
        
        # Test 3: Admin review page
        test_review_page()
        
        # Test 4: Time-based unlock (informational)
        test_time_based_unlock()
        
        print("\n" + "=" * 50)
        print("Tests completed!")
        print("\nTo manually test the full workflow:")
        print("1. Go to http://localhost:8000/admin/learning-content")
        print("2. Click 'Start Review' button")
        print("3. Rate some fragments")
        print("4. Click 'Finish Review' to get next item")
        print("5. Press Enter key to quickly move to next review")
        
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to server. Make sure it's running on port 8000")
    except Exception as e:
        print(f"✗ Test failed with error: {e}")

if __name__ == "__main__":
    main()