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

# ryans 
async def scrape_ryans(product, context):
    results = {"products": [], "logo": "https://www.ryans.com/wp-content/themes/ryans/img/logo.png"}
    try:
        url = f"https://www.ryans.com/search?q={urllib.parse.quote(product)}"
        page = await context.new_page()
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        soup = BeautifulSoup(await page.content(), "html.parser")
        for item in soup.select(".category-single-product"):
            name_elem = item.select_one(".card-text a")
            price_elem = item.select_one(".pr-text")
            link_elem = item.select_one(".image-box a")
            img_elem = item.select_one(".image-box img")

            results["products"].append({
                "id": str(uuid.uuid4()),
                "name": name_elem.get_text(strip=True) if name_elem else "Name not found",
                "price": normalize_price(price_elem.get_text(strip=True) if price_elem else "0"),
                "link": urllib.parse.urljoin(url, link_elem["href"]) if link_elem else "#",
                "img": img_elem["src"] if img_elem else "",
                "in_stock": True
            })

        await page.close()
        return results
    except Exception as e:
        logger.error(f"Ryans error: {e}")
        return results


#static scrapper

# startech 
def scrape_startech(product):
    try:
        url = f"https://www.startech.com.bd/product/search?search={urllib.parse.quote(product)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        products = []
        logo_url = "https://www.startech.com.bd/catalog/view/theme/starship/images/logo.png"

        for item in soup.select(".p-item"):
            name = item.select_one(".p-item-name")
            price = item.select_one(".price-new") or item.select_one(".p-item-price")
            img = item.select_one(".p-item-img img")
            link = item.select_one(".p-item-img a")

            products.append({
                "id": str(uuid.uuid4()),
                "name": name.text.strip() if name else "Name not found",
                "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                "img": img["src"] if img else "Image not found",
                "link": link["href"] if link else "Link not found"
            })

        return {"products": products, "logo": logo_url}

    except Exception as e:
        logger.error(f"StarTech error: {e}")
        return {"products": [], "logo": "logo not found"}


# techland 
def scrape_techland(product):
    try:
        url = f"https://www.techlandbd.com/index.php?route=product/search&search={urllib.parse.quote(product)}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        products = []
        
        logo = soup.select_one("a.navbar-brand img")
        logo_url = logo["src"] if logo and "src" in logo.attrs else "https://via.placeholder.com/150"
        
        product_items = soup.select('div.flex.overflow-hidden.transition-all')
        
        if not product_items:
            logger.warning(f"No products found on Techland for: {product}")
            return {"products": [], "logo": logo_url}
        
        for item in product_items:
            try:
             
                name_elem = item.select_one('h3.text-xs a') or item.select_one('h3.text-sm a')
                price_container = item.select_one('.price-tag')
                img_elem = item.select_one('div.relative img')
                link_elem = name_elem  
                
                price_text = ""
                if price_container:

                    texts = [text.strip() for text in price_container.find_all(text=True, recursive=True) if text.strip()]
                    if texts:
                        
                        price_text = texts[0]
                
                if not name_elem or not price_text:
                    continue
                    
                products.append({
                    "id": str(uuid.uuid4()),
                    "name": name_elem.text.strip(),
                    "price": normalize_price(price_text),
                    "img": img_elem.get("src", "") if img_elem else "",
                    "link": link_elem.get("href", "")
                })
                
            except Exception as e:
                logger.warning(f"Techland product parse error: {e}")
                continue
                
        return {"products": products, "logo": logo_url}
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Techland network error: {e}")
    except Exception as e:
        logger.error(f"Techland general error: {e}", exc_info=True)
        
    return {"products": [], "logo": "https://via.placeholder.com/150"}
    
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
from urllib.parse import urljoin

def scrape_binary(product):
    try:
        url = f"https://www.binarylogic.com.bd/search/{urllib.parse.quote(product)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.binarylogic.com.bd/",
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
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
                "img": urljoin("https://www.binarylogic.com.bd", img["src"]) if img else "Image not found",
                "link": urljoin("https://www.binarylogic.com.bd", link["href"]) if link else "Link not found"
            })

        return {"products": products, "logo": logo}

    except Exception as e:
        logger.error(f"Binary error: {e}", exc_info=True)
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