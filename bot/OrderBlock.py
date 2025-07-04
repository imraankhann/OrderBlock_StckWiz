from pickle import NONE
import time
import requests
import asyncio
import pytz
import json
import math
from datetime import datetime
from pytz import timezone
import numpy as np
import pandas as pd
import pytz
from telegram import Bot
import logging
import yfinance as yf

now = datetime.now()
format = "%d-%m-%Y %H:%M:%S %Z%z"
now_utc = datetime.now(timezone('UTC'))
now_asia = now_utc.astimezone(timezone('Asia/Kolkata'))
ocTime = now_asia.strftime(format)
fName = now_asia.strftime(format)
tdate = fName.split(" IST")
nowTime = tdate[0]
print(nowTime)
curWeekday = datetime.today().weekday()
dtTime = fName.split(" IST")
dt = dtTime[0].split(" ")
dtWithOutTime = dt[0].split(" ")
dateWithOutTime = dtWithOutTime[0]
isHolidayNxtDay = ""
reqTime = ocTime[11:16]
reqMin = ocTime[14:16]
intTime = int(reqTime[0:2])
intMin = int(reqMin)
print("Int min : ", intMin)
counter = 0
logFileName = dateWithOutTime+"-"+"MagicLevel.log"

TELEGRAM_BOT_TOKEN = "5817461626:AAHp1IIIMkQGWFTqIuu84lYOoxlO8KS7CZo"
TELEGRAM_CHAT_ID = "@swingTradeScreenedStocks"

#Fetch Updated Index values from csv file
nsedf_minus_supply_level = pd.read_csv('./levels_for_orderblock.csv',usecols=['minusSupplyLevel'],nrows=1)
nsedf_plus_supply_level = pd.read_csv('./levels_for_orderblock.csv',usecols=['plusSupplyLevel'],nrows=1)
nsedf_minus_demand_level = pd.read_csv('./levels_for_orderblock.csv',usecols=['minusDemandLevel'],nrows=1)
nsedf_plus_demand_level = pd.read_csv('./levels_for_orderblock.csv',usecols=['plusDemandLevel'],nrows=1)
nse_ce_risky_levels = int(nsedf_minus_supply_level['minusSupplyLevel'].loc[nsedf_minus_supply_level.index[0]])
nse_ce_safe_levels = int(nsedf_plus_supply_level['plusSupplyLevel'].loc[nsedf_plus_supply_level.index[0]])
nse_pe_safe_levels = int(nsedf_minus_demand_level['minusDemandLevel'].loc[nsedf_minus_demand_level.index[0]])
nse_pe_risky_levels = int(nsedf_plus_demand_level['plusDemandLevel'].loc[nsedf_plus_demand_level.index[0]])

# Function to fetch Nifty data
def fetch_nifty_data():
    # Fetch Nifty data (use "period=3d" for buffer)
    nifty_data = yf.download('^NSEI', period='3d', interval='1d')
    return nifty_data

# Function to send Telegram notification
async def send_telegram_notification(message):
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

 #Notify Index values To Telegram Channel after 9:15AM
if intTime==9 and intMin in range(15,45):
    message = (f'===============================\n'
              f'Order Block detected at {nowTime} IST.\n'
              f'===============================\n'
              f'AI BOT STARTED SUCCESSFULLY..!\n'
              f'===============================\n'
              f'TODAY ORDER BLOCK LEVELS\n'
              f'===============================\n'
              f'NIFTY SUPPLY LOW LEVEL : {nse_ce_risky_levels}\n'
              f'===============================\n'
              f'NIFTY SUPPLY HIGH LEVEL : {nse_ce_safe_levels}\n'
              f'===============================\n'
              f'NIFTY DEMAND LOW LEVEL : {nse_pe_risky_levels}\n'
              f'===============================\n'
              f'NIFTY DEMAND HIGH LEVEL : {nse_pe_safe_levels}\n'
              f'===============================\n')
    
    asyncio.run(send_telegram_notification(message))  

else: 
    print("Time not between 9:15 AM - 9:30 AM to show the levels...!")

