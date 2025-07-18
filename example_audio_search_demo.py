#!/usr/bin/env python3
"""
Demonstration script for the new search functionality in ExampleAudioManager.

This script shows how to use the search methods to avoid unnecessary TTS API calls
by finding and reusing existing audio examples.
"""

import asyncio
from services.example_audio_manager import ExampleAudioManager
from services.text_to_voice import TextToSpeechService
from database.manager import DatabaseManager
from models.database import AnkiCard
from sqlalchemy.orm import Session


async def demonstrate_search_functionality():
    """Demonstrate the various search methods available in ExampleAudioManager"""
    
    audio_manager = ExampleAudioManager()
    tts_service = TextToSpeechService()
    db_manager = DatabaseManager()
    
    print("=== Audio Search Functionality Demo ===\n")
    
    # Example Thai texts that might be found in card examples
    thai_texts = [
        "สวัสดี",      # Hello
        "ขอบคุณ",      # Thank you
        "ยินดีต้อนรับ",  # Welcome
        "ลาก่อน",      # Goodbye
        "ขอโทษ",       # Sorry
        "ไม่เป็นไร",    # No problem
        "ช่วยได้ไหม",   # Can you help?
        "อร่อย",       # Delicious
        "สบายดี",      # How are you?
        "ได้"          # Can/Yes
    ]
    
    print("1. Testing find_reusable_audio() method:")
    print("   This method finds exact matches for Thai text\n")
    
    for text in thai_texts[:5]:  # Test first 5 texts
        existing_audio = audio_manager.find_reusable_audio(text)
        if existing_audio:
            print(f"   ✓ Found existing audio for '{text}' (ID: {existing_audio['audio_id']})")
        else:
            print(f"   ✗ No existing audio found for '{text}' - would need TTS generation")
    
    print("\n2. Testing batch_find_or_create_audio() method:")
    print("   This method efficiently processes multiple texts at once\n")
    
    batch_results = audio_manager.batch_find_or_create_audio(thai_texts)
    
    existing_count = sum(1 for result in batch_results if not result['needs_generation'])
    needs_generation_count = sum(1 for result in batch_results if result['needs_generation'])
    
    print(f"   📊 Batch processing results:")
    print(f"   - {existing_count} texts have existing audio (no TTS needed)")
    print(f"   - {needs_generation_count} texts need TTS generation")
    print(f"   - Potential TTS API calls saved: {existing_count}")
    
    print("\n   Details:")
    for result in batch_results:
        if result['needs_generation']:
            print(f"   🔄 '{result['text']}' needs generation")
        else:
            audio_id = result['existing_audio']['audio_id']
            print(f"   ✓ '{result['text']}' can reuse audio ID {audio_id}")
    
    print("\n3. Testing search_audio_examples() method:")
    print("   This method supports pattern matching for flexible searches\n")
    
    # Search for greetings
    greeting_patterns = ["สวัสดี", "ยินดี", "ลาก่อน"]
    greeting_results = audio_manager.search_audio_examples(
        text_patterns=greeting_patterns,
        limit=10
    )
    
    print(f"   🔍 Search results for greeting patterns {greeting_patterns}:")
    for audio in greeting_results:
        print(f"   - '{audio['example_text']}' (used {audio['usage_count']} times)")
    
    # Search for commonly used words
    common_patterns = ["ขอบคุณ", "ขอโทษ", "ได้"]
    common_results = audio_manager.search_audio_examples(
        text_patterns=common_patterns,
        limit=10
    )
    
    print(f"\n   🔍 Search results for common patterns {common_patterns}:")
    for audio in common_results:
        print(f"   - '{audio['example_text']}' (used {audio['usage_count']} times)")
    
    print("\n4. Audio bank overview:")
    print("   Current state of the audio example bank\n")
    
    audio_bank = audio_manager.get_audio_bank(limit=20)
    
    if audio_bank:
        print(f"   📚 Audio bank contains {len(audio_bank)} examples (showing first 20):")
        for i, audio in enumerate(audio_bank[:10], 1):
            print(f"   {i:2d}. '{audio['example_text']}' (used {audio['usage_count']} times)")
        
        if len(audio_bank) > 10:
            print(f"   ... and {len(audio_bank) - 10} more")
    else:
        print("   📚 Audio bank is empty - no audio examples found")
    
    print("\n5. Usage statistics for popular audio:")
    print("   Understanding which audio examples are most reused\n")
    
    # Show stats for some audio examples
    for audio in audio_bank[:5]:
        stats = audio_manager.get_audio_usage_stats(audio['audio_id'])
        if stats:
            print(f"   📊 '{stats['example_text']}' statistics:")
            print(f"       - Used by {stats['used_by_cards']} cards")
            print(f"       - Card IDs: {stats['card_ids']}")
            print(f"       - TTS Model: {stats['tts_model']}")
            print("")


