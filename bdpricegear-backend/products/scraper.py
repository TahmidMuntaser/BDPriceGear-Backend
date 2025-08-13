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

# startech 
async def scrape_startech(product):
    results ={"products": [], "logo": "https://www.startech.com.bd/images/logo.png"}
    
    try:
        url = f"https://www.startech.com.bd/product/search?search={urllib.parse.quote(product)}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=15000)
            
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            
            for item in soup.select(".p-item"):
                name = item.select_one(".p-item-name")
                price = item.select_one(".price-new") or item.select_one(".p-item-price")
                img = item.select_one(".p-item-img img")
                link = item.select_one(".p-item-img a")
                
                results["products"].append({
                    "id": str(uuid.uuid4()),
                    "name": name.text.strip() if name else "Name not found",
                    "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                    "img": img["src"] if img else "Image not found",
                    "link": link["href"] if link else "Link not found"
                })
                
            await browser.close()
            
        return results
        
    except Exception as e:
        logger.error(f"StarTech error: {e}")
        return results


# ryans 
async def scrape_ryans(product_name):
    results = {
        "products": [],
        "logo": "https://www.ryans.com/wp-content/themes/ryans/img/logo.png",
        "store": "Ryans"
    }

    try:
        encoded_product = urllib.parse.quote(product_name)
        url = f"https://www.ryans.com/search?q={encoded_product}"
        logger.info(f"Starting scraping Ryans for: {product_name}")

        async with async_playwright() as p:
            
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0"
            )
            
            page = await context.new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            
            # Wait for page body to load
            await page.wait_for_selector("body", timeout=15000)
            
            # Scroll to trigger lazy-loaded products
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            items = soup.select(".category-single-product")
            logger.info(f"Ryans: found {len(items)} items")

            for item in items:
                try:
                    name_elem = item.select_one(".card-text a")
                    price_elem = item.select_one(".pr-text")
                    link_elem = item.select_one(".image-box a")
                    img_elem = item.select_one(".image-box img")

                    raw_price = price_elem.get_text(strip=True) if price_elem else "0"

                    results["products"].append({
                        "id": str(uuid.uuid4()),
                        "name": name_elem.get_text(strip=True) if name_elem else "Name not found",
                        "price": normalize_price(raw_price),
                        "link": urllib.parse.urljoin(url, link_elem["href"]) if link_elem else "#",
                        "img": img_elem["src"] if img_elem else "",
                        "in_stock": True
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing Ryans product: {e}")

            await browser.close()

        return results

    except Exception as e:
        logger.error(f"Ryans scraping failed: {e}")
        return {"products": [], "logo": "https://www.ryans.com/wp-content/themes/ryans/img/logo.png", "error": str(e)}



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
        
        logger.error(f"skyland error: {e}")
        return {"products": [], "logo": "logo not found"}    
    
    

# pchouse 
def scrape_pchouse(product):
    try:
        url = f"https://www.pchouse.com.bd/index.php?route=product/search&search={urllib.parse.quote(product)}"
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
        
        logger.error(f"pchouse error: {e}")
        return {"products": [], "logo": "logo not found"}
    

# ultratech 
def scrape_ultratech(product):
    try:
        url = f"https://www.ultratech.com.bd/index.php?route=product/search&search={urllib.parse.quote(product)}"
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
        
        logger.error(f"UltraTech error: {e}")
        return {"products": [], "logo": "logo not found"}
    
    
# binary 
def scrape_binary(product):
    try:
        url = f"https://www.binarylogic.com.bd/search/{urllib.parse.quote(product)}"
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        products = []
        
        logo = "https://www.binarylogic.com.bd/images/logo.png"
        
        for item in soup.select(".single_product"):
            name = item.select_one(".p-item-name")
            price = item.select_one(".current_price")
            img = item.select_one(".p-item-img img")
            link = item.select_one(".p-item-img a")
            
            products.append({
                "id": str(uuid.uuid4()),
                "name": name.text.strip() if name else "Name not found",
                "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                "img": img["src"] if img else "Image not found",
                "link": link["href"] if link else "Link not found"
            })
            
        return {"products": products, "logo": logo}
    
    except Exception as e:
        
        logger.error(f"Binary error: {e}")
        return {"products": [], "logo": "logo not found"}
    
# potakaIT 
def scrape_potakait(product):
    try:
        url = f"https://www.potakait.com/index.php?route=product/search&search={urllib.parse.quote(product)}"
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        products = []
        
        logo = soup.select_one(".brand-logo img")
        if logo:
            logo_url = logo["src"]
        else:
            logo_url = "logo not found"
        
        for item in soup.select(".product-item"):
            name = item.select_one(".title a")
            price = item.select_one(".price:not(.old)")
            img = item.select_one(".product-img img")
            link = item.select_one(".title a")
            
            products.append({
                "id": str(uuid.uuid4()),
                "name": name.text.strip() if name else "Name not found",
                "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                "img": img["src"] if img else "Image not found",
                "link": link["href"] if link else "Link not found"
            })
            
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        
        logger.error(f"PotakaIT error: {e}")
        return {"products": [], "logo": "logo not found"}