#Keep Running below code from 9AM to 3PM
if intTime >= 9 and intTime < 18:
#if intTime >= 18 and intTime < 54:
    while(intTime<18):
        c = datetime.now(tz=pytz.timezone('Asia/Kolkata'))
        runTime = c.strftime('%H:%M:%S')
        current_hour = int(c.strftime('%H'))
        current_minute = int(c.strftime('%M'))
        if current_hour>18:
            print(f"Exiting the script at {runTime}, as it's past 3 PM.")
            break;
        
        data = yf.download("^NSEI", period="1mo", interval="5m")

        def get_live_price(data):
            """Fetch the current live price of an index from the last row of data."""
            return float(data['Close'].iloc[-1])

        live_price = round(get_live_price(data),2)

        def get_nearest_strike_price(live_price, step):
            """Calculate the nearest strike price for a given index price."""
            return round(live_price / step) * step

        nearest_strike_nf = get_nearest_strike_price(live_price, 50)

        nse_ce_risky_range = nse_ce_risky_levels - 10
        nse_ce_safe_range = nse_ce_safe_levels + 10
        nse_pe_risky_range = nse_pe_risky_levels + 10
        nse_pe_safe_range = nse_pe_safe_levels - 10

        niftyLastPrice = int(live_price)
        print("NIFTY CMP : ",niftyLastPrice)
        print(f'==========================\n'
              f'Running task at:", {runTime}\n'
              f'NIFTY CMP : {niftyLastPrice}\n'
              f'NIFTY SUPPLY LOW LEVEL : {nse_ce_risky_range}\n'
              f'NIFTY SUPPLY HIGH LEVEL : {nse_ce_safe_range}\n'
              f'NIFTY DEMAND HIGH LEVEL : {nse_pe_risky_range}\n'
              f'NIFTY DEMAND LOW LEVEL : {nse_pe_safe_range}\n'
              f'==========================\n')

        print("Nearest Nifty Strike : ", nearest_strike_nf)
        print("Run Time : ", runTime)
        counter= counter+1
        print("Counter : ", counter)
        
        if nse_ce_risky_range <= niftyLastPrice <= nse_ce_safe_range:
            buy = 'PE'
            message=(f'==========================\n'
                     f'Time : {dt[0]+"-"+runTime}\n'
                     f'==========================\n'
                     f'AI-BOT FOR ORDER BLOCK LEVELS\n'
                     f'==========================\n'
                     f'NIFYT CMP : {niftyLastPrice}\n'
                     f'==========================\n'
                     f'NIFTY TRADING NEAR PE BD LEVEL:{nse_ce_risky_levels}\n'
                     f'==========================\n'
                     f'CHOOSE STRIKE : {nearest_strike_nf} {buy}\n'
                     f'==========================\n'
                     f'NOTE : ONLY FOR EDUCATIONAL PURPOSE.\n'
                     f'==========================\n'
                     f'BOT IS NOT SEBI REG..!\n'
                     f'==========================\n')
            asyncio.run(send_telegram_notification(message)) 

        if nse_pe_risky_range <= niftyLastPrice <= nse_pe_safe_range :
            buy = "CE"
            message=(f'==========================\n'
                    f'Time : {dt[0]+"-"+runTime}\n'
                    f'==========================\n'
                    f'AI-BOT FOR ORDER BLOCK LEVELS\n'
                    f'==========================\n'
                    f'NIFYT CMP : {niftyLastPrice}\n'
                    f'==========================\n'
                    f'NIFTY TRADING NEAR  CE BO LEVEL:{nse_pe_risky_levels}\n'
                    f'==========================\n'
                    f'CHOOSE STRIKE : {nearest_strike_nf} {buy}\n'
                    f'==========================\n'
                    f'NOTE : ONLY FOR EDUCATIONAL PURPOSE.\n'
                    f'==========================\n'
                    f'BOT IS NOT SEBI REG..!\n'
                    f'==========================\n')
            asyncio.run(send_telegram_notification(message))     

        time.sleep(180)




