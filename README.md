# NestLeap

Stock analysis platform for long-term investors. Analyzes ~200 large-cap stocks weekly using fundamentals data from Yahoo Finance and AI-generated insights via Google Gemini. Runs a simulated DCA portfolio that buys the top undervalued picks and benchmarks against the S&P 500.

## What it does

- **Weekly batch analysis** of the top 200 US stocks by market cap
- **Deterministic scoring** across quality, value, growth, and momentum metrics
- **AI synthesis** via Gemini — generates fair value estimates, risk/catalyst assessment, and an overall score that adjusts the deterministic baseline
- **Daily market summary** with index data and news context
- **Simulated portfolio** — $1,000/week DCA into the top 10 undervalued stocks, sells positions at fair value or overvalued, tracks performance vs S&P 500
- **Admin panel** at `/admin` for triggering batch runs, rebalancing, and individual stock analysis

## Architecture

```
frontend/          Next.js 14, Tailwind CSS, single-page app
backend/           FastAPI, SQLAlchemy, SQLite
  app/
    collectors/    Yahoo Finance data + news
    analysis/      Scoring engine, Gemini integration, batch runner, portfolio engine
    main.py        API endpoints (public + admin)
```

The backend collects fundamentals via `yfinance`, computes deterministic sub-scores (16 metrics), then makes a single Gemini API call per stock to synthesize everything into a valuation, fair value estimate, and adjusted overall score. Results are stored in SQLite.

The frontend is read-only for users. All write operations (batch analysis, re-analysis, rebalance) require an admin key passed via `X-Admin-Key` header.

## Running locally

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example ../.env  # edit with your Gemini key
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Deploying

The project ships with Docker Compose + Caddy for deployment on any VPS.

```bash
cp .env.example .env   # fill in GEMINI_API_KEY, ADMIN_KEY, DOMAIN
docker compose up -d --build
```

Caddy handles HTTPS automatically via Let's Encrypt.

### Scheduled jobs (on the VPS)

The app does not start cron by itself. Use `crontab -e` on the server with your **public URL** and **`ADMIN_KEY`** from `.env` (same key as `/admin`).

```bash
chmod +x scripts/weekly-batch.sh scripts/daily-market-summary.sh
```

**Every Sunday 02:00** — full batch (~200 stocks). Portfolio rebalances automatically when the batch finishes; the script then refreshes the market summary.

```
0 2 * * 0 cd /root/stock_platform && API_URL=https://nestleap.au ADMIN_KEY=your_admin_key ./scripts/weekly-batch.sh >> /var/log/nestleap-weekly.log 2>&1
```

**Every day 06:15** — new AI market summary (change the time if you like).

```
15 6 * * * cd /root/stock_platform && API_URL=https://nestleap.au ADMIN_KEY=your_admin_key ./scripts/daily-market-summary.sh >> /var/log/nestleap-market.log 2>&1
```

Replace `nestleap.au` if your domain differs. Times use the **server’s** timezone (`timedatectl` to check).

See `.env.example` for required environment variables.
