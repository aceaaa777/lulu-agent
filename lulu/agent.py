"""Public agent entry: Lulu's own loop, local capabilities, pluggable model provider."""
from .loop import Agent
from .models import OllamaProvider, OpenAICompatibleProvider, provider_from_config
