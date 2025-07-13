import logging
from config import settings
from litellm import speech

logger = logging.getLogger(__name__)

class TextToSpeechService:
	def __init__(self, api_key: str = None, model: str = None, audio_format: str = None, voice: str = None):
		self.api_key = api_key or settings.openai_api_key
		self.model = model or settings.openai_tts_model
		self.audio_format = audio_format or settings.openai_tts_format
		self.voice = voice or settings.openai_tts_voice

	def synthesize(self, text: str, model: str = None, audio_format: str = None, voice: str = None, instructions: str = None) -> dict:
		"""
		Call OpenAI TTS via litellm and return audio bytes and model name.
		"""
		model = model or self.model
		audio_format = audio_format or self.audio_format
		voice = voice or self.voice
		try:
			response = speech(
				model=model,
				voice=voice,
				input=text,
				api_key=self.api_key,
				response_format=audio_format,
				instructions=instructions
			)
			return {
				"audio": response.content,
				"tts_model": model
			}
		except Exception as e:
			logger.error(f"TTS synthesis failed: {e}")
			raise
