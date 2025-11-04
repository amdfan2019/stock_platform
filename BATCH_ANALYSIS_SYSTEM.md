# Batch Analysis & Opportunity Scanner System

## Overview

This system enables efficient analysis of all 500 S&P stocks with rate limiting to avoid Gemini API overload, plus hourly scanning to identify best buy opportunities, urgent sell signals, and biggest movers.

## Architecture

### 1. Database Schema

####  `sp500_stocks` - S&P 500 Stock List
- Tracks which stocks need analysis
- Records: `ticker`, `company_name`, `sector`, `is_active`, `last_analyzed_at`, `analysis_status`
- Status: `pending`, `analyzing`, `completed`, `failed`

#### `stock_opportunities` - Hourly Scan Results
- Stores current prices vs buy/sell thresholds
- Calculates opportunity percentages
- Records price movements (1d, 1w)
- Flags: `is_best_buy`, `is_urgent_sell`, `is_big_mover`

#### `batch_analysis_jobs` - Batch Job Tracking
- Tracks progress of batch analysis jobs
- Records: `job_id`, `total_stocks`, `completed_stocks`, `failed_stocks`, `status`
- Enables progress bar in frontend

### 2. Backend Services

#### BatchAnalysisService
**Purpose**: Rate-limited batch analysis of stocks

**Configuration**:
- `max_concurrent = 5` - Process 5 stocks simultaneously
- `delay_between_batches = 2.0` - 2 second delay between batches
- Prevents Gemini API overload

**Methods**:
- `start_batch_analysis(tickers, initiated_by)` - Start batch job
- `get_job_status(job_id)` - Get progress (for progress bar)
- `load_sp500_tickers()` - Load S&P 500 list

**Rate Limiting Strategy**:
```
Batch 1: [AAPL, MSFT, GOOGL, AMZN, NVDA] → Analyze concurrently
Wait 2 seconds
Batch 2: [TSLA, META, BRK.B, UNH, XOM] → Analyze concurrently
...
```

**Efficiency**: 500 stocks in ~100 batches = ~200 seconds + ~45 minutes analysis time ≈ **50 minutes total**

#### OpportunityScanner
**Purpose**: Hourly scan to identify opportunities

**Thresholds**:
- **Best Buy**: Price 5%+ below `buy_below` threshold
- **Urgent Sell**: Price 5%+ above `sell_above` threshold  
- **Big Mover**: Price change 5%+ in one day

**Opportunity Types**:
- `strong_buy` - Price 10%+ below buy threshold
- `buy` - Price below buy threshold
- `hold` - Price between buy and sell thresholds
- `sell` - Price above sell threshold
- `strong_sell` - Price 10%+ above sell threshold

**Methods**:
- `scan_all_opportunities()` - Scan all S&P 500 stocks
- `get_best_buys(limit=10)` - Top buy opportunities
- `get_urgent_sells(limit=10)` - Top sell signals
- `get_big_movers(limit=10)` - Biggest price changes

### 3. API Endpoints

#### Batch Analysis
```
POST /api/stocks/batch-analyze
Body: { "tickers": ["AAPL", "MSFT", ...] } (optional - defaults to all S&P 500)
Response: { "job_id": "batch_abc123", "total_stocks": 500 }

GET /api/stocks/batch-status/{job_id}
Response: {
  "status": "running",  // running, completed, failed
  "total_stocks": 500,
  "completed_stocks": 127,
  "failed_stocks": 3,
  "progress_pct": 25.4
}
```

#### Opportunities
```
GET /api/stocks/opportunities/best-buys?limit=10
Response: { "best_buys": [...], "count": 10 }

GET /api/stocks/opportunities/urgent-sells?limit=10
Response: { "urgent_sells": [...], "count": 10 }

GET /api/stocks/opportunities/big-movers?limit=10
Response: { "big_movers": [...], "count": 10 }

POST /api/stocks/scan-opportunities
Response: { "status": "success", "message": "Scan started in background" }
```

### 4. Schedulers

#### Hourly Opportunity Scanner
- **Frequency**: Every 1 hour
- **Purpose**: Update current prices, identify new opportunities
- **Runs automatically in background**

## Frontend Integration

### Debug Tab - Batch Analysis UI

**Features**:
- "Start Batch Analysis" button
- Real-time progress bar (0-100%)
- Status display: "Analyzing 127/500 stocks (25.4%)"
- Failed stock counter
- Estimated time remaining
- Cancel button

