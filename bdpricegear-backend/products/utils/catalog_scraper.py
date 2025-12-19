import asyncio
import logging
import re
import uuid
import urllib.parse
import time

from bs4 import BeautifulSoup
import requests
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("catalog_scraper")

def normalize_price(text):
    """Extract and clean price values"""
    match = re.findall(r"[\d\.,]+", str(text))
    if not match:
        return "Out of Stock"
    
    num = match[0].replace(',', '')
    try:
        return float(num)
    except:
        return "Out Of Stock"


# StarTech - Scrape all pages
def scrape_startech_catalog(category):
    """Scrape all pages from StarTech for a category"""
    try:
        base_url = "https://www.startech.com.bd/product/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        products = []
        logo_url = "https://www.startech.com.bd/catalog/view/theme/starship/images/logo.png"
        page = 1
        max_pages = 50
        consecutive_empty = 0
        
        while page <= max_pages:
            url = f"{base_url}?search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"StarTech: Scraping page {page} for {category}")
            
            response = requests.get(url, headers=headers, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            
            items = soup.select(".p-item")
            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info(f"StarTech: No more products found, stopping at page {page}")
                    break
                page += 1
                continue
            
            consecutive_empty = 0
            
            for item in items:
                name = item.select_one(".p-item-name")
                price = item.select_one(".price-new") or item.select_one(".p-item-price")
                img = item.select_one(".p-item-img img")
                link = item.select_one(".p-item-img a")
                
                if name and link:
                    products.append({
                        "id": str(uuid.uuid4()),
                        "name": name.text.strip(),
                        "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                        "img": img["src"] if img else "",
                        "link": link["href"] if link else ""
                    })
            
            page += 1
            time.sleep(0.3)
        
        logger.info(f"StarTech: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"StarTech catalog error: {e}")
        return {"products": [], "logo": ""}


# SkyLand - Scrape all pages
def scrape_skyland_catalog(category):
    """Scrape all pages from SkyLand for a category"""
    try:
        base_url = "https://www.skyland.com.bd/"
        products = []
        page = 1
        max_pages = 50
        consecutive_empty = 0
        
        logo = None
        logo_url = "https://www.skyland.com.bd/image/catalog/logo.png"
        
        while page <= max_pages:
            url = f"{base_url}index.php?route=product/search&search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"SkyLand: Scraping page {page} for {category}")
            
            response = requests.get(url, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            
            if page == 1 and not logo:
                logo_elem = soup.select_one("#logo img")
                if logo_elem and logo_elem.has_attr("src"):
                    logo_url = logo_elem["src"]
                    if not logo_url.startswith(('http://', 'https://')):
                        logo_url = urllib.parse.urljoin(base_url, logo_url)
            
            items = soup.select(".product-layout")
            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info(f"SkyLand: No more products found, stopping at page {page}")
                    break
                page += 1
                continue
            
            consecutive_empty = 0
            
            for item in items:
                name = item.select_one(".name")
                price = item.select_one(".price-new")
                img = item.select_one(".image img") or item.select_one(".product-img img") or item.select_one("img")
                link = item.select_one(".product-img") or item.select_one(".name a")
                
                img_url = ""
                if img and img.has_attr("src"):
                    img_url = img["src"]
                    if not img_url.startswith(('http://', 'https://')):
                        img_url = urllib.parse.urljoin(base_url, img_url)
                elif img and img.has_attr("data-src"):
                    img_url = img["data-src"]
                    if not img_url.startswith(('http://', 'https://')):
                        img_url = urllib.parse.urljoin(base_url, img_url)
                
                link_url = ""
                if link and link.has_attr("href"):
                    link_url = link["href"]
                    if not link_url.startswith(('http://', 'https://')):
                        link_url = urllib.parse.urljoin(base_url, link_url)
                
                if name and link_url:
                    products.append({
                        "id": str(uuid.uuid4()),
                        "name": name.text.strip(),
                        "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                        "img": img_url,
                        "link": link_url
                    })
            
            page += 1
            time.sleep(0.3)
        
        logger.info(f"SkyLand: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"SkyLand catalog error: {e}")
        return {"products": [], "logo": ""}


# PcHouse - Scrape all pages
def scrape_pchouse_catalog(category):
    """Scrape all pages from PcHouse for a category"""
    try:
        base_url = "https://www.pchouse.com.bd/product/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        products = []
        logo_url = "https://www.pchouse.com.bd/image/catalog/unnamed.png"
        page = 1
        max_pages = 50
        consecutive_empty = 0
        
        while page <= max_pages:
            url = f"{base_url}?search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"PcHouse: Scraping page {page} for {category}")
            
            response = requests.get(url, headers=headers, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            
            items = soup.select(".single-product-item")
            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info(f"PcHouse: No more products found, stopping at page {page}")
                    break
                page += 1
                continue
            
            consecutive_empty = 0
            
            for item in items:
                name_elem = item.select_one("h4 a")
                price_elem = item.select_one(".special-price") or item.select_one(".regular-price")
                img_elem = item.select_one("img")
                link_elem = item.select_one("h4 a")
                
                if name_elem and link_elem:
                    products.append({
                        "id": str(uuid.uuid4()),
                        "name": name_elem.text.strip(),
                        "price": normalize_price(price_elem.text.strip()) if price_elem else "Out Of Stock",
                        "img": img_elem.get("src", "") if img_elem else "",
                        "link": link_elem.get("href", "") if link_elem else ""
                    })
            
            page += 1
            time.sleep(0.3)
        
        logger.info(f"PcHouse: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"PcHouse catalog error: {e}")
        return {"products": [], "logo": ""}


# UltraTech - Scrape all pages
def scrape_ultratech_catalog(category):
    """Scrape all pages from UltraTech for a category"""
    try:
        base_url = "https://www.ultratech.com.bd/index.php"
        products = []
        logo_url = "https://www.ultratech.com.bd/image/catalog/logo.png"
        page = 1
        max_pages = 50
        consecutive_empty = 0
        
        while page <= max_pages:
            url = f"{base_url}?route=product/search&search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"UltraTech: Scraping page {page} for {category}")
            
            response = requests.get(url, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            
            items = soup.select(".product-layout")
            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info(f"UltraTech: No more products found, stopping at page {page}")
                    break
                page += 1
                continue
            
            consecutive_empty = 0
            
            for item in items:
                name = item.select_one(".name")
                price = item.select_one(".price-new")
                img = item.select_one(".product-img img")
                link = item.select_one(".product-img")
                
                if name and link:
                    products.append({
                        "id": str(uuid.uuid4()),
                        "name": name.text.strip(),
                        "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                        "img": img["src"] if img else "",
                        "link": link["href"] if link else ""
                    })
            
            page += 1
            time.sleep(0.3)
        
        logger.info(f"UltraTech: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"UltraTech catalog error: {e}")
        return {"products": [], "logo": ""}


# PotakaIT - Scrape all pages
def scrape_potakait_catalog(category):
    """Scrape all pages from PotakaIT for a category"""
    try:
        base_url = "https://www.potakait.com/index.php"
        products = []
        logo_url = "https://www.potakait.com/image/catalog/logo.png"
        page = 1
        max_pages = 50
        consecutive_empty = 0
        
        while page <= max_pages:
            url = f"{base_url}?route=product/search&search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"PotakaIT: Scraping page {page} for {category}")
            
            response = requests.get(url, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            
            items = soup.select(".product-item")
            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info(f"PotakaIT: No more products found, stopping at page {page}")
                    break
                page += 1
                continue
            
            consecutive_empty = 0
            
            for item in items:
                name = item.select_one(".title a")
                price = item.select_one(".price:not(.old)")
                img = item.select_one(".product-img img")
                link = item.select_one(".title a")
                
                if name and link:
                    products.append({
                        "id": str(uuid.uuid4()),
                        "name": name.text.strip(),
                        "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                        "img": img["src"] if img else "",
                        "link": link["href"] if link else ""
                    })
            
            page += 1
            time.sleep(0.3)
        
        logger.info(f"PotakaIT: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"PotakaIT catalog error: {e}")
        return {"products": [], "logo": ""}


# Ryans - Scrape all pages with Playwright
async def scrape_ryans_catalog(category, context):
    """Scrape all pages from Ryans for a category"""
    results = {"products": [], "logo": "https://www.ryans.com/wp-content/themes/ryans/img/logo.png"}
    page_obj = None
    
    try:
        base_url = f"https://www.ryans.com/search?q={urllib.parse.quote(category)}"
        page_obj = await context.new_page()
        
        await page_obj.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page_num = 1
        max_pages = 50
        consecutive_empty = 0
        
        while page_num <= max_pages:
            url = f"{base_url}&page={page_num}"
            logger.info(f"Ryans: Scraping page {page_num} for {category}")
            
            try:
                await page_obj.goto(url, timeout=40000, wait_until="load")
                await asyncio.sleep(1.5)
                await page_obj.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                await asyncio.sleep(0.5)
                
                soup = BeautifulSoup(await page_obj.content(), "html.parser")
                items = soup.select(".category-single-product")
                
                if not items:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        logger.info(f"Ryans: No more products found, stopping at page {page_num}")
                        break
                    page_num += 1
                    await asyncio.sleep(1)
                    continue
                
                consecutive_empty = 0
                
                for item in items:
                    name_elem = item.select_one(".card-body .card-text a")
                    price_elem = item.select_one(".pr-text")
                    link_elem = item.select_one(".image-box a")
                    img_elem = item.select_one(".image-box img")
                    
                    if name_elem:
                        product_name = name_elem.get_text(strip=True)
                        product_link = urllib.parse.urljoin(url, link_elem["href"]) if link_elem and link_elem.has_attr("href") else ""
                        product_price = normalize_price(price_elem.get_text(strip=True)) if price_elem else "Out of Stock"
                        product_img = img_elem["src"] if img_elem and img_elem.has_attr("src") else ""
                        
                        if product_img and not product_img.startswith(('http://', 'https://')):
                            product_img = urllib.parse.urljoin(url, product_img)
                        
                        if product_link:
                            results["products"].append({
                                "id": str(uuid.uuid4()),
                                "name": product_name,
                                "price": product_price,
                                "link": product_link,
                                "img": product_img,
                                "in_stock": True
                            })
                
                page_num += 1
                await asyncio.sleep(0.5)
                
            except PlaywrightTimeout:
                logger.warning(f"Ryans: Timeout at page {page_num}")
                break
        
        logger.info(f"Ryans: Total scraped {len(results['products'])} products for {category}")
        return results
        
    except Exception as e:
        logger.error(f"Ryans catalog error: {e}")
        return results
    finally:
        if page_obj:
            await page_obj.close()


# Binary Logic - Scrape all pages with Playwright
async def scrape_binary_catalog(category, context):
    """Scrape all pages from Binary Logic for a category"""
    results = {"products": [], "logo": "https://www.binarylogic.com.bd/images/logo.png"}
    page_obj = None
    
    try:
        page_obj = await context.new_page()
        page_num = 1
        max_pages = 50
        consecutive_empty = 0
        
        while page_num <= max_pages:
            url = f"https://www.binarylogic.com.bd/search/{urllib.parse.quote(category)}?page={page_num}"
            logger.info(f"Binary: Scraping page {page_num} for {category}")
            
            try:
                await page_obj.goto(url, timeout=40000, wait_until="domcontentloaded")
                await page_obj.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                await asyncio.sleep(0.5)
                
                soup = BeautifulSoup(await page_obj.content(), "html.parser")
                items = soup.select(".single_product")
                
                if not items:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        logger.info(f"Binary: No more products found, stopping at page {page_num}")
                        break
                    page_num += 1
                    await asyncio.sleep(0.5)
                    continue
                
                consecutive_empty = 0
                
                for item in items:
                    name_elem = item.select_one(".p-item-name")
                    price_elem = item.select_one(".current_price")
                    img_elem = item.select_one(".p-item-img img")
                    link_elem = item.select_one(".p-item-img a")
                    
                    if name_elem and link_elem:
                        results["products"].append({
                            "id": str(uuid.uuid4()),
                            "name": name_elem.get_text(strip=True),
                            "price": normalize_price(price_elem.get_text(strip=True) if price_elem else "0"),
                            "link": urllib.parse.urljoin(url, link_elem["href"]) if link_elem else "",
                            "img": urllib.parse.urljoin(url, img_elem["src"]) if img_elem else "",
                            "in_stock": True
                        })
                
                page_num += 1
                await asyncio.sleep(0.5)
                
            except PlaywrightTimeout:
                logger.warning(f"Binary: Timeout at page {page_num}")
                break
        
        logger.info(f"Binary: Total scraped {len(results['products'])} products for {category}")
        return results
        
    except Exception as e:
        logger.error(f"Binary catalog error: {e}")
        return results
    finally:
        if page_obj:
            await page_obj.close()
