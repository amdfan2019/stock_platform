#!/usr/bin/env python3
"""
Test script to verify stock analysis works with Alpha Vantage API
"""

import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.stock_screener import StockScreener

async def test_stock_analysis():
    """Test stock analysis for a sample stock"""
    
    print("🧪 Testing Stock Analysis")
    print("=" * 40)
    
    screener = StockScreener()
    
    # Test with a popular stock
    ticker = "AAPL"
    print(f"📊 Analyzing {ticker}...")
    
    try:
        analysis = await screener.analyze_stock(ticker)
        
        print(f"\n✅ Successfully analyzed {ticker}")
        print(f"📈 Company: {analysis.get('company_name', 'Unknown')}")
        print(f"💰 Current Price: ${analysis.get('current_price', 0):.2f}")
        print(f"🏢 Market Cap: ${analysis.get('market_cap', 0):,.0f}")
        
        print(f"\n📊 Valuation Metrics:")
        print(f"  • P/E Ratio: {analysis.get('pe_ratio', 'N/A')}")
        print(f"  • Forward P/E: {analysis.get('forward_pe', 'N/A')}")
        print(f"  • PEG Ratio: {analysis.get('peg_ratio', 'N/A')}")
        print(f"  • Price-to-Book: {analysis.get('price_to_book', 'N/A')}")
        
        print(f"\n💪 Financial Health:")
        print(f"  • Debt-to-Equity: {analysis.get('debt_to_equity', 'N/A')}")
        print(f"  • Current Ratio: {analysis.get('current_ratio', 'N/A')}")
        print(f"  • ROE: {analysis.get('return_on_equity', 'N/A')}")
        
        print(f"\n📈 Technical Indicators:")
        print(f"  • SMA 50: ${analysis.get('sma_50', 0):.2f}")
        print(f"  • SMA 200: ${analysis.get('sma_200', 0):.2f}")
        print(f"  • RSI (14): {analysis.get('rsi_14', 'N/A')}")
        print(f"  • MACD Signal: {analysis.get('macd_signal', 'N/A')}")
        
        print(f"\n⭐ Quality Score: {analysis.get('quality_score', 0):.1f}/100")
        
        # Test intrinsic value calculation
        print(f"\n💎 Testing intrinsic value calculation...")
        intrinsic_value, margin_of_safety = await screener.calculate_intrinsic_value(analysis)
        
        if intrinsic_value:
            print(f"📊 Intrinsic Value: ${intrinsic_value:.2f}")
            print(f"🛡️ Margin of Safety: {margin_of_safety:.1f}%")
        else:
            print(f"⚠️ Could not calculate intrinsic value (insufficient data)")
        
        print(f"\n🎉 Stock analysis test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during stock analysis: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Set up environment
    os.environ.setdefault('GOOGLE_API_KEY', 'AIzaSyCb_UCb-qQUXvJs6oac2OvyvsdqC_09sOg')
    os.environ.setdefault('ALPHA_VANTAGE_API_KEY', 'U9NQ5J3D0NR5QTHD')
    os.environ.setdefault('NEWS_API_KEY', '')
    
    asyncio.run(test_stock_analysis()) 