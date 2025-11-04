# Analysis Validation System

## 🎯 Purpose

Automatically validate that all stock analyses have required fields populated and alert you to incomplete or failed analyses.

---

## 📊 What Gets Validated

### Required Fields Checked:
1. **Basic Fields**
   - `ticker`
   - `current_price`
   - `analysis_date`

2. **Valuation Fields**
   - `valuation_assessment`
   - `fair_value_price`
   - `buy_below`
   - `sell_above`

3. **Master Analysis Fields**
   - `company_description`
   - `analysis` (investment thesis)
   - `forward_outlook`
   - `market_comparison`

4. **Insights Fields**
   - `key_insights` (must have at least 1 item)
   - `risk_factors` (must have at least 1 item)
   - `catalysts` (must have at least 1 item)

---

## 🔄 How It Works

### 1. **Automatic Validation During Batch Analysis**
- After each stock is analyzed, the system automatically validates it
- If any required fields are missing, the stock is marked as `incomplete`
- Validation results are logged with specific error details

### 2. **API Endpoint for Failed Analyses**
```bash
GET http://localhost:8000/api/stocks/failed-analyses
```

Returns:
```json
{
  "failed_analyses": [
    {
      "ticker": "ORCL",
      "company_name": "Oracle Corporation",
      "sector": "Technology",
      "last_analyzed_at": "2025-11-03T13:42:58.046239",
      "error_count": 1,
      "errors": [
        "Missing or empty: key_insights"
      ]
    }
  ],
  "count": 459,
  "timestamp": "2025-11-03T14:30:00.000000"
}
```

### 3. **Debug Tab UI Section**
- Displays all incomplete/failed analyses in a table
- Shows:
  - Ticker
  - Company name
  - Sector
  - Specific errors
  - Last analyzed timestamp
- Includes a "Refresh" button to check for new failures
- Auto-loads when you open the Debug tab

---

## 🐛 Why ORCL Had No Analysis

**Finding:** ORCL was analyzed but `key_insights` was empty/missing.

**Root Cause:** LLM timeout or incomplete JSON response during master analysis generation.

**Status:** ORCL is now flagged in the "Incomplete / Failed Analyses" section of the Debug tab.

---

## 🔧 Components Added

### Backend
1. **`backend/app/services/analysis_validator.py`**
   - `AnalysisValidator` class with validation logic
   - `validate_analysis()` - checks a single stock
   - `get_all_failed_analyses()` - returns all incomplete analyses
   - `mark_analysis_validation_status()` - updates stock status

2. **`backend/app/services/batch_worker.py`** (Updated)
   - Added validation call after each analysis completes
   - Marks stocks as `incomplete` if validation fails

3. **`backend/app/main.py`** (Updated)
   - Added `GET /api/stocks/failed-analyses` endpoint

### Frontend
1. **`frontend/components/DebugGeminiCalls.tsx`** (Updated)
   - Added `FailedAnalysis` interface
   - Added failed analyses state and fetch function
   - Added new UI section: "Incomplete / Failed Analyses"
   - Shows table with ticker, company, sector, errors, timestamp
   - Displays success message if all analyses are complete

---

## 📈 Current Statistics

As of last check:
- **459 stocks** have incomplete analyses
- Most common error: `"Missing or empty: key_insights"`
- All failures are now visible in the Debug tab

---

## 🎯 Next Steps

### To Fix Incomplete Analyses:
1. Go to Debug tab → "Incomplete / Failed Analyses" section
2. Review which stocks have errors
3. Run a new batch analysis to re-analyze failed stocks
4. Validation will run automatically and update the list

### Future Improvements:
- Add "Re-analyze Failed" button to automatically trigger analysis for incomplete stocks
- Add validation warnings to individual stock pages
- Implement LLM retry logic for timeout errors
- Add field-level completion percentage to batch progress

---

## 💡 Key Benefits

✅ **Visibility**: Know exactly which stocks have incomplete data
✅ **Debugging**: See specific errors for each failed analysis  
✅ **Quality Control**: Ensure all fields are populated before using data
✅ **Automation**: Validation runs automatically during batch analysis
✅ **User Experience**: Alerts you to issues rather than showing empty fields

---

## 🧪 Testing

To test the validation system:

1. **View failed analyses:**
```bash
curl http://localhost:8000/api/stocks/failed-analyses | jq
```

2. **Check specific stock:**
```bash
curl http://localhost:8000/api/stocks/failed-analyses | jq '.failed_analyses[] | select(.ticker == "ORCL")'
```

3. **Frontend**: Go to Dashboard → Debug → Scroll to "Incomplete / Failed Analyses"

