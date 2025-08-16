# Retail Category Selector (API Only)

## Quickstart

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    python -m src.api.main

Health: http://127.0.0.1:5000/health  
Categorize (POST): http://127.0.0.1:5000/categorize

Edit taxonomies/prompt under `./data` without touching code.
