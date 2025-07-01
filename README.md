# Stock Analysis Platform 📈

A minimalistic, real-time (hourly-delayed) platform for long-term stock investors that delivers intelligent buy/sell alerts and AI-summarized news.

## 🚀 Features

- **Smart Stock Screener**: Analyzes valuation metrics, technical indicators, and market dynamics
- **AI News Summarization**: Delivers relevant news with sentiment analysis in under 300 characters
- **Buy/Sell Alerts**: Intelligent recommendations based on valuation + market dynamics + news sentiment
- **Clean UI**: Intuitive interface that avoids information overload
- **Price Ranges**: Buy/sell ranges instead of overwhelming real-time charts

## 🏗️ Architecture

### Backend (`/backend`)
- **FastAPI** REST API server
- **PostgreSQL** database for storing metrics and analysis
- **Stock Screener Engine**: Calculates P/E, FCF, technical indicators
- **News Sentiment Collector**: Scrapes and analyzes news from multiple sources
- **LLM Inference Layer**: Gemini 2.5 Flash for generating recommendations

### Frontend (`/frontend`)
- **Next.js** + **React** + **Tailwind CSS**
- **Home Screen**: Stock search and summary cards
- **Stock Detail View**: Detailed analysis and historical data

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI + PostgreSQL |
| LLM | Gemini 2.5 Flash |
| Data APIs | Alpha Vantage, Yahoo Finance, NewsAPI |
| Scraping | Playwright |
| Frontend | Next.js + React + Tailwind |
| Deployment | Railway / Vercel |

## 🚀 Quick Start

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # Add your API keys
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## 📊 Core Components

1. **Stock Screener Engine** - Analyzes fundamentals and technicals
2. **News Sentiment Collector** - Aggregates and summarizes news
3. **LLM Inference Layer** - Generates intelligent recommendations
4. **React UI** - Clean, intuitive user interface

## 🔑 Environment Variables

### Required API Keys

Before running the platform, you'll need to obtain API keys for:

1. **Alpha Vantage** - For stock fundamentals data
   - Get free API key at: https://www.alphavantage.co/support/#api-key
   - Add to `backend/.env`: `ALPHA_VANTAGE_API_KEY=your_key_here`

2. **Google Gemini** - For LLM analysis (optional for demo)
   - Get API key at: https://makersuite.google.com/app/apikey
   - Add to `backend/.env`: `GOOGLE_API_KEY=your_key_here`

