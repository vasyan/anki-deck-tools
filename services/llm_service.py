import logging
from config import settings
from litellm import completion  # type: ignore

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class LLMService:
	def __init__(self, api_key: str | None = None, model: str | None = None):
		self.api_key = api_key or settings.openai_api_key
		self.model = model or settings.openai_model

	def call_llm(self, prompt: str) -> str:
		try:
			# logger.debug(f"Prompt: {prompt}")
			response = completion(
				model=self.model,
				messages=[{"role": "user", "content": prompt}],
				api_key=self.api_key
			)

			return response.choices[0].message.content.strip() # type: ignore
		except Exception as e:
			logger.error(f"Example generation failed: {e}")
			raise

