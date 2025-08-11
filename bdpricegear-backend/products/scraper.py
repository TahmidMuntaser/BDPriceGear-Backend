import asyncio
import logging
import re
import uuid
import urllib.parse

from bs4 import BeautifulSoup
import requests

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper")

# extracts and cleans price values
def normalize_price(text):
    match = re.findall(r"[\d\.,]+", str(text))
    if not match:
        return "Out of Stock"
    
    num = match[0].replace(',', '')
    try:
        return float(num)
    except:
        return "Out Of Stock"
    
    
#dynamic scrapper
async def scrape_startech(product):
    return {"products": [], "logo": ""}

async def scrape_ryans(product):
    return {"products": [], "logo": ""}


#static scrapper

def scrape_techland(product):
    return {"products": [], "logo": ""}

def scrape_skyland(product):
    return {"products": [], "logo": ""}

def scrape_pchouse(product):
    return {"products": [], "logo": ""}

def scrape_ultratech(product):
    return {"products": [], "logo": ""}

def scrape_binary(product):
    return {"products": [], "logo": ""}

def scrape_potakait(product):
    return {"products": [], "logo": ""}
