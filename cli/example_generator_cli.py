#!/usr/bin/env python3
"""
Standalone CLI for example generation using LLMs for Anki cards
"""
import asyncio
import sys
from pathlib import Path
import logging

sys.path.append(str(Path(__file__).parent))

from database.manager import DatabaseManager
from models.database import AnkiCard
from services.example_generator import ExampleGeneratorService

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

def get_card_data(card, columns):
	data = {}
	for col in columns:
		if hasattr(card, col):
			data[col] = getattr(card, col)
		else:
			data[col] = None
	return data

async def main():
	import argparse
	parser = argparse.ArgumentParser(description="Anki Vector Example Generator Batch Processor")
	parser.add_argument('--deck', type=str, help='Target specific deck')
	parser.add_argument('--columns', type=str, required=True, help='Comma-separated list of columns to use as input for the prompt')
	parser.add_argument('--instructions', type=str, required=True, help='Path to Jinja2 template file for prompt')
	parser.add_argument('--limit', type=int, default=None, help='Limit number of cards to process')
	parser.add_argument('--dry-run', action='store_true', help='Do not write example to DB, just simulate')
	parser.add_argument('--parallel', action='store_true', help='Process cards in parallel (default: sequential)')
	args = parser.parse_args()

	example_service = ExampleGeneratorService()
	db_manager = DatabaseManager()

	columns = [c.strip() for c in args.columns.split(',')]
	with open(args.instructions, 'r', encoding='utf-8') as f:
		template_str = f.read()

	# Query cards
	with db_manager.get_session() as session:
		query = session.query(AnkiCard)
		if args.deck:
			query = query.filter(AnkiCard.deck_name == args.deck)
		# Only process cards where example is empty
		query = query.filter((AnkiCard.example == None) | (AnkiCard.example == ''))
		if args.limit:
			query = query.limit(args.limit)
		cards = query.all()

	if not cards:
		print('No cards found for processing.')
		return

	logger.info(f"Processing {len(cards)} cards for example generation...")

	async def process_card(card):
		card_data = get_card_data(card, columns)
		try:
			result = example_service.generate_example(card_data, template_str)
			if not args.dry_run:
				card.example = result
				with db_manager.get_session() as s2:
					c2 = s2.get(AnkiCard, card.id)
					c2.example = result
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
	logger.info(f"Example generation complete. Success: {success}, Failed: {fail}")

if __name__ == "__main__":
	asyncio.run(main()) 
