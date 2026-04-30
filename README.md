# Retail Category Selector

A Flask REST API that automatically maps retail products to the correct leaf category in multiple marketplace taxonomies. It uses a two-stage pipeline: a fast keyword pre-filter shortlists candidates, then an LLM (OpenAI or Anthropic) makes the final selection.

Supports **Tesco, B&Q, SuperDrug, Mountain Warehouse, Debenhams, and Decathlon** out of the box. New marketplaces can be added by dropping in a taxonomy JSON file and a one-line entry in `data/marketplaces.json` — no code changes required.

---

## Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Adding a Marketplace](#adding-a-marketplace)
- [Deploying to Railway](#deploying-to-railway)

---

## Features

- **Multi-marketplace** — categorise a single product across all configured marketplaces in one request, or target a specific one via query parameter
- **Dual LLM provider** — switch between OpenAI and Anthropic at config time; override per-request via query parameters
- **Token-efficient** — heuristic pre-filter shortlists up to 300 leaf candidates before the LLM call, keeping prompt sizes predictable
- **Zero-code taxonomy management** — add or update marketplaces by editing JSON files under `data/`
- **Test mode** — optional confidence scores, per-marketplace token usage, and effective model config in the response
- **Demo UI** — browser-based interface at `/` for non-technical testing

---

## How It Works

```
POST /categorize
       │
       ▼
  Map external fields (ItemNumber, ItemTitle, …)
  to internal ItemInput model
       │
       ▼
  For each marketplace:
  ┌─────────────────────────────────────────┐
  │  1. Flatten taxonomy JSON → leaf nodes  │
  │  2. Score leaves by keyword overlap     │
  │     (product name × 2, description × 1)│
  │  3. Keep top 300 candidates             │
  │  4. Send candidates + product to LLM   │
  │  5. LLM returns category_id + name     │
  │  6. Resolve to canonical leaf node     │
  └─────────────────────────────────────────┘
       │
       ▼
  Return { categories: [...] }
```

---

## Project Structure

```
retail-category-selector/
├── src/
│   ├── api/
│   │   └── main.py          # Flask app, routes, request mapping
│   ├── core/
│   │   ├── categorizer.py   # Pre-filter + LLM orchestration
│   │   ├── llm.py           # OpenAI / Anthropic client wrappers
│   │   ├── loaders.py       # Marketplace config + taxonomy loaders
│   │   ├── models.py        # Pydantic models
│   │   └── taxonomy_store.py# Leaf-node flattening utilities
│   └── config.py            # Environment variable configuration
├── data/
│   ├── marketplaces.json    # Marketplace registry
│   ├── prompts/
│   │   └── category_prompt.md  # System prompt for the LLM
│   └── taxonomies/
│       ├── Tesco.json
│       ├── BandQ.json
│       ├── SuperDrug.json
│       ├── MountainWarehouse.json
│       ├── Debenhams.json
│       └── Decathlon.json
├── ui/                      # Demo web interface (Tailwind CSS)
├── tests/
│   └── smoke.http           # Manual HTTP test collection
├── docs/
│   └── openapi-as-is.json   # OpenAPI 3.1 specification
├── Procfile                 # Gunicorn start command for Railway/Heroku
├── railway.toml             # Railway deployment configuration
├── requirements.txt
└── .python-version          # Pins Python 3.11
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- An OpenAI **or** Anthropic API key

### Install and run

```bash
git clone https://github.com/fluffhead-tim/retail-category-selector.git
cd retail-category-selector

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
MODEL_PROVIDER=anthropic          # or: openai
ANTHROPIC_API_KEY=sk-ant-...      # required if using anthropic
OPENAI_API_KEY=sk-...             # required if using openai
```

Start the server:

```bash
python -m src.api.main
```

The API is now available at `http://127.0.0.1:8000`.

Verify it's running:

```bash
curl http://127.0.0.1:8000/health
```

---

## Configuration

All configuration is through environment variables. Set them in `.env` for local development or in your deployment platform's secrets/variables panel.

### Required

| Variable | Description |
|---|---|
| `MODEL_PROVIDER` | LLM to use: `openai` or `anthropic` (default: `openai`) |
| `OPENAI_API_KEY` | Required when `MODEL_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | Required when `MODEL_PROVIDER=anthropic` |
| `API_KEY` | Secret key that callers must supply in the `X-API-Key` request header. When unset (e.g. local dev), authentication is skipped. |

### Optional — model tuning

| Variable | Default | Description |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model identifier |
| `OPENAI_TEMPERATURE` | `0.0` | Sampling temperature |
| `OPENAI_TOP_P` | `0.0` | Nucleus sampling top-p |
| `OPENAI_MAX_TOKENS` | `200` | Max completion tokens |
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet-latest` | Anthropic model identifier |
| `ANTHROPIC_TEMPERATURE` | `0.0` | Sampling temperature |
| `ANTHROPIC_MAX_TOKENS` | `300` | Max completion tokens |

### Optional — runtime behaviour

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `./data` | Path to the data directory |
| `PORT` | `8000` | Port the server listens on |
| `SHORTLIST_MAX_PER_MKT` | `300` | Max leaf candidates sent to the LLM per marketplace |
| `MAX_NAME_CHARS` | `300` | Product name character limit passed to the LLM |
| `MAX_DESC_CHARS` | `2000` | Product description character limit passed to the LLM |
| `DEBUG` | `` | Set to `1` or `true` to enable fallback debug logging |

All model parameters can also be overridden **per request** via query parameters (see [API Reference](#api-reference)).

---

## API Reference

Full OpenAPI 3.1 specification: [`docs/openapi-as-is.json`](docs/openapi-as-is.json)

### `GET /health`

Basic liveness check.

**Response `200`**
```json
{
  "status": "ok",
  "data_dir": "/app/data",
  "marketplaces_file": "/app/data/marketplaces.json"
}
```

---

### `GET /health/llm`

Returns the active LLM provider and whether each provider's API key is configured.

**Response `200`**
```json
{
  "provider": "anthropic",
  "openai":    { "configured": false, "model": "gpt-4o-mini" },
  "anthropic": { "configured": true,  "model": "claude-3-5-sonnet-latest" }
}
```

---

### `POST /categorize`

Categorise a product across all configured marketplaces (or a single one).

#### Authentication

When `API_KEY` is set on the server, include the key in every request:

```
X-API-Key: <your-api-key>
```

Requests missing the header, or supplying the wrong value, receive `401 Unauthorized`. The `/health` and `/health/llm` endpoints do not require authentication.

#### Request body

The body must be a single JSON object. `ItemNumber` and `ItemTitle` are required; all other fields improve accuracy.

```json
{
  "ItemNumber":           "SKU-001",
  "ItemTitle":            "Outdoor Rattan 4-Seater Garden Sofa Set",
  "Brand":                "GardenCo",
  "Description":          "<p>Comfortable rattan sofa set for outdoor use.</p>",
  "Listing Description":  "Includes cushions and a weather-resistant cover.",
  "Price":                "£299.99",
  "Country of Manufacture": "China",
  "bulletpoints":         "UV-resistant rattan. Seats up to 4. All-weather cushions.",
  "Image1FullSource":     "https://cdn.example.com/images/product-001.jpg"
}
```

Image fields `Image1FullSource` through `Image10FullSource` are all accepted.

#### Query parameters

| Parameter | Description |
|---|---|
| `marketplace` | Restrict to a single marketplace by name (case-insensitive), e.g. `?marketplace=Debenhams` |
| `test` | Set to `true`, `1`, or `yes` to include confidence scores, token usage, and effective model config in the response |
| `MODEL_PROVIDER` | Override the LLM provider for this request (`openai` or `anthropic`) |
| `OPENAI_MODEL` | Override OpenAI model for this request |
| `OPENAI_TEMPERATURE` | Override OpenAI temperature (float) |
| `OPENAI_TOP_P` | Override OpenAI top-p (float) |
| `OPENAI_MAX_TOKENS` | Override OpenAI max tokens (integer) |
| `ANTHROPIC_MODEL` | Override Anthropic model for this request |
| `ANTHROPIC_TEMPERATURE` | Override Anthropic temperature (float) |
| `ANTHROPIC_TOP_P` | Override Anthropic top-p (float) |
| `ANTHROPIC_MAX_TOKENS` | Override Anthropic max tokens (integer) |

#### Response `200` — standard

```json
{
  "categories": [
    {
      "products": {
        "category_code":  "12345",
        "category_label": "Garden Furniture",
        "category_path":  "Home & Garden > Garden Furniture",
        "product_sku":    "SKU-001",
        "product_id":     "SKU-001",
        "marketplace":    "Debenhams",
        "note":           null
      }
    }
  ]
}
```

When a marketplace's taxonomy file is missing, that entry returns `category_label: "UNMAPPED"` and `category_code: "N/A"` with a `note` explaining why — the rest of the marketplaces are still processed.

#### Response `200` — test mode (`?test=true`)

The response additionally includes `confidence` on each result, a `usage` array, and an `env` object:

```json
{
  "categories": [
    {
      "products": {
        "category_code":  "12345",
        "category_label": "Garden Furniture",
        "category_path":  "Home & Garden > Garden Furniture",
        "product_sku":    "SKU-001",
        "product_id":     "SKU-001",
        "marketplace":    "Debenhams",
        "note":           null,
        "confidence":     0.92
      }
    }
  ],
  "usage": [
    {
      "marketplace":        "Debenhams",
      "prompt_tokens":      450,
      "completion_tokens":  35,
      "total_tokens":       485
    }
  ],
  "env": {
    "MODEL_PROVIDER":       "anthropic",
    "ANTHROPIC_MODEL":      "claude-3-5-sonnet-latest",
    "ANTHROPIC_TEMPERATURE": 0.0,
    "ANTHROPIC_TOP_P":      null,
    "ANTHROPIC_MAX_TOKENS": 300,
    "OPENAI_MODEL":         "gpt-4o-mini",
    "OPENAI_TEMPERATURE":   0.0,
    "OPENAI_TOP_P":         0.0,
    "OPENAI_MAX_TOKENS":    200
  }
}
```

#### Error responses

| Status | Condition |
|---|---|
| `400` | Body is not valid JSON |
| `400` | Body is a JSON array instead of an object |
| `400` | `ItemNumber` or `ItemTitle` missing from payload |
| `400` | `marketplace` query parameter does not match any configured marketplace — the response includes an `available` array of valid names |

---

## Adding a Marketplace

No code changes are needed.

1. **Add the taxonomy file** to `data/taxonomies/` as a JSON hierarchy. The structure should match the existing files (nested nodes with `code`, `label`, and `children` fields, or configure alternate field names in step 2).

2. **Register the marketplace** in `data/marketplaces.json`:

```json
{
  "name": "MyMarketplace",
  "taxonomy_file": "data/taxonomies/MyMarketplace.json",
  "id_field": "code",
  "name_field": "label"
}
```

3. Restart the server (or redeploy). The new marketplace will appear in all `/categorize` responses automatically.

Supported field name overrides: `id_field`, `name_field`, `children_field` (defaults: `id`, `name`, `children`).

---

## Deploying to Railway

The repository includes a `Procfile` and `railway.toml` pre-configured for Railway.

1. Push the repo to GitHub (including the `data/` directory — taxonomy files must be in the repo).
2. In the [Railway dashboard](https://railway.com), create a **New Project → Deploy from GitHub repo** and select this repository.
3. Under **Variables**, set at minimum:

   | Variable | Value |
   |---|---|
   | `MODEL_PROVIDER` | `anthropic` or `openai` |
   | `ANTHROPIC_API_KEY` | your key |
   | `OPENAI_API_KEY` | your key |

   Do **not** set `PORT` — Railway injects it automatically.

4. Railway will build and deploy. Every subsequent `git push` to the main branch triggers a new deployment.

Verify the live deployment:

```bash
curl https://<your-railway-url>/health
```

---

## Dependencies

| Package | Purpose |
|---|---|
| Flask 3.0 | Web framework |
| Pydantic 2 | Request/response validation |
| openai | OpenAI API client |
| anthropic | Anthropic API client |
| rapidfuzz | Fuzzy string matching in the pre-filter |
| orjson | Fast JSON parsing |
| python-dotenv | `.env` file loading |
| gunicorn | Production WSGI server |
