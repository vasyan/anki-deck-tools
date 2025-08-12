import logging
from config import settings
from litellm import speech
from models.schemas import SynthesizeOutput

logger = logging.getLogger(__name__)

instructions_file = "instructions/pronounce-teacher-thai.txt"

class TextToSpeechService:
	def __init__(
			self,
			api_key: str | None = None,
			model: str | None = None,
			audio_format: str | None = None,
			voice: str | None = None,
			instructions: str | None = None):
		self.api_key = api_key or settings.openai_api_key
		self.model = model or settings.openai_tts_model
		self.audio_format = audio_format or settings.openai_tts_format
		self.voice = voice or settings.openai_tts_voice
		self.instructions = instructions or self._read_instructions()

	async def synthesize(
			self,
			text: str,
			model: str | None = None,
			audio_format: str | None = None,
			voice: str | None = None,
			instructions: str | None = None) -> SynthesizeOutput:
		"""
		Call OpenAI TTS via litellm and return audio bytes and model name.
		"""
		model = model or self.model
		audio_format = audio_format or self.audio_format
		voice = voice or self.voice
		instructions = instructions or self.instructions
		logger.info(f"Using instructions: {instructions}")
		try:
			response = speech(
				model=model,
				voice=voice,
				input=text,
				api_key=self.api_key,
				response_format=audio_format,
				instructions=instructions
			)
			return SynthesizeOutput(
				audio=response.content,
				tts_model=model
			)
		except Exception as e:
			logger.error(f"TTS synthesis failed: {e}")
			raise

	def _read_instructions(self) -> str:
		with open(instructions_file, "r") as f:
			return f.read()