async def demonstrate_practical_usage():
    """Show practical usage patterns that would be used in real code"""
    
    print("\n=== Practical Usage Examples ===\n")
    
    audio_manager = ExampleAudioManager()
    
    # Scenario 1: Processing a card with multiple Thai examples
    print("1. Processing a card with multiple Thai examples:")
    print("   (This simulates what happens in example_audio_cli.py)\n")
    
    # Simulated Thai texts extracted from a card's example HTML
    card_thai_texts = ["สวัสดี", "ขอบคุณครับ", "ยินดีต้อนรับ", "ลาก่อน"]
    
    print(f"   📋 Found {len(card_thai_texts)} Thai texts in card example:")
    for i, text in enumerate(card_thai_texts, 1):
        print(f"   {i}. {text}")
    
    # Check which ones already have audio
    batch_results = audio_manager.batch_find_or_create_audio(card_thai_texts)
    
    tts_calls_needed = 0
    audio_reused = 0
    
    print(f"\n   🔍 Processing results:")
    for i, result in enumerate(batch_results, 1):
        if result['needs_generation']:
            print(f"   {i}. '{result['text']}' - needs TTS generation")
            tts_calls_needed += 1
        else:
            print(f"   {i}. '{result['text']}' - reusing existing audio")
            audio_reused += 1
    
    print(f"\n   📊 Summary:")
    print(f"   - TTS API calls needed: {tts_calls_needed}")
    print(f"   - Audio examples reused: {audio_reused}")
    print(f"   - API calls saved: {audio_reused}")
    
    # Scenario 2: Smart audio generation with caching
    print("\n2. Smart audio generation with automatic caching:")
    print("   (This shows how the new system avoids duplicate audio)\n")
    
    # Simulate generating audio for texts that might already exist
    new_texts = ["สวัสดี", "สวัสดีครับ", "ขอบคุณ", "ขอบคุณค่ะ"]
    
    for text in new_texts:
        existing = audio_manager.find_reusable_audio(text)
        if existing:
            print(f"   ✓ '{text}' - found existing audio (ID: {existing['audio_id']})")
        else:
            print(f"   🔄 '{text}' - would generate new audio")
    
    # Scenario 3: Finding similar audio examples
    print("\n3. Finding similar audio examples:")
    print("   (This shows pattern-based searching)\n")
    
    search_patterns = ["สวัสดี", "ขอบคุณ"]
    similar_audio = audio_manager.search_audio_examples(
        text_patterns=search_patterns,
        limit=5
    )
    
    print(f"   🔍 Found {len(similar_audio)} similar audio examples:")
    for audio in similar_audio:
        print(f"   - '{audio['example_text']}' (used {audio['usage_count']} times)")


async def show_performance_benefits():
    """Demonstrate the performance benefits of the new search system"""
    
    print("\n=== Performance Benefits ===\n")
    
    audio_manager = ExampleAudioManager()
    
    # Get some statistics
    audio_bank = audio_manager.get_audio_bank(limit=100)
    
    if not audio_bank:
        print("   📊 No audio bank data available for performance analysis")
        return
    
    total_audio_examples = len(audio_bank)
    total_usage_count = sum(audio['usage_count'] for audio in audio_bank)
    
    # Calculate potential savings
    reused_count = sum(audio['usage_count'] - 1 for audio in audio_bank if audio['usage_count'] > 1)
    
    print(f"   📈 Audio Bank Performance Statistics:")
    print(f"   - Total unique audio examples: {total_audio_examples}")
    print(f"   - Total audio usage across all cards: {total_usage_count}")
    print(f"   - Audio reuse instances: {reused_count}")
    print(f"   - TTS API calls saved: {reused_count}")
    print(f"   - Storage efficiency: {reused_count} duplicate files avoided")
    
    # Show most reused examples
    most_reused = sorted(audio_bank, key=lambda x: x['usage_count'], reverse=True)[:5]
    
    print(f"\n   🏆 Most reused audio examples:")
    for i, audio in enumerate(most_reused, 1):
        if audio['usage_count'] > 1:
            print(f"   {i}. '{audio['example_text']}' - used {audio['usage_count']} times")
    
    # Calculate theoretical time savings (assuming 1 second per TTS call)
    print(f"\n   ⏱️  Estimated time savings:")
    print(f"   - TTS calls avoided: {reused_count}")
    print(f"   - Time saved (assuming 1s per TTS call): {reused_count} seconds")
    print(f"   - Time saved (minutes): {reused_count / 60:.1f} minutes")


if __name__ == "__main__":
    print("🎵 Audio Search Functionality Demonstration")
    print("=" * 50)
    
    try:
        asyncio.run(demonstrate_search_functionality())
        asyncio.run(demonstrate_practical_usage())
        asyncio.run(show_performance_benefits())
        
        print("\n" + "=" * 50)
        print("✅ Demo completed successfully!")
        print("\nKey benefits of the new search system:")
        print("• 🔍 Smart audio reuse reduces TTS API calls")
        print("• 💾 Eliminates duplicate audio storage")
        print("• ⚡ Faster processing through batch operations")
        print("• 📊 Usage tracking for optimization")
        print("• 🎯 Flexible pattern-based searching")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc() 
