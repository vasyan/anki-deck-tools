#!/usr/bin/env python3
"""
CLI for generating and publishing example audio for Anki cards
"""
import asyncio
import sys
import re
from pathlib import Path
import logging
import base64
from datetime import datetime

sys.path.append(str(Path(__file__).parent))

from database.manager import DatabaseManager
from models.database import AnkiCard, ExampleAudio, ExampleAudioLog
from services.text_to_voice import TextToSpeechService
from services.example_audio_manager import ExampleAudioManager
from services.card_service import CardService
from sqlalchemy.orm import Session

# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

THAI_REGEX = re.compile(r'[\u0E00-\u0E7F]+(?:\s[\u0E00-\u0E7F]+)*')
STRONG_TAG_REGEX = re.compile(r'<strong>(.*?)</strong>', re.DOTALL)


def extract_thai_strongs(html):
	matches = list(STRONG_TAG_REGEX.finditer(html))
	thai_strongs = []
	for i, match in enumerate(matches):
		content = match.group(1)
		if THAI_REGEX.search(content):
			thai_text = ' '.join(THAI_REGEX.findall(content))
			thai_strongs.append({
				'thai': thai_text,
				'start': match.start(0),
				'end': match.end(0),
				'full': match.group(0),
				'index': i
			})
	return thai_strongs


def insert_sound_tokens(html, card_id, thai_strongs):
	# Insert or update [sound:example_{card_id}_{index}.mp3] after each <strong> with Thai, from the end
	result = html
	for idx, item in reversed(list(enumerate(thai_strongs))):
		sound_token = f'[sound:example_{card_id}_{idx}.mp3]'
		insert_pos = item['end']
		# Check if there is already a [sound:example_*.mp3] token immediately after the <strong> tag
		post_str = result[insert_pos:insert_pos+30]  # 30 chars is enough for the token
		import re
		match = re.match(r'\[sound:example_\d+_\d+\.mp3\]', post_str)
		if match:
			# Replace the existing token with the correct one
			old_token = match.group(0)
			result = result[:insert_pos] + sound_token + result[insert_pos+len(old_token):]
		else:
			# Insert the token if not present
			result = result[:insert_pos] + sound_token + result[insert_pos:]
	return result


def log_action(session: Session, card_id, action, status, details=None):
	log = ExampleAudioLog(
		card_id=card_id,
		action=action,
		status=status,
		timestamp=datetime.utcnow(),
		details=details if details else None
	)
	session.add(log)
	session.commit()


