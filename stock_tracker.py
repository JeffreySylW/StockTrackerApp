import requests
from bs4 import BeautifulSoup
import json
import time
import os
import logging
from datetime import datetime
import re
import csv
import yfinance as yf

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_tracker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('stock_tracker')

class StockTracker:
    def __init__(self, data_file="stock_history.json"):
        """Initialize the stock tracker with a data file for storing price history."""
        self.data_file = data_file
        self.stock_history = self.load_stock_history()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def load_stock_history(self):
        """Load stock history from JSON file."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {self.data_file}")
                return {}
        return {}

    def save_stock_history(self):
        """Save stock history to JSON file."""
        with open(self.data_file, 'w') as f:
            json.dump(self.stock_history, f, indent=2)
        
        # Also export to CSV for easier analysis
        csv_file = self.data_file.replace('.json', '.csv')
        try:
            with open(csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Symbol', 'Timestamp', 'Price', 'Change', 'Percent_Change'])
                
                for symbol, data in self.stock_history.items():
                    for record in data['history']:
                        writer.writerow([
                            symbol,
                            record['timestamp'],
                            record['price'],
                            record.get('change', ''),
                            record.get('percent_change', '')
                        ])
                        
            logger.info(f"Exported stock history to CSV: {csv_file}")
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")

    def get_stock_data_from_api(self, symbol):
        """Get stock data from Yahoo Finance API."""
        try:
            # Use yfinance to get current stock data
            stock = yf.Ticker(symbol)
            stock_info = stock.info
            
            if not stock_info:
                logger.warning(f"No stock info found for {symbol}")
                return None
                
            # Get the current price
            current_price = stock_info.get('currentPrice') or stock_info.get('regularMarketPrice')
            if not current_price:
                logger.warning(f"No price data found for {symbol}")
                return None
                
            # Get the price change
            previous_close = stock_info.get('previousClose')
            if previous_close:
                change = current_price - previous_close
                percent_change = (change / previous_close) * 100
            else:
                change = None
                percent_change = None
                
            return {
                'price': current_price,
                'change': change,
                'percent_change': percent_change,
                'volume': stock_info.get('volume'),
                'market_cap': stock_info.get('marketCap'),
                'high_52w': stock_info.get('fiftyTwoWeekHigh'),
                'low_52w': stock_info.get('fiftyTwoWeekLow')
            }
            
        except Exception as e:
            logger.error(f"Error getting stock data for {symbol}: {e}")
            return None

    def track_stock(self, symbol, check_interval=300, notify_thresholds=None):
        """
        Track stock price at a given interval.
        
        Args:
            symbol: Stock symbol to track
            check_interval: How often to check price in seconds
            notify_thresholds: Dict with 'price' and 'percent' thresholds for alerts
        """
        symbol = symbol.upper()
        logger.info(f"Starting stock tracking for {symbol}")
        
        # Initialize stock in history if not present
        if symbol not in self.stock_history:
            self.stock_history[symbol] = {
                "history": []
            }
        
        if notify_thresholds is None:
            notify_thresholds = {
                'price': 1.0,      # Alert on $1 change
                'percent': 2.0     # Alert on 2% change
            }
            
        while True:
            try:
                # Get stock data
                stock_data = self.get_stock_data_from_api(symbol)
                
                if stock_data:
                    price = stock_data['price']
                    timestamp = datetime.now().isoformat()
                    
                    # Add to history
                    entry = {
                        "price": price,
                        "timestamp": timestamp
                    }
                    
                    # Add change data if available
                    if stock_data['change'] is not None:
                        entry['change'] = stock_data['change']
                        entry['percent_change'] = stock_data['percent_change']
                    
                    self.stock_history[symbol]["history"].append(entry)
                    
                    # Log the current price
                    change_str = f", Change: ${stock_data['change']:.2f} ({stock_data['percent_change']:.2f}%)" if stock_data['change'] is not None else ""
                    logger.info(f"Stock price for {symbol}: ${price:.2f}{change_str}")
                    
                    # Save history
                    self.save_stock_history()
                    
                    # Check for significant changes to alert on
                    self.check_price_alerts(symbol, notify_thresholds)
                else:
                    logger.warning(f"Failed to get price data for {symbol}")
                
            except Exception as e:
                logger.error(f"Error tracking {symbol}: {e}")
            
            # Sleep until next check
            logger.info(f"Next update in {check_interval} seconds")
            time.sleep(check_interval)

    def check_price_alerts(self, symbol, thresholds):
        """Check if there are significant price changes that should trigger alerts."""
        history = self.stock_history[symbol]["history"]
        if len(history) < 2:
            return
        
        current_price = history[-1]["price"]
        
        # Check for threshold crossing compared to last check
        previous_price = history[-2]["price"]
        abs_change = abs(current_price - previous_price)
        percent_change = (abs_change / previous_price) * 100
        
        if abs_change >= thresholds['price'] or percent_change >= thresholds['percent']:
            change_type = "increased" if current_price > previous_price else "decreased"
            logger.info(f"PRICE ALERT: {symbol} has {change_type} by ${abs_change:.2f} ({percent_change:.2f}%) " +
                      f"from ${previous_price:.2f} to ${current_price:.2f}")

    def get_price_summary(self, symbol):
        """Get a summary of price history for a stock."""
        if symbol not in self.stock_history or not self.stock_history[symbol]["history"]:
            logger.warning(f"No price history for {symbol}")
            return None
        
        history = self.stock_history[symbol]["history"]
        
        # Get current, first, min and max prices
        current_price = history[-1]["price"]
        first_price = history[0]["price"]
        min_price = min(entry["price"] for entry in history)
        max_price = max(entry["price"] for entry in history)
        
        # Calculate overall change
        price_change = current_price - first_price
        percent_change = (price_change / first_price) * 100
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "first_tracked_price": first_price,
            "price_change": price_change,
            "percent_change": percent_change,
            "min_price": min_price,
            "max_price": max_price,
            "num_checks": len(history),
            "first_checked": history[0]["timestamp"],
            "last_checked": history[-1]["timestamp"]
        }

def main():
    """Main function to run the stock tracker."""
    # Check if yfinance is installed
    try:
        import yfinance
    except ImportError:
        print("Error: Required package 'yfinance' is not installed.")
        print("Please install it using: pip install yfinance")
        return
    
    print("Welcome to the Stock Tracker!")
    
    # Get user input for tracking
    symbol = input("Enter the stock symbol to track (e.g., AAPL): ").strip().upper()
    
    try:
        check_interval = int(input("Enter how often to check the price (in seconds, default 300): ") or "300")
    except ValueError:
        check_interval = 300
        print("Invalid input. Using default check interval of 300 seconds (5 minutes).")
    
    # Ask for alert thresholds
    try:
        price_threshold = float(input("Alert when price changes by $ amount (default 1.0): ") or "1.0")
    except ValueError:
        price_threshold = 1.0
        print("Invalid input. Using default price threshold of $1.0.")
    
    try:
        percent_threshold = float(input("Alert when price changes by percent (default 2.0): ") or "2.0")
    except ValueError:
        percent_threshold = 2.0
        print("Invalid input. Using default percent threshold of 2.0%.")
    
    notify_thresholds = {
        'price': price_threshold,
        'percent': percent_threshold
    }
    
    # Start tracking
    tracker = StockTracker()
    print(f"\nStarting to track {symbol} every {check_interval} seconds...")
    print(f"Price alerts will trigger on ${price_threshold:.2f} or {percent_threshold:.2f}% changes")
    print("Press Ctrl+C to stop\n")
    
    try:
        tracker.track_stock(symbol, check_interval, notify_thresholds)
    except KeyboardInterrupt:
        print("\nStopped tracking.")
        
        # Show summary
        summary = tracker.get_price_summary(symbol)
        if summary:
            print("\nSummary of tracking session:")
            print(f"Symbol: {summary['symbol']}")
            print(f"Current price: ${summary['current_price']:.2f}")
            print(f"Price change: ${summary['price_change']:.2f} ({summary['percent_change']:.2f}%)")
            print(f"Price range: ${summary['min_price']:.2f} - ${summary['max_price']:.2f}")
            print(f"Checks performed: {summary['num_checks']}")
            print(f"Data saved to: {tracker.data_file} and {tracker.data_file.replace('.json', '.csv')}")

if __name__ == "__main__":
    main()