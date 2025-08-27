#!/usr/bin/env python3
import argparse
import asyncio
import traceback
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from workflows.anki_builder import AnkiBuilder

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

async def main():
    parser = argparse.ArgumentParser(description="Test populate_content_with_example function")
    parser.add_argument('mode', type=str, help='mode to run', default='fragments')
    # parser.add_argument('args', type=list, help='args to pass to the mode', default=None)
    args = parser.parse_args()

    # logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

    builder = AnkiBuilder()
    try:
        if args.mode == 'contents':
            builder.process_contents()
        elif args.mode == 'fragments':
            await builder.process_fragments()
        elif args.mode == 'anki':
            await builder.sync_to_anki()
        else:
            raise ValueError(f"Invalid mode: {args.mode}")

        print(f"✅ Finished")
    except Exception as e:
        print(f"❌ Error: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
