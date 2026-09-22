# ConMix Pro — Concrete Mix Design

Vercel-ready FastAPI + static frontend concrete mix design calculator.

## Project structure
- `index.html` — frontend UI
- `script.js` — browser logic and API call
- `style.css` — styling
- `api/index.py` — FastAPI calculation API and frontend asset routes
- `pyproject.toml` — Python dependencies

## Vercel deployment
Use the repository root (`./`) as the Vercel Root Directory and select the FastAPI preset. No custom build command or output directory is required.

## API endpoints
- `GET /` — frontend
- `GET /style.css` — stylesheet
- `GET /script.js` — frontend JavaScript
- `GET /api` — API status
- `GET /api/health` — health check
- `POST /api/calculate` — mix calculation

## Engineering note
The calculator follows an IS 10262:2019 / IS 456:2000-inspired workflow, but strength-versus-water/cement values are illustrative defaults. Results are first-trial proportions and must be verified with actual materials and laboratory trial mixes before project use.