3. **News Sources** - Multiple free sources (no API key needed)
   - Google News RSS feeds
   - Reuters business news
   - MarketWatch financial news
   - Yahoo Finance news
   - Finviz headlines

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd stock_platform
   ```

2. **Quick Start with Docker** (Recommended)
   ```bash
   ./start.sh
   ```
   This will automatically:
   - Check for Docker/Docker Compose
   - Create environment files
   - Start all services (database, backend, frontend)
   - Display service URLs

3. **Manual Setup**

   **Backend Setup:**
   ```bash
   cd backend
   cp env.example .env
   # Edit .env with your API keys
   pip install -r requirements.txt
   
   # Start PostgreSQL and Redis (via Docker)
   docker run -d --name postgres -p 5432:5432 -e POSTGRES_DB=stock_platform -e POSTGRES_USER=username -e POSTGRES_PASSWORD=password postgres:15
   docker run -d --name redis -p 6379:6379 redis:7-alpine
   
   # Run migrations
   alembic upgrade head
   
   # Start backend
   uvicorn app.main:app --reload
   ```

   **Frontend Setup:**
   ```bash
   cd frontend
   npm install
   echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
   npm run dev
   ```

## 🎯 Usage

1. **Access the Platform**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

2. **Analyze a Stock**
   - Enter a stock ticker (e.g., AAPL, GOOGL, MSFT) in the search bar
   - Click "Analyze" or press Enter
   - View AI-powered recommendation with:
     - Buy/Hold/Sell decision
     - Confidence score
     - Price ranges
     - Key factors
     - Recent news sentiment

3. **Explore Features**
   - **Smart Recommendations**: AI-powered buy/sell alerts
   - **Technical Analysis**: RSI, MACD, moving averages
   - **News Sentiment**: AI-summarized headlines from 5+ free sources (no API keys needed)
   - **Valuation Metrics**: P/E ratios, DCF analysis, margin of safety

## 📊 API Endpoints

### Main Endpoints
- `GET /api/search/{ticker}` - Comprehensive stock analysis
- `GET /api/recommendation/{ticker}` - Get buy/sell recommendation
- `GET /api/news/{ticker}` - Stock news with sentiment analysis
- `GET /api/analysis/{ticker}` - Detailed fundamental analysis
- `GET /api/trending` - Trending stocks
- `GET /api/health` - Health check

### Example Response
```json
{
  "ticker": "AAPL",
  "action": "BUY",
  "confidence_score": 0.78,
  "reasoning": "Strong fundamentals with attractive valuation",
  "buy_range_low": 150.00,
  "buy_range_high": 155.00,
  "risk_level": "low",
  "recent_news": [...]
}
```

## 🛠️ Development

### Project Structure
```
stock_platform/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── services/       # Core analysis services
│   │   ├── models.py       # Database models
│   │   └── main.py        # FastAPI app
│   └── requirements.txt
├── frontend/               # Next.js frontend
│   ├── app/               # App router pages
│   ├── components/        # React components
│   └── lib/              # Utilities
└── docker-compose.yml    # Development environment
```

### Key Services

1. **Stock Screener Engine** (`backend/app/services/stock_screener.py`)
   - Calculates P/E, FCF, technical indicators
   - Performs DCF valuation analysis
   - Generates quality scores

2. **News Sentiment Collector** (`backend/app/services/news_collector.py`)
   - Scrapes 5+ free news sources (Google News, Reuters, MarketWatch, Yahoo, Finviz)
   - No API keys required for news collection
   - Uses LLM for sentiment analysis and summarization
   - Extracts actionable signals and impact levels

3. **LLM Inference Layer** (`backend/app/services/llm_inference.py`)
   - Combines all signals
   - Generates recommendations with reasoning
   - Calculates price ranges

### Adding New Features

1. **New Data Sources**: Extend the stock screener or news collector
2. **Additional Metrics**: Add to database models and calculation logic
3. **Enhanced UI**: Create new React components in `frontend/components/`
4. **Custom Analysis**: Modify the LLM prompts for different investment strategies

## 🚀 Deployment

### Production Setup
1. Set up PostgreSQL and Redis instances
2. Configure environment variables with production values
3. Build and deploy:
   ```bash
   # Backend
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   
   # Frontend
   cd frontend
   npm run build
   npm start
   ```

### Environment Variables for Production
```bash
# Backend
DATABASE_URL=postgresql://user:pass@host:5432/db
GOOGLE_API_KEY=your_production_key
DEBUG=False
CORS_ORIGINS=["https://yourdomain.com"]

# Frontend
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

## 🧪 Testing

### Quick API Tests
Test your setup with the included test scripts:

```bash
# Test stock analysis (Alpha Vantage + yfinance)
python3 test_stock_analysis.py

# Test news collection (multiple free sources)
python3 test_news.py
```

### Full Test Suite
```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

### Manual Testing
1. **Start the platform**: `./start.sh`
2. **Open frontend**: http://localhost:3000
3. **Test stock search**: Enter "AAPL" and click Analyze
4. **Check API directly**: http://localhost:8000/docs

## 📈 Performance

- **Analysis Speed**: ~5-10 seconds per stock
- **Concurrent Users**: Supports 100+ concurrent analyses
- **Data Freshness**: Hourly updates for stock data
- **News Updates**: Real-time news collection every 30 minutes

## 🔧 Troubleshooting

### Common Issues

1. **API Key Errors**
   - Ensure all required API keys are set in `.env`
   - Check API key validity and rate limits

2. **Database Connection**
   - Verify PostgreSQL is running on port 5432
   - Check database credentials in environment variables

3. **News Collection Issues**
   - Free news sources may occasionally block requests (normal behavior)
   - Platform uses 5+ sources, so some failures are expected
   - If no news appears, check network connectivity
   - RSS feeds and web scraping may have intermittent issues

4. **LLM Analysis Slow**
   - Gemini API has rate limits
   - Consider using local LLM models for high-volume usage

### Performance Tips

1. **Caching**: Implement Redis caching for frequently requested stocks
2. **Background Jobs**: Use Celery for long-running analysis tasks
3. **Database Optimization**: Add indexes for frequently queried fields
4. **CDN**: Use CDN for frontend assets in production

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

For issues and questions:
- Create an issue in the GitHub repository
- Check the troubleshooting section above
- Review API documentation at http://localhost:8000/docs 