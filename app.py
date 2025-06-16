from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import ntplib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import asyncio
import requests
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import json
import time

load_dotenv()  # Load environment variables from .env file

# MongoDB connection initialization
def init_mongodb():
    try:
        # Get MongoDB URI from environment variable
        mongo_uri = os.getenv('MONGODB_URI')
        client = MongoClient(mongo_uri)
        
        # Test the connection
        client.admin.command('ping')
        print("Successfully connected to MongoDB!")
        
        # Check if db_option database exists
        db_list = client.list_database_names()
        if 'db_option' not in db_list:
            print("Creating db_option database...")
            # Create the database by inserting a document
            client['db_option'].create_collection('init')
            print("db_option database created successfully!")
        else:
            print("db_option database already exists")
            
        return client
    except ConnectionFailure as e:
        print(f"Could not connect to MongoDB: {e}")
        return None

# Initialize MongoDB connection
mongo_client = init_mongodb()
db = mongo_client['db_option'] if mongo_client else None

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

async def check_market_time():
    try:
        # Get time from NTP server
        ntp_client = ntplib.NTPClient()
        response = ntp_client.request('pool.ntp.org')
        # Convert NTP time to datetime and set timezone to ET
        current_time = datetime.fromtimestamp(response.tx_time, ZoneInfo("America/New_York"))
    except Exception as e:
        print(f"Error getting NTP time: {e}")
        # Fallback to local time if NTP fails
        current_time = datetime.now(ZoneInfo("America/New_York"))

    print("current_time: ", current_time)
    
    # Check if it's a weekday (0 = Monday, 6 = Sunday)
    if current_time.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Create time objects for market open and close
    market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = current_time.replace(hour=16, minute=0, second=0, microsecond=0)
    
    # Check if current time is within market hours
    is_market_open = market_open <= current_time <= market_close
    return is_market_open

@app.route('/')
def home():
    is_market_open = asyncio.run(check_market_time())
    print("is_market_open: ", is_market_open)
    return jsonify({
        "message": "Welcome to the Flask API",
        "status": "success",
        "is_market_open": is_market_open
    })

def get_option_symbol(symbol, side, price):
    today = datetime.now()
    
    # Calculate days until next Friday
    current_weekday = today.weekday()
    if current_weekday == 5:
        days_until_friday = 6
    elif current_weekday == 6:
        days_until_friday = 5
    else:
        days_until_friday = 5 - current_weekday - 1
    
    expiration_date = today + timedelta(days=days_until_friday)
    
    # Format year as 2 digits
    year = str(expiration_date.year)[-2:]
    # Format month as 2 digits with leading zero
    month = f"{expiration_date.month:02d}"
    # Format day as 2 digits with leading zero
    day = f"{expiration_date.day:02d}"
    
    # Format price: take the integer part, pad with zeros to 5 digits, then add 000
    price_int = int(float(price))
    price_str = f"{price_int:05d}000"
    
    if side == "buy":
        return f"{symbol}{year}{month}{day}C{price_str}"
    elif side == "sell":
        return f"{symbol}{year}{month}{day}P{price_str}"
    else:
        return None

@app.route('/api/buyOrder', methods=['POST'])
def buy_order():
    data = request.get_json()
    symbol = data['symbol']
    side = data['side']
    strategyName = data['strategyName']
    price = data['price']

    api_key = os.getenv('API_KEY')
    api_secret = os.getenv('SECREAT_KEY')

    optionSymbol = get_option_symbol(symbol, side, price)
    print("optionSymbol: ", optionSymbol)

    db.orders.insert_one({
        "symbol": symbol,
        "side": side,
        "strategyName": strategyName,
        "price": price,
        "optionSymbol": optionSymbol,
    })

    payload = {
        "type": "market",
        "time_in_force": "day",
        "symbol": optionSymbol,
        "qty": "2",
        "side": side
    }
    headers = {
    "accept": "application/json",
    "content-type": "application/json",
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }
    url = "https://paper-api.alpaca.markets/v2/orders"
    response = requests.post(url, json=payload, headers=headers)
    print("response: ", response.json())
    time.sleep(2)

    return jsonify({
        "message": "Buy order received successfully",
        "received_data": data,
        "status": "success"
    })

@app.route('/api/sellOrder', methods=['POST'])
def sell_order():
    data = request.get_json()
    symbol = data['symbol']
    side = data['side']
    strategyName = data['strategyName']
    price = data['price']

    api_key = os.getenv('API_KEY')
    api_secret = os.getenv('SECREAT_KEY')

    url = "https://paper-api.alpaca.markets/v2/positions"
    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }
    response = requests.delete(url, headers=headers)
    print("response: ", response.json())

    return jsonify({
        "message": "Sell order received successfully",
        "received_data": data,
        "status": "success"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)