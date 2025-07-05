import os
import time
import asyncio
import pytz
import pandas as pd
from datetime import datetime
from telegram import Bot
from nsetools import Nse
import yfinance as yf
from nsepy import get_history
from datetime import timedelta, date

# =================== CONFIG ===================
TELEGRAM_BOT_TOKEN = "your_bot_token_here"
TELEGRAM_CHAT_ID = "@your_chat_id_or_channel"
TIMEZONE = 'Asia/Kolkata'
SLEEP_INTERVAL = 180  # in seconds
LOG_DIR = './signal_logs'
os.makedirs(LOG_DIR, exist_ok=True)

nse = Nse()
tz = pytz.timezone(TIMEZONE)
now = datetime.now(tz)
log_filename = f"{LOG_DIR}/signals_{now.strftime('%Y-%m-%d_%H-%M-%S')}.csv"
sent_signals = set()
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# ================ UTILS =================

async def send_telegram(message):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

async def send_log_file():
    if os.path.exists(log_filename):
        with open(log_filename, 'rb') as f:
            await bot.send_document(chat_id=TELEGRAM_CHAT_ID, document=f)
        os.remove(log_filename)

def get_nifty_spot():
    """Fetch NIFTY spot price from NSE. Fallback to yfinance."""
    try:
        quote = nse.get_index_quote("nifty 50")
        spot = float(quote['lastPrice'])
        print(f"✅ NSETools Price: {spot}")
        return spot
    except Exception as e:
        print(f"⚠️ NSETools failed: {e}")
        return get_nifty_fallback()

last_download_time = None
cached_yf_data = None

def get_nifty_fallback():
    global last_download_time, cached_yf_data
    try:
        now = datetime.now()
        if not last_download_time or (now - last_download_time).seconds > 900:
            cached_yf_data = yf.download("^NSEI", period="1d", interval="5m")
            last_download_time = now
        if cached_yf_data is not None and not cached_yf_data.empty:
            spot = float(cached_yf_data['Close'].iloc[-1])
            print(f"🔁 Fallback YF Price: {spot}")
            return spot
    except Exception as e:
        print("❌ YFinance fallback also failed:", e)
        return None

def get_nearest_strike(price):
    return round(price / 50) * 50

def get_previous_day_ohlc():
    today = date.today()

    # Try NSEPy first
    for i in range(1, 8):
        try_date = today - timedelta(days=i)
        if try_date.weekday() > 4:
            continue
        try:
            df = get_history(symbol="NIFTY", index=True, start=try_date, end=try_date)
            if not df.empty:
                print(f"✅ NSEPY OHLC for {try_date}")
                return {
                    'Open': df['Open'].iloc[0],
                    'High': df['High'].iloc[0],
                    'Low': df['Low'].iloc[0],
                    'Close': df['Close'].iloc[0],
                }
        except Exception as e:
            print(f"❌ NSEPY failed for {try_date}: {e}")

    print("⚠️ Falling back to Yahoo Finance...")
    # Fallback to Yahoo Finance
    try:
        df_yf = yf.download('^NSEI', period='5d', interval='1d')
        if len(df_yf) >= 2:
            prev = df_yf.iloc[-2]
            return {
                'Open': prev['Open'],
                'High': prev['High'],
                'Low': prev['Low'],
                'Close': prev['Close']
            }
        else:
            print("❌ Yahoo Finance also returned insufficient data.")
            return None
    except Exception as e:
        print(f"❌ yfinance fallback failed: {e}")
        return None


def is_valid_breakout(price, ohlc):
    return ohlc['Low'] < price < ohlc['High']

def load_levels():
    df = pd.read_csv('./levels_for_orderblock.csv')
    return {
        'ce_risky': int(df['minusSupplyLevel'].iloc[0]),
        'ce_safe': int(df['plusSupplyLevel'].iloc[0]),
        'pe_risky': int(df['plusDemandLevel'].iloc[0]),
        'pe_safe': int(df['minusDemandLevel'].iloc[0]),
    }

def log_signal(timestamp, price, strike, signal_type):
    df_log = pd.DataFrame([{
        "timestamp": timestamp,
        "nifty_price": price,
        "strike_price": strike,
        "signal": signal_type
    }])
    df_log.to_csv(log_filename, mode='a', header=not os.path.exists(log_filename), index=False)

# ================ MAIN LOOP =================

async def monitor_nifty():
    levels = load_levels()
    ce_range = range(levels['ce_risky'] - 10, levels['ce_safe'] + 10)
    pe_range = range(levels['pe_safe'] - 10, levels['pe_risky'] + 10)
    prev_ohlc = get_previous_day_ohlc()
    print("prev_ohlc : ", prev_ohlc)
    if prev_ohlc is None:
        print("❌ Couldn't fetch previous day OHLC. Exiting.")
        return

    print("⏳ Waiting for market open (9:15 AM IST)...")
    while True:
        now = datetime.now(tz)
        current_time = now.time()

        market_start = datetime.strptime("09:15:00", "%H:%M:%S").time()
        market_end = datetime.strptime("15:30:00", "%H:%M:%S").time()

        if current_time < market_start:
            print(f"🕒 {now.strftime('%H:%M:%S')} — Market not open yet.")
            await asyncio.sleep(60)
            continue

        if current_time > market_end:
            print("🔚 Market closed. Sending log file and exiting.")
            await send_log_file()
            break

        price = get_nifty_spot()
        if price is None:
            print("⚠️ Skipping due to missing price.")
            await asyncio.sleep(SLEEP_INTERVAL)
            continue

        strike = get_nearest_strike(price)
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S')

        if is_valid_breakout(price, prev_ohlc):
            if int(price) in ce_range and f"PE-{strike}" not in sent_signals:
                message = (
                    f"[{timestamp}] PE Signal 🚨\n"
                    f"NIFTY CMP: {price}\n"
                    f"BUY PE {strike}\n"
                    f"Block Range: {levels['ce_risky']} - {levels['ce_safe']}"
                )
                await send_telegram(message)
                log_signal(timestamp, price, strike, "PE")
                sent_signals.add(f"PE-{strike}")

            elif int(price) in pe_range and f"CE-{strike}" not in sent_signals:
                message = (
                    f"[{timestamp}] CE Signal 🚨\n"
                    f"NIFTY CMP: {price}\n"
                    f"BUY CE {strike}\n"
                    f"Block Range: {levels['pe_safe']} - {levels['pe_risky']}"
                )
                await send_telegram(message)
                log_signal(timestamp, price, strike, "CE")
                sent_signals.add(f"CE-{strike}")
        else:
            print(f"⏳ {timestamp}: CMP {price} not in valid range.")

        await asyncio.sleep(SLEEP_INTERVAL)

# ================ RUN =================

if __name__ == "__main__":
    print("🚀 NIFTY Order Block Bot Started...\n")
    asyncio.run(monitor_nifty())