async def main():
	import argparse
	parser = argparse.ArgumentParser(description="Generate and publish example audio for Anki cards")
	parser.add_argument('--deck', type=str, help='Target specific deck')
	parser.add_argument('--limit', type=int, default=None, help='Limit number of cards to process')
	parser.add_argument('--publish', action='store_true', help='Publish to Anki after generation')
	parser.add_argument('--republish', action='store_true', help='Force re-publish even if already published')
	args = parser.parse_args()

	db_manager = DatabaseManager()
	card_service = CardService(db_manager)
	tts_service = TextToSpeechService()

	with db_manager.get_session() as session:
		query = session.query(AnkiCard)
		if args.deck:
			query = query.filter(AnkiCard.deck_name == args.deck)
		if args.limit:
			query = query.limit(args.limit)
		cards = query.all()
		card_ids = [card.id for card in cards]

		if not cards:
			logger.info('No cards found for processing.')
			return

		logger.info(f"Processing {len(cards)} cards for example audio generation...")

		for card in cards:
			try:
				example_html = card.example or ''
				thai_strongs = extract_thai_strongs(example_html)
				if not thai_strongs:
					log_action(session, card.id, 'generate', 'skipped', 'No Thai <strong> tags found')
					continue
				# Generate audio for each Thai strong
				audio_blobs = []
				for idx, item in enumerate(thai_strongs):
					try:
						# Caching: check if this text already exists in the audio bank
						audio_manager = ExampleAudioManager()
						
						existing_audio = audio_manager.find_reusable_audio(item['thai'])
						if existing_audio:
							audio_blob = existing_audio['audio_blob']
							tts_model = existing_audio['tts_model']
							
							# Associate existing audio with this card
							audio_manager.associate_audio_with_card(
								card_id=card.id,
								audio_id=existing_audio['audio_id'],
								order_index=idx
							)
							
							audio_blobs.append((idx, audio_blob))
							log_action(session, card.id, 'generate', 'cached', f'Audio reused for index {idx}')
							continue
							
						# If not cached, call TTS API
						result = tts_service.synthesize(item['thai'])
						audio_blob = result['audio']
						tts_model = result['tts_model']
						
						# Create new audio and associate with card
						audio_id, association_id = audio_manager.create_audio_and_associate(
							card_id=card.id,
							example_text=item['thai'],
							audio_blob=audio_blob,
							tts_model=tts_model,
							order_index=idx
						)
						
						audio_blobs.append((idx, audio_blob))
						log_action(session, card.id, 'generate', 'success', f'Audio generated for index {idx}')
					except Exception as e:
						log_action(session, card.id, 'generate', 'failed', f'Audio generation failed for index {idx}: {e}')
				# Update example field with sound tokens
				logger.debug(f"thai_strongs: {thai_strongs}")
				new_example = insert_sound_tokens(example_html, card.id, thai_strongs)
				card.example = new_example
				session.commit()
				log_action(session, card.id, 'update_example', 'success', 'Example field updated with sound tokens')
			except Exception as e:
				log_action(session, card.id, 'generate', 'failed', f'Card processing failed: {e}')

	if args.publish:
		logger.info('Publishing audio and updated examples to Anki...')
		from anki.client import AnkiConnectClient
		with db_manager.get_session() as session:
			for card_id in card_ids:
				try:
					# Re-fetch the card in the current session
					card_in_session = session.query(AnkiCard).get(card_id)
					# Get all example audios for this card
					audio_manager = ExampleAudioManager()
					example_audios_data = audio_manager.get_card_audio_examples(card_id)
					
					# Convert to ExampleAudio-like objects for compatibility
					class AudioExample:
						def __init__(self, data):
							self.audio_blob = data['audio_blob']
							self.example_text = data['example_text']
							self.tts_model = data['tts_model']
							self.order_index = data['order_index']
					
					example_audios = [AudioExample(data) for data in example_audios_data]
					if not example_audios:
						log_action(session, card_id, 'publish', 'skipped', 'No example audios to publish')
						continue
					# Check if already published (unless --republish)
					already_published = False
					if not args.republish:
						log_entry = session.query(ExampleAudioLog).filter_by(card_id=card_id, action='publish', status='success').first()
						if log_entry:
							already_published = True
					if already_published:
						log_action(session, card_id, 'publish', 'skipped', 'Already published')
						continue
					# Upload audio files and update example field in Anki
					async def publish_to_anki():
						async with AnkiConnectClient() as anki_client:
							# Upload each audio file
							for audio in example_audios:
								filename = f"example_{card_id}_{audio.order_index}.mp3"
								try:
									await anki_client._request("storeMediaFile", {"filename": filename, "data": base64.b64encode(audio.audio_blob).decode('utf-8')})
									log_action(session, card_id, 'publish', 'success', f'Uploaded {filename}')
								except Exception as e:
									log_action(session, card_id, 'publish', 'failed', f'Failed to upload {filename}: {e}')
							# Update example field in Anki
							if card_in_session.anki_note_id:
								try:
									await anki_client._request("updateNoteFields", {"note": {"id": card_in_session.anki_note_id, "fields": {"Example": card_in_session.example}}})
									log_action(session, card_id, 'publish', 'success', 'Updated example field in Anki')
								except Exception as e:
									log_action(session, card_id, 'publish', 'failed', f'Failed to update example field: {e}')
							else:
								log_action(session, card_id, 'publish', 'failed', 'No anki_note_id for card')
					await publish_to_anki()
				except Exception as e:
					log_action(session, card_id, 'publish', 'failed', f'Publish process failed: {e}')

if __name__ == "__main__":
	asyncio.run(main()) 
