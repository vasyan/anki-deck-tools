import logging
from config import settings
from litellm import completion
from jinja2 import Template

logger = logging.getLogger(__name__)

class ExampleGeneratorService:
	def __init__(self, api_key: str = None, model: str = None):
		self.api_key = api_key or settings.openai_api_key
		self.model = model or "gpt-3.5-turbo"

	def generate_example(self, card_data: dict, template_str: str) -> str:
		"""
		Render the prompt using Jinja2 and call the LLM to generate an example.
		"""
		try:
			template = Template(template_str)
			prompt = template.render(**card_data)
			response = completion(
				model=self.model,
				messages=[{"role": "user", "content": prompt}],
				api_key=self.api_key
			)
			# Extract the generated text
			return response.choices[0].message.content.strip()
		except Exception as e:
			logger.error(f"Example generation failed: {e}")
			raise 
