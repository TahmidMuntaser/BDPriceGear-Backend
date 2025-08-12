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

# techland 
def scrape_techland(product):
    try:
        url = f"https://www.techlandbd.com/index.php?route=product/search&search={urllib.parse.quote(product)}"
        response = requests.get(url, timeout = 15)
        soap = BeautifulSoup(response.text, "html.parser")
        
        products = []
        
        logo = soap.select_one("#logo img")
        if logo:
            logo_url = logo["src"]
        else:
            logo_url = "logo not found"
            
        for item in soap.select(".product-layout"):
            name = item.select_one(".name")
            price = item.select_one(".price-new")
            img = item.select_one(".image img")
            link = item.select_one(".product-img")
            
            products.append({
                    "id": str(uuid.uuid4()),
                    "name": name.text.strip() if name else "Name not found",
                    "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                    "img": img["src"] if img else "Image not found",
                    "link": link["href"] if link else "Link not found"
            })
            
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        
        logger.error(f"TechLand error: {e}")
        return {"products": [], "logo": "logo not found"}
    
    
# skyland     
def scrape_skyland(product):
    try:
        url = f"https://www.skyland.com.bd/index.php?route=product/search&search={urllib.parse.quote(product)}"
        response = requests.get(url, timeout = 15)
        soap = BeautifulSoup(response.text, "html.parser")
        
        products = []
        
        logo = soap.select_one("#logo img")
        if logo:
            logo_url = logo["src"]
        else:
            logo_url = "logo not found"
            
        for item in soap.select(".product-layout"):
            name = item.select_one(".name")
            price = item.select_one(".price-new")
            img = item.select_one(".product-img img")
            link = item.select_one(".product-img")
            
            products.append({
                    "id": str(uuid.uuid4()),
                    "name": name.text.strip() if name else "Name not found",
                    "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                    "img": img["src"] if img else "Image not found",
                    "link": link["href"] if link else "Link not found"
            })
            
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        
        logger.error(f"TechLand error: {e}")
        return {"products": [], "logo": "logo not found"}    
    
    



def scrape_pchouse(product):
    return {"products": [], "logo": ""}

def scrape_ultratech(product):
    return {"products": [], "logo": ""}

def scrape_binary(product):
    return {"products": [], "logo": ""}

def scrape_potakait(product):
    return {"products": [], "logo": ""}
