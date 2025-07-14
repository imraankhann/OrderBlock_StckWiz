import os
import time
import asyncio
import pytz
import pandas as pd
from datetime import datetime
from telegram import Bot
from nsetools import Nse
import yfinance as yf

# =================== CONFIG ===================
TELEGRAM_BOT_TOKEN = "6377307246:AAEuJAlBiQgDQEa03yNmKQJmZbXyQ0WINOk"
TELEGRAM_CHAT_ID = "-996001230"
TIMEZONE = 'Asia/Kolkata'
SLEEP_INTERVAL = 30  # in seconds (5 minutes)
LOG_DIR = './signal_logs'
os.makedirs(LOG_DIR, exist_ok=True)

# ================ GLOBALS =================
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

last_download_time = None
cached_yf_data = None

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

def get_nifty_fallback():
    global last_download_time, cached_yf_data
    try:
        now = datetime.now(tz)
        if not last_download_time or (now - last_download_time).seconds > SLEEP_INTERVAL:
            cached_yf_data = yf.download("NSEI^", period="1d", interval="5m")
            last_download_time = now
        if cached_yf_data is not None and not cached_yf_data.empty:
            spot = round(float(cached_yf_data['Close'].iloc[-1].item()), 2)
            print(f"🔁 cur_time: {now.strftime('%H:%M:%S')} Fallback YF Price: {spot}")
            return spot
    except Exception as e:
        print("❌ YFinance fallback failed:", e)
    return None

def get_nearest_strike(price):
    return round(price / 50) * 50

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

# ================ MAIN =================

async def monitor_nifty():
    levels = load_levels()
    selling_range = range(levels['ce_risky'] - 10, levels['ce_safe'] + 10)
    buying_range = range(levels['pe_safe'] - 10, levels['pe_risky'] + 10)

    print("⏳ Waiting for market open (9:15 AM IST)...")
    while True:
        now = datetime.now(tz)
        current_time = now.time()

        market_start = datetime.strptime("09:15:00", "%H:%M:%S").time()
        market_end = datetime.strptime("18:45:00", "%H:%M:%S").time()

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
        timestamp = now.strftime('%d-%m-%Y %H:%M:%S')

        if int(price) in selling_range and f"PE-{strike}" not in sent_signals:
            message = (
                f"======================\n"
                f"[{timestamp}] PE Signal 🚨\n"
                f"NIFTY CMP: {price}\n"
                f"BUY PE {strike}\n"
                f"Block Range: {levels['ce_risky']} - {levels['ce_safe']}\n"
                f"NOTE: We are not SEBI Reg..! This is Intraday Trade.\n"
                f"Trade at your own risk..!\n"
                f"======================\n"
            )
            await send_telegram(message)
            log_signal(timestamp, price, strike, "PE")
            sent_signals.add(f"PE-{strike}")

        elif int(price) in buying_range and f"CE-{strike}" not in sent_signals:
            message = (
                f"======================\n"
                f"[{timestamp}] CE Signal 🚨\n"
                f"NIFTY CMP: {price}\n"
                f"BUY CE {strike}\n"
                f"Block Range: {levels['pe_safe']} - {levels['pe_risky']}\n"
                f"NOTE: We are not SEBI Reg..! This is Intraday Trade.\n"
                f"Trade at your own risk..!\n"
                f"======================\n"
            )
            await send_telegram(message)
            log_signal(timestamp, price, strike, "CE")
            sent_signals.add(f"CE-{strike}")
        else:
            print(f"⏳ {timestamp}: CMP {price} not in zone.")

        await asyncio.sleep(SLEEP_INTERVAL)

# ================ RUN =================

if __name__ == "__main__":
    print("🚀 NIFTY Order Block Bot Started...\n")
    asyncio.run(monitor_nifty())
