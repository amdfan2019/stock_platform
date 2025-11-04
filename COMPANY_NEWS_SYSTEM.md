# Company News Analysis System

## Overview

The stock news analysis system has been completely redesigned to work like the market news system - **actually reading articles and maintaining persistent company summaries**.

## Architecture

### 1. Database Schema

#### `CompanyNewsSummary` Table
- **Purpose**: Persistent company profile that updates incrementally
- **Fields**:
  - Company overview (name, sector)
  - Latest earnings (date, result, EPS, revenue, guidance)
  - Persistent profile (risks, opportunities, products, management, regulatory)
  - Summary texts (company_summary, recent_developments_summary, outlook)
  - Metadata (articles processed, last update)

#### `StockArticle` Table
- **Purpose**: Individual articles with full content and LLM analysis
- **Fields**:
  - Article content (URL, title, source, full_text, summary)
  - LLM analysis (is_significant, article_type, key_points, sentiment)
  - Tracking (was_used_in_summary_update, processed_at)

#### `StockNewsAnalysis` Table (Enhanced)
- **Purpose**: Store comprehensive news analysis for API responses
- **New Fields**: All CompanyNewsSummary fields plus analysis metadata

### 2. CompanyNewsCollector Service

Located: `backend/app/services/company_news_collector.py`

**Main Function**: `collect_and_analyze(days_back=30)`

**Workflow**:

1. **Fetch Article URLs** from yfinance
   - Uses new yfinance API structure (nested under 'content')
   - Extracts: title, summary, URL, published date, source
   
2. **Read Article Content**
   - **Primary**: Attempts to extract full text with `newspaper3k`
   - **Fallback**: Uses yfinance-provided summary (handles paywalls)
   - Minimum 50 characters required
   
3. **Analyze Each Article** with LLM
   - Determine significance (is this earnings/major news?)
   - Classify type (earnings, product, management, regulatory, general)
   - Extract key points
   - Calculate sentiment (-1 to 1)
   - Assess if information is new vs. existing summary
   
4. **Store Articles** in database
   - Save full analysis to `StockArticle` table
   - Deduplication by URL
   
5. **Decide if Summary Needs Updating**
   - New company: Always update
   - Has significant articles: Update
   - 20+ articles accumulated: Update
   - Summary >30 days old: Update
   
6. **Generate Company Summary** with LLM
   - Comprehensive company profile
   - Latest earnings details (if available)
   - Key risks and opportunities
   - Product developments
   - Management changes
   - Regulatory issues
   - Competitive position
   - Forward outlook
   
7. **Store Summary**
   - Update `CompanyNewsSummary`
   - Create `StockNewsAnalysis` record
   - Mark articles as used

### 3. StockNewsAgentV2

Located: `backend/app/agents/stock_news_agent_v2.py`

**Purpose**: Orchestrates news collection and integrates with agent network

**Key Methods**:
- `run_cycle()`: Triggers comprehensive news analysis
- `get_latest_news_analysis()`: Retrieves stored analysis
- `_calculate_sentiment()`: Derives sentiment from risks/opportunities
- `_store_news_analysis()`: Saves to database

### 4. API Integration

**Endpoint**: `GET /api/stock/{ticker}/analysis`

**Response Now Includes**:
```json
{
  "ticker": "TSLA",
  "company_summary": "Tesla, Inc. designs, develops...",
  "recent_developments": "Tesla chair Robyn Denholm...",
  "outlook": "Tesla's outlook is shaped by...",
  "latest_earnings": {
    "date": null,
    "result": null,
    "summary": "Recent earnings reports...",
    "eps_actual": null,
    "eps_expected": null
  },
  "key_risks": [
    "Stock market volatility...",
    "CEO reputation concerns...",
    "Competitive pressures..."
  ],
  "key_opportunities": [
    "Mass-market EV development...",
    "AI advancement opportunities...",
    "Battery technology innovation..."
  ],
  "recent_products": [
    {
      "date": "2025-10-31",
      "product": "Cybercab",
      "description": "Potential for mass-market EV..."
    }
  ],
  "management_changes": [],
  "regulatory_issues": [],
  "competitive_position": "Tesla maintains a leading...",
  "articles_analyzed": 10,
  "news_last_updated": "2025-11-02T02:07:39"
}
```

## Key Features

### 1. Persistent Summaries
- Company profiles **persist across analyses**
- Only update when **materially new information** emerges
- Efficient: Don't re-analyze everything every time

### 2. Deep Article Reading
- **Primary**: Full article extraction with newspaper3k
- **Fallback**: yfinance summaries (handles paywalls gracefully)
- LLM analyzes full content, not just headlines

### 3. Intelligent Updating
- Articles classified by significance
- Major news (earnings, products, management) triggers updates
- Minor news accumulates until threshold

### 4. Comprehensive Analysis
- Company overview and business description
- Specific earnings data (EPS, revenue, guidance)
- Structured risks and opportunities
- Product pipeline tracking
- Management and regulatory monitoring
- Forward-looking outlook

### 5. Scalability
- **Per-stock storage**: `CompanyNewsSummary` (one row per stock)
- **Article storage**: `StockArticle` (grows linearly with articles)
- **Efficient updates**: Only process new articles
- **Deduplication**: By URL to avoid redundant processing
- **Can scale to 500+ stocks**

## Data Flow

```
1. yfinance → Fetch article URLs and summaries
2. For each article:
   - newspaper3k → Extract full text (or use yfinance summary)
   - LLM → Analyze significance, type, sentiment
   - Database → Store in StockArticle
3. If significant updates exist:
   - LLM → Generate comprehensive company summary
   - Database → Update CompanyNewsSummary
   - Database → Store StockNewsAnalysis
4. API → Retrieve and return comprehensive analysis
```

## Example: Tesla (TSLA)

**Articles Processed**: 10 (from yfinance)

**Generated Insights**:
- **Company**: Leader in EVs and AI for autonomous driving
- **Recent News**: Cybercab as potential mass-market vehicle
- **Risks**: Market volatility, CEO reputation, competition
- **Opportunities**: Affordable EV, AI leadership, battery innovation
- **Products**: Cybercab development underway

**How It Works**:
1. Fetched 10 recent articles about Tesla
2. Extracted content (paywalled articles used yfinance summaries)
3. LLM analyzed each article for significance
4. Generated comprehensive company profile
5. Stored for future API calls
6. Will update when new earnings or major news appears

## Benefits

1. **Actual Content Analysis**: Not just headlines - full articles
2. **Persistent Knowledge**: Company profiles persist and evolve
3. **Efficient Updates**: Only update when new information emerges
4. **Structured Data**: Earnings, risks, opportunities in standard format
5. **Scalable**: Can handle hundreds of stocks
6. **Paywall Resistant**: Falls back to yfinance summaries gracefully

## Configuration

**Days Lookback**: 30 days (configurable in `collect_and_analyze`)
**Update Triggers**:
- New company
- Significant articles (earnings, products, management)
- 20+ articles accumulated
- 30+ days since last update

**Article Processing**:
- Limit: 15 most recent articles per run
- Minimum content: 50 characters
- LLM analyzes significance before storing

## Future Enhancements

- [ ] Additional news sources beyond yfinance
- [ ] Earnings call transcript analysis
- [ ] SEC filing integration
- [ ] Sentiment trend tracking over time
- [ ] Peer comparison in news context

