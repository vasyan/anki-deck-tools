#!/usr/bin/env python3
"""
CLI for publishing draft cards to Anki, ensuring model migration and field superset logic.
"""
import argparse
import sys
import asyncio
from services.card_service import CardService

async def main():
    parser = argparse.ArgumentParser(description="Publish draft cards to Anki with model migration.")
    parser.add_argument('--deck', type=str, required=True, help='Target deck name (required)')
    parser.add_argument('--model', type=str, default=None, help='Model name to use (optional)')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of draft cards to upload (optional)')
    args = parser.parse_args()

    service = CardService()
    try:
        result = await service.publish_draft_cards(deck_name=args.deck, model_name=args.model, limit=args.limit)
        print("\n=== Publish Draft Cards Result ===")
        print(f"Message: {result.get('message')}")
        print(f"Published: {result.get('published', 0)}")
        print(f"Failed: {result.get('failed', 0)}")
        if result.get('failed_ids'):
            print(f"Failed IDs: {result['failed_ids']}")
        if result.get('success_ids'):
            print(f"Success IDs: {result['success_ids']}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if sys.version_info < (3, 7):
        print("Python 3.7+ is required.", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main()) 
