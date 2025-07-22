#!/usr/bin/env python3
"""
Standalone CLI for TTS (text-to-speech) batch processing on Anki cards
"""
import asyncio
import sys
from pathlib import Path
import logging
import time

sys.path.append(str(Path(__file__).parent))

from database.manager import DatabaseManager
from models.database import AnkiCard
from services.text_to_voice import TextToSpeechService
from config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

def get_card_text(card, column):
	if column == 'front':
		return card.front_text
	elif column == 'back':
		return card.back_text
	elif hasattr(card, column):
		return getattr(card, column)
	else:
		raise ValueError(f"Column '{column}' not found in AnkiCard")

async def main():
	import argparse
	parser = argparse.ArgumentParser(description="Anki Vector TTS Batch Processor")
	parser.add_argument('--deck', type=str, help='Target specific deck')
	parser.add_argument('--column', type=str, default='front', help='Card column to use as text input (default: front)')
	parser.add_argument('--dry-run', action='store_true', help='Do not write audio to DB, just simulate')
	parser.add_argument('--parallel', action='store_true', help='Process cards in parallel (default: sequential)')
	parser.add_argument('--model', type=str, default=settings.openai_tts_model, help='TTS model to use')
	parser.add_argument('--format', type=str, default=settings.openai_tts_format, help='Audio format (mp3, wav, etc.)')
	parser.add_argument('--limit', type=int, default=None, help='Limit number of cards to process')
	parser.add_argument('--debug-output', action='store_true', help='Save every TTS result to a timestamped mp3 file in the project root')
	parser.add_argument('--instructions', type=str, default=None, help='Path to file with instructions for TTS voice (accent, tone, etc.)')
	args = parser.parse_args()

	ts_service = TextToSpeechService(model=args.model, audio_format=args.format)
	db_manager = DatabaseManager()

	# Query cards
	with db_manager.get_session() as session:
		query = session.query(AnkiCard)
		if args.deck:
			query = query.filter(AnkiCard.deck_name == args.deck)
		# Only process cards without audio
		query = query.filter(AnkiCard.audio == None)
		if args.limit:
			query = query.limit(args.limit)
		cards = query.all()

	if not cards:
		print('No cards found for processing.')
		return

	logger.info(f"Processing {len(cards)} cards for TTS generation...")

	instructions_text = None
	if args.instructions:
		with open(args.instructions, 'r', encoding='utf-8') as f:
			instructions_text = f.read()

	async def process_card(card):
		text = get_card_text(card, args.column)
		if not text or not text.strip():
			logger.warning(f"Card {card.id} has empty text in column '{args.column}', skipping.")
			return False
			
		try:
			result = ts_service.synthesize(text, model=args.model, audio_format=args.format, voice=args.voice if hasattr(args, 'voice') else None, instructions=instructions_text)
			if args.debug_output and result['audio']:
				ts = int(time.time() * 1000)
				filename = f"{ts}.mp3"
				with open(filename, 'wb') as f:
					f.write(result['audio'])
				logger.info(f"Debug audio output saved to {filename}")
			if not args.dry_run:
				card.audio = result['audio']
				card.tts_model = result['tts_model']
				with db_manager.get_session() as s2:
					c2 = s2.get(AnkiCard, card.id)
					c2.audio = result['audio']
					c2.tts_model = result['tts_model']
					s2.commit()
			logger.info(f"Card {card.id} processed successfully.")
			return True
		except Exception as e:
			logger.error(f"Card {card.id} failed: {e}")
			return False

	if args.parallel:
		import concurrent.futures
		with concurrent.futures.ThreadPoolExecutor() as executor:
			loop = asyncio.get_event_loop()
			results = await asyncio.gather(*[loop.run_in_executor(executor, lambda c=card: asyncio.run(process_card(c))) for card in cards])
	else:
		results = []
		for card in cards:
			res = await process_card(card)
			results.append(res)

	success = sum(1 for r in results if r)
	fail = len(results) - success
	logger.info(f"TTS processing complete. Success: {success}, Failed: {fail}")

if __name__ == "__main__":
	asyncio.run(main()) 
