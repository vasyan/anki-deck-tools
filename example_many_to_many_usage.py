#!/usr/bin/env python3
"""
Example script demonstrating the many-to-many relationship between AnkiCard and ExampleAudio.

This script shows how to:
1. Create audio examples and associate them with cards
2. Reuse audio examples across multiple cards
3. Manage the audio example "bank"
4. Update existing code to work with the new relationship
"""

import asyncio
from services.example_audio_manager import ExampleAudioManager
from services.card_service import CardService
from services.text_to_voice import TextToSpeechService


async def demonstrate_many_to_many():
    """Demonstrate the many-to-many relationship features"""
    
    audio_manager = ExampleAudioManager()
    card_service = CardService()
    tts_service = TextToSpeechService()
    
    print("=== Many-to-Many Relationship Demo ===\n")
    
    # 1. Create some example audio
    print("1. Creating example audio...")
    thai_texts = ["สวัสดี", "ขอบคุณ", "ยินดีต้อนรับ"]
    audio_examples = []
    
    for text in thai_texts:
        try:
            # Generate TTS audio
            result = tts_service.synthesize(text)
            audio_blob = result["audio"]
            tts_model = result["tts_model"]
            
            # Create audio example (not associated with any card yet)
            audio_id, _ = audio_manager.create_audio_and_associate(
                card_id=1,  # Assuming card 1 exists
                example_text=text,
                audio_blob=audio_blob,
                tts_model=tts_model
            )
            
            audio_examples.append({
                "audio_id": audio_id,
                "text": text,
                "tts_model": tts_model
            })
            print(f"✓ Created audio example: {text} (ID: {audio_id})")
            
        except Exception as e:
            print(f"✗ Failed to create audio for '{text}': {e}")
    
    # 2. Demonstrate reusing audio across multiple cards
    print("\n2. Reusing audio across multiple cards...")
    
    # Assuming we have cards with IDs 1, 2, 3
    card_ids = [1, 2, 3]
    
    for card_id in card_ids:
        print(f"\nAssociating audio with card {card_id}:")
        
        # Associate the first two audio examples with this card
        for i, audio_example in enumerate(audio_examples[:2]):
            association_id = audio_manager.associate_audio_with_card(
                card_id=card_id,
                audio_id=audio_example["audio_id"],
                order_index=i
            )
            print(f"  ✓ Associated '{audio_example['text']}' with card {card_id}")
    
    # 3. Show usage statistics
    print("\n3. Audio usage statistics...")
    for audio_example in audio_examples:
        stats = audio_manager.get_audio_usage_stats(audio_example["audio_id"])
        print(f"'{stats['example_text']}' is used by {stats['used_by_cards']} cards: {stats['card_ids']}")
    
    # 4. Demonstrate finding reusable audio
    print("\n4. Finding reusable audio...")
    for text in ["สวัสดี", "สวัสดีครับ", "ขอบคุณ"]:
        existing_audio = audio_manager.find_reusable_audio(text)
        if existing_audio:
            print(f"✓ Found reusable audio for '{text}': ID {existing_audio['audio_id']}")
        else:
            print(f"✗ No existing audio found for '{text}'")
    
    # 5. Show audio bank
    print("\n5. Audio bank contents...")
    audio_bank = audio_manager.get_audio_bank(limit=10)
    for audio in audio_bank:
        print(f"  Audio ID {audio['audio_id']}: '{audio['example_text']}' (used {audio['usage_count']} times)")
    
    # 6. Demonstrate reordering
    print("\n6. Reordering audio examples for a card...")
    card_id = 1
    current_audios = audio_manager.get_card_audio_examples(card_id)
    
    if len(current_audios) > 1:
        print(f"Current order for card {card_id}:")
        for audio in current_audios:
            print(f"  {audio['order_index']}: {audio['example_text']}")
        
        # Reverse the order
        new_order = [audio['audio_id'] for audio in reversed(current_audios)]
        audio_manager.reorder_card_audio_examples(card_id, new_order)
        
        print(f"Reordered audio examples for card {card_id}")
        
        # Show new order
        updated_audios = audio_manager.get_card_audio_examples(card_id)
        print("New order:")
        for audio in updated_audios:
            print(f"  {audio['order_index']}: {audio['example_text']}")


async def migrate_existing_code_example():
    """Example of how to migrate existing code to use the new relationship"""
    
    print("\n=== Code Migration Example ===\n")
    
    audio_manager = ExampleAudioManager()
    
    # OLD WAY (using direct CardService methods):
    # card_service = CardService()
    # audios = await card_service.get_example_audios(card_id=1)
    
    # NEW WAY (using ExampleAudioManager):
    card_id = 1
    audios = audio_manager.get_card_audio_examples(card_id)
    print(f"Found {len(audios)} audio examples for card {card_id}")
    
    for audio in audios:
        print(f"  - {audio['example_text']} (Audio ID: {audio['audio_id']})")
    
    # OLD WAY (creating new audio tied to specific card):
    # audio_id = await card_service.add_example_audio(card_id, "test text", audio_blob)
    
    # NEW WAY (check for existing audio first, then associate):
    example_text = "ทดสอบ"
    existing_audio = audio_manager.find_reusable_audio(example_text)
    
    if existing_audio:
        print(f"Reusing existing audio for '{example_text}'")
        audio_manager.associate_audio_with_card(card_id, existing_audio['audio_id'])
    else:
        print(f"Creating new audio for '{example_text}'")
        # You would generate the audio_blob here
        # audio_id, assoc_id = audio_manager.create_audio_and_associate(
        #     card_id, example_text, audio_blob, tts_model
        # )


def show_benefits():
    """Show the benefits of the many-to-many relationship"""
    
    print("\n=== Benefits of Many-to-Many Relationship ===\n")
    
    benefits = [
        "🔄 **Audio Reuse**: Same audio can be used across multiple cards",
        "💾 **Storage Efficiency**: Duplicate audio files are eliminated",
        "🎯 **Flexible Associations**: Easy to add/remove audio from cards",
        "📊 **Usage Tracking**: See which audio examples are most popular",
        "🗂️ **Audio Bank**: Centralized collection of all audio examples",
        "⚡ **Performance**: Faster generation by reusing existing audio",
        "🔧 **Maintenance**: Easy to update audio examples globally"
    ]
    
    for benefit in benefits:
        print(f"  {benefit}")
    
    print("\n=== Migration Steps ===\n")
    
    steps = [
        "1. 📋 **Run Migration Script**: Execute `python migrate_to_many_to_many.py`",
        "2. 🔄 **Update Code**: Replace direct CardService calls with ExampleAudioManager",
        "3. 🧪 **Test Thoroughly**: Ensure all functionality works correctly",
        "4. 🧹 **Clean Up**: Remove backup tables when confident",
        "5. 📈 **Optimize**: Use find_reusable_audio() to improve efficiency"
    ]
    
    for step in steps:
        print(f"  {step}")


if __name__ == "__main__":
    print("Starting many-to-many relationship demonstration...")
    
    try:
        # Show benefits first
        show_benefits()
        
        # Run the demonstrations
        asyncio.run(demonstrate_many_to_many())
        asyncio.run(migrate_existing_code_example())
        
        print("\n✅ Demo completed successfully!")
        print("\nNext steps:")
        print("1. Run the migration script: python migrate_to_many_to_many.py")
        print("2. Update your existing code to use ExampleAudioManager")
        print("3. Test the new functionality")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc() 
