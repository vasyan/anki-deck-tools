#!/usr/bin/env python3
import asyncio
import traceback
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from workflows.anki_builder import AnkiBuilder

async def main():
    # parser = argparse.ArgumentParser(description="Test populate_content_with_example function")
    # parser.add_argument('learning_content_id', type=int, help='Learning content ID to test', default=52)
    # args = parser.parse_args()

    # logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

    ID = 52

    builder = AnkiBuilder()
    try:
        # builder.process_contents()

        # generate audio asset for fragments
        # await builder.process_fragments()

        # play audio
        # await builder.play_audio(17)

        await builder.process_uploading()

        print(f"✅ Successfully processed learning content ID {ID}")
    except Exception as e:
        print(f"❌ Error: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
