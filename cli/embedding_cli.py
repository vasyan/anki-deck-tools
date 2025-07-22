#!/usr/bin/env python3
"""
Standalone CLI for embedding operations
"""

import asyncio
import sys
from pathlib import Path

# Add current directory to path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from embedding_processor import EmbeddingManager, EmbeddingConfig

async def main():
    """CLI entry point for embedding operations"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Anki Vector Embedding Operations")
    
    # Model configuration
    parser.add_argument("--model", type=str, default="all-MiniLM-L6-v2", 
                       help="Sentence transformer model name")
    parser.add_argument("--batch-size", type=int, default=32, 
                       help="Batch size for processing")
    parser.add_argument("--device", type=str, default="auto", 
                       choices=["auto", "cpu", "cuda", "mps"],
                       help="Device for model inference")
    
    # Operations
    parser.add_argument("--generate", action="store_true", 
                       help="Generate embeddings")
    parser.add_argument("--deck", type=str, 
                       help="Target specific deck (use with --generate)")
    parser.add_argument("--all-decks", action="store_true", 
                       help="Target all decks (use with --generate)")
    parser.add_argument("--force", action="store_true", 
                       help="Force regenerate existing embeddings")
    
    # Search operations
    parser.add_argument("--search", type=str, 
                       help="Search for similar cards with query text")
    parser.add_argument("--search-deck", type=str, 
                       help="Limit search to specific deck")
    parser.add_argument("--embedding-type", type=str, default="combined", 
                       choices=["front", "back", "combined"],
                       help="Embedding type for search")
    parser.add_argument("--top-k", type=int, default=10, 
                       help="Number of results for search")
    parser.add_argument("--threshold", type=float, default=0.5, 
                       help="Similarity threshold for search")
    
    # Statistics
    parser.add_argument("--stats", action="store_true", 
                       help="Show embedding statistics")
    
    args = parser.parse_args()
    
    if not any([args.generate, args.search, args.stats]):
        parser.print_help()
        print("\nPlease specify an operation: --generate, --search, or --stats")
        return
    
    # Create configuration
    config = EmbeddingConfig(
        model_name=args.model,
        batch_size=args.batch_size,
        device=args.device
    )
    
    # Initialize manager
    print(f"Initializing embedding manager with model: {config.model_name}")
    manager = EmbeddingManager(config)
    
    if not await manager.initialize():
        print("❌ Failed to initialize embedding manager")
        return
    
    print("✅ Embedding manager initialized successfully")
    
    try:
        # Generate embeddings
        if args.generate:
            if args.all_decks:
                print("🔄 Generating embeddings for all decks...")
                result = await manager.generate_embeddings_for_all_decks(force_regenerate=args.force)
                
                print(f"\n📊 Results Summary:")
                print(f"   Processed decks: {result['processed_decks']}")
                print(f"   Successful: {result['total_results']['successful']}")
                print(f"   Failed: {result['total_results']['failed']}")
                print(f"   Skipped: {result['total_results']['skipped']}")
                print(f"   Total time: {result['total_results']['total_processing_time']:.2f}s")
                
            elif args.deck:
                print(f"🔄 Generating embeddings for deck: {args.deck}")
                result = await manager.generate_embeddings_for_deck(args.deck, force_regenerate=args.force)
                
                print(f"\n📊 Results for '{args.deck}':")
                print(f"   Cards processed: {result['cards_processed']}")
                print(f"   Successful: {result['results']['successful']}")
                print(f"   Failed: {result['results']['failed']}")
                print(f"   Skipped: {result['results']['skipped']}")
                print(f"   Processing time: {result['results']['total_processing_time']:.2f}s")
                
            else:
                print("❌ Please specify --deck <name> or --all-decks")
        
        # Search similar cards
        elif args.search:
            print(f"🔍 Searching for: '{args.search}'")
            results = await manager.search_similar_cards(
                query_text=args.search,
                embedding_type=args.embedding_type,
                top_k=args.top_k,
                deck_name=args.search_deck,
                similarity_threshold=args.threshold
            )
            
            if results:
                print(f"\n📋 Found {len(results)} similar cards:")
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. Card {result['card_id']} (Similarity: {result['similarity_score']:.3f})")
                    print(f"   Deck: {result['deck_name']}")
                    print(f"   Front: {result['front_text'][:100]}...")
                    if result['back_text']:
                        print(f"   Back: {result['back_text'][:100]}...")
                    if result['tags']:
                        print(f"   Tags: {', '.join(result['tags'])}")
            else:
                print("No similar cards found")
        
        # Show statistics
        elif args.stats:
            print("📊 Fetching embedding statistics...")
            stats = await manager.get_embedding_statistics()
            
            print(f"\n📈 Embedding Statistics:")
            print(f"   Total cards: {stats['total_cards']}")
            print(f"   Cards with embeddings: {stats['cards_with_embeddings']}")
            print(f"   Overall completion rate: {stats['completion_rate']:.2%}")
            
            print(f"\n🏷️  Embeddings by type:")
            for emb_type, count in stats['embedding_counts_by_type'].items():
                print(f"   {emb_type}: {count}")
            
            print(f"\n📚 Deck statistics:")
            for deck_name, deck_stats in stats['deck_statistics'].items():
                print(f"   {deck_name}:")
                print(f"     Cards: {deck_stats['total_cards']}")
                print(f"     Embeddings: {deck_stats['total_embeddings']}")
                print(f"     Completion: {deck_stats['completion_rate']:.2%}")
            
            print(f"\n🤖 Model info:")
            print(f"   Model: {stats['model_info']['model_name']}")
            print(f"   Dimension: {stats['model_info']['embedding_dimension']}")
            print(f"   Device: {stats['model_info']['device']}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return

if __name__ == "__main__":
    asyncio.run(main()) 
