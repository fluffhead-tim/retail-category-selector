import os
from dotenv import load_dotenv

load_dotenv()


def _get_float_env(name, default=None):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int_env(name, default=None):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = _get_float_env("OPENAI_TEMPERATURE", 0.0)
OPENAI_TOP_P = _get_float_env("OPENAI_TOP_P", 0.0)
OPENAI_MAX_TOKENS = _get_int_env("OPENAI_MAX_TOKENS", 200)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
ANTHROPIC_TEMPERATURE = _get_float_env("ANTHROPIC_TEMPERATURE", 0.0)
ANTHROPIC_TOP_P = _get_float_env("ANTHROPIC_TOP_P")
ANTHROPIC_MAX_TOKENS = _get_int_env("ANTHROPIC_MAX_TOKENS", 300)

DATA_DIR = os.getenv("DATA_DIR", "./data")
MARKETPLACES_FILE = os.path.join(DATA_DIR, "marketplaces.json")
PROMPT_FILE = os.path.join(DATA_DIR, "prompts", "category_prompt.md")
TAXONOMY_DIR = os.path.join(DATA_DIR, "taxonomies")
