# PowerTrust Solar Intelligence — Demo Runbook

Two services. Backend first, frontend second.

## 0. Prerequisites (one-time)

- Python 3.12, Node 18+, Chrome
- `GROQ_API_KEY` set in environment
- Python deps installed to user site: `pip install --user --no-deps fastapi "uvicorn[standard]" starlette`
- Node deps: `cd web && npm install`

## 1. Start the backend (port 8000)

```bash
cd C:/Users/NJ/Desktop/solar-intelligence
python -c "import sys, site; sys.path.insert(0, site.getusersitepackages()); import uvicorn; uvicorn.run('api.main:app', host='127.0.0.1', port=8000, log_level='warning')"
```

The user-site injection is required because Anaconda on this machine has `ENABLE_USER_SITE=False` but the FastAPI deps live in the user site.

Verify: `curl http://127.0.0.1:8000/api/health` → `{"status":"ok","countries_loaded":10,"groq_configured":true}`

## 2. Start the frontend (port 3000)

```bash
cd C:/Users/NJ/Desktop/solar-intelligence/web
npx next dev -p 3000
```

Verify: open http://localhost:3000/ in Chrome.

## 3. Demo routes

| Route | What to show |
|---|---|
| `/` | Hero, 4 KPI tiles, country grid |
| `/country/Mexico` | Dashboard: feasibility ranking + recommendation card |
| `/country/Brazil/deep-dive?state=Minas%20Gerais` | Radar profile + dimension scores |
| `/country/Chile/chat` | Ask: "What is PMGD and why does it matter?" |
| `/country/South%20Africa/audit` | Full coverage heatmap across 5 states |
| `/methodology` | Scoring weights + translation provenance |

## 4. Chat prompts that demo well

| Country | Prompt | Expected |
|---|---|---|
| Chile | "What is PMGD and why does it matter?" | Cites Ley 20.571 + Ley 21.118 |
| Brazil | "How does DG compensation work after Lei 14.300?" | Cites the actual law |
| Colombia | "Tax incentives under Law 1715?" | 50% deduction + accel. depreciation + VAT exemption |
| Mexico | "Who won Eurovision 2024?" | One-sentence refusal (out-of-scope demo) |
| Brazil | "Compare Minas Gerais and São Paulo" | Refuses on São Paulo (shows no-invent discipline) |

## 5. If something breaks mid-demo

- Backend crashed → rerun Step 1 (takes ~10s to reload KB)
- Frontend crashed → `Ctrl+C` in the web/ terminal, rerun Step 2
- Chat silently hangs → check `GROQ_API_KEY` is still valid
- Port already in use → `netstat -ano | findstr :8000` then `taskkill //PID <n> //F`

## 6. Known demo-day risks

- **Groq is a live dependency.** Rate limits / network issues will break chat — have a backup prompt you already demoed ready.
- **Next.js in dev mode** — first paint is slower than prod. OK for this demo length, but if it feels sluggish: `cd web && npx next build && npx next start`.
- **Old Streamlit `app.py` still in repo.** Ignore it. Do not run `streamlit run app.py`.
