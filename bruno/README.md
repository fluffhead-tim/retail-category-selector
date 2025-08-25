# Bruno Collection for Retail Category Selector

This collection targets your Flask API:

- **local** → http://127.0.0.1:5000
- **stage** → update in `environments/stage.bru`
- **prod**  → update in `environments/prod.bru`

## Environments
Edit the host in:
- `environments/local.bru`
- `environments/stage.bru`
- `environments/prod.bru`

## Secrets
If you need secrets for headers, put them in `bruno/.env` (NOT committed).
A sample is in `.env.example`.

## Run with Bruno app
Open this folder as a collection.

## CLI (optional)
Install CLI:
  npm i -D @usebruno/cli

Run whole collection:
  npx bru run ./bruno --env local

Run a single request:
  npx bru run ./bruno/requests/health.bru --env local
