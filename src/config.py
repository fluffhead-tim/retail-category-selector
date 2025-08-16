import os
from dotenv import load_dotenv

load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

DATA_DIR = os.getenv("DATA_DIR", "./data")
MARKETPLACES_FILE = os.path.join(DATA_DIR, "marketplaces.json")
PROMPT_FILE = os.path.join(DATA_DIR, "prompts", "category_prompt.md")
TAXONOMY_DIR = os.path.join(DATA_DIR, "taxonomies")