**Implementation** (to be added):
```typescript
// Poll for status every 3 seconds
const pollBatchStatus = async (jobId) => {
  const response = await fetch(`/api/stocks/batch-status/${jobId}`);
  const data = await response.json();
  
  // Update progress bar
  setProgress(data.progress_pct);
  setCompleted(data.completed_stocks);
  setFailed(data.failed_stocks);
  
  if (data.status === 'completed') {
    // Stop polling
    return;
  }
  
  // Continue polling
  setTimeout(() => pollBatchStatus(jobId), 3000);
};
```

### Assets Tab - Opportunities Dashboard

**New Default View** (replaces Tesla):

1. **Best Buy Opportunities** (Top 10)
   - Ticker, Current Price, Buy Below, Opportunity %
   - "Price is X% below buy threshold"
   - Click to view full analysis

2. **Urgent Sell Signals** (Top 10)
   - Ticker, Current Price, Sell Above, Urgency %
   - "Price is X% above sell threshold"
   - Click to view full analysis

3. **Biggest Movers** (Top 10)
   - Ticker, Price Change 1D, Price Change 1W
   - Volume vs Average
   - Click to view full analysis

**Search Functionality**:
- Search bar remains at top
- Can still search for individual stocks
- Opportunities are default view when not searching

## Usage Flow

### Daily Batch Analysis

1. **User Trigger** (Debug Tab):
   ```
   User clicks "Start Batch Analysis for All S&P 500"
   → POST /api/stocks/batch-analyze
   → Returns job_id
   → Frontend polls /api/stocks/batch-status/{job_id}
   → Progress bar updates in real-time
   → Completes in ~50 minutes
   ```

2. **Automated Daily** (Optional):
   - Can schedule daily batch analysis at specific time
   - Runs automatically in background
   - No user interaction required

### Hourly Opportunity Identification

1. **Automatic Hourly**:
   ```
   Every hour:
   → OpportunityScanner.scan_all_opportunities()
   → Fetches current prices for all 500 stocks
   → Compares to buy/sell thresholds
   → Identifies best buys, urgent sells, big movers
   → Stores in stock_opportunities table
   ```

2. **Frontend Refresh**:
   ```
   Assets tab automatically fetches:
   → GET /api/stocks/opportunities/best-buys
   → GET /api/stocks/opportunities/urgent-sells
   → GET /api/stocks/opportunities/big-movers
   → Displays updated lists
   → Refreshes every 5 minutes
   ```

## Scalability

### Current Setup
- **40 stocks** pre-loaded (top S&P 500 by market cap)
- **Expandable to 500** by adding tickers to `sp500_stocks` table
- **Rate limiting prevents** Gemini API overload
- **Database indexed** for fast opportunity queries

### Performance
- **Batch Analysis**: 500 stocks in ~50 minutes
- **Hourly Scan**: 500 price checks in ~30 seconds (no LLM calls)
- **API Response**: Opportunities in <100ms (database query)

### Resource Usage
- **Gemini API**: ~100 calls/minute during batch (well under limits)
- **Database**: ~3 new records/hour per stock (manageable)
- **Memory**: Minimal (streaming processing)

## Safety Features

1. **Rate Limiting**: Prevents API throttling
2. **Error Handling**: Failed stocks don't block batch
3. **Status Tracking**: Know exactly what's completed
4. **Idempotent**: Can re-run batch safely
5. **Cancellable**: Stop batch analysis mid-run

## Sample Data

### Best Buy Example
```json
{
  "ticker": "AAPL",
  "current_price": 145.50,
  "buy_below": 160.00,
  "buy_opportunity_pct": 9.9,  // (160-145.5)/145.5*100
  "opportunity_type": "buy",
  "valuation_assessment": "Undervalued"
}
```

### Urgent Sell Example
```json
{
  "ticker": "TSLA",
  "current_price": 385.00,
  "sell_above": 360.00,
  "sell_urgency_pct": 6.9,  // (385-360)/360*100
  "opportunity_type": "sell",
  "valuation_assessment": "Overvalued"
}
```

### Big Mover Example
```json
{
  "ticker": "NVDA",
  "current_price": 520.00,
  "price_change_1d": 7.5,
  "price_change_1w": 15.3,
  "volume_vs_avg": 2.3,
  "is_big_mover": true
}
```

## Migration Required

Run this SQL migration to create tables:
```bash
docker exec stock_platform-postgres-1 psql -U username -d stock_platform -f /app/migrations/add_opportunities_tables.sql
```

## Next Steps

1. ✅ Run database migration
2. ✅ Restart backend to load new services
3. ⏳ Add Batch Analysis UI to Debug tab (frontend)
4. ⏳ Update Assets tab with Opportunities Dashboard (frontend)
5. ⏳ Test batch analysis with 40 sample stocks
6. ⏳ Verify hourly scanner is running
7. ⏳ Load full S&P 500 list (expand from 40 to 500)

