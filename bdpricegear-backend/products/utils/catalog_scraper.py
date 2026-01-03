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

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    logger.warning("cloudscraper not installed. Ryans scraping may be limited. Install with: pip install cloudscraper")

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


def scrape_startech_catalog(category, max_pages=50):
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
        # max_pages is now passed as argument
        consecutive_empty = 0
        
        while page <= max_pages:
            url = f"{base_url}?search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"StarTech: Scraping page {page} for {category}")
            
            try:
                response = requests.get(url, headers=headers, timeout=60)  # Increased timeout
            except (requests.Timeout, requests.ConnectionError) as e:
                logger.warning(f"StarTech: Timeout on page {page}: {e}")
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                page += 1
                continue
                
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


def scrape_skyland_catalog(category, max_pages=50):
    """Scrape all pages from SkyLand for a category"""
    try:
        base_url = "https://www.skyland.com.bd/"
        products = []
        page = 1
        # max_pages is now passed as argument
        consecutive_empty = 0
        
        logo = None
        logo_url = "https://www.skyland.com.bd/image/cache/wp/gp/skyland-logo-1398x471.webp"
        
        while page <= max_pages:
            url = f"{base_url}index.php?route=product/search&search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"SkyLand: Scraping page {page} for {category}")
            
            try:
                response = requests.get(url, timeout=30, allow_redirects=True)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
            except requests.exceptions.Timeout:
                logger.warning(f"SkyLand: Timeout on page {page}, retrying once...")
                try:
                    response = requests.get(url, timeout=45)
                    soup = BeautifulSoup(response.text, "html.parser")
                except Exception as retry_err:
                    logger.error(f"SkyLand: Retry failed on page {page}: {retry_err}")
                    break
            except Exception as e:
                logger.error(f"SkyLand: Error on page {page}: {e}")
                break
            
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


def scrape_pchouse_catalog(category, max_pages=50):
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
        # max_pages is now passed as argument
        consecutive_empty = 0
        
        while page <= max_pages:
            url = f"{base_url}?search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"PcHouse: Scraping page {page} for {category}")
            
            try:
                response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
            except requests.exceptions.Timeout:
                logger.warning(f"PcHouse: Timeout on page {page}, retrying once...")
                try:
                    response = requests.get(url, headers=headers, timeout=45)
                    soup = BeautifulSoup(response.text, "html.parser")
                except Exception as retry_err:
                    logger.error(f"PcHouse: Retry failed on page {page}: {retry_err}")
                    break
            except Exception as e:
                logger.error(f"PcHouse: Error on page {page}: {e}")
                break
            
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


def scrape_ultratech_catalog(category, max_pages=50):
    """Scrape all pages from UltraTech for a category"""
    try:
        base_url = "https://www.ultratech.com.bd/index.php"
        products = []
        logo_url = "https://www.ultratech.com.bd/image/cache/catalog/website/logo/ultra-technology-header-logo-500x500.png.webp"
        page = 1
        consecutive_empty = 0
        consecutive_errors = 0
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        while page <= max_pages:
            url = f"{base_url}?route=product/search&search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"UltraTech: Scraping page {page} for {category}")
            
            # Retry logic for timeout issues
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, headers=headers, timeout=60)  # Increased to 60s
                    break  # Success, exit retry loop
                except (requests.Timeout, requests.ConnectionError) as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"UltraTech: Timeout on page {page}, attempt {attempt + 1}/{max_retries}, retrying...")
                        time.sleep(2)
                        continue
                    else:
                        logger.error(f"UltraTech: Failed after {max_retries} attempts on page {page}: {e}")
                        consecutive_errors += 1
                        if consecutive_errors >= 3:
                            logger.warning(f"UltraTech: Too many errors, stopping at page {page}")
                            return {"products": products, "logo": logo_url}
                        page += 1
                        continue
            else:
                # Failed all retries
                page += 1
                continue
            
            consecutive_errors = 0  # Reset on success
            
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
            time.sleep(1)  # Increased delay to avoid overwhelming slow server
        
        logger.info(f"UltraTech: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"UltraTech catalog error: {e}")
        return {"products": products if 'products' in locals() else [], "logo": logo_url if 'logo_url' in locals() else ""}


def scrape_potakait_catalog(category, max_pages=50):
    """Scrape all pages from PotakaIT for a category"""
    try:
        base_url = "https://www.potakait.com/index.php"
        products = []
        logo_url = "https://www.potakait.com/image/catalog/logo.png"
        page = 1
        # max_pages is now passed as argument
        consecutive_empty = 0
        
        while page <= max_pages:
            url = f"{base_url}?route=product/search&search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"PotakaIT: Scraping page {page} for {category}")
            
            try:
                response = requests.get(url, timeout=60)  # Increased timeout
            except (requests.Timeout, requests.ConnectionError) as e:
                logger.warning(f"PotakaIT: Timeout on page {page}: {e}")
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                page += 1
                continue
            
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


def scrape_ryans_catalog(category, max_pages=50):
    """Scrape all pages from Ryans for a category using cloudscraper"""
    
    if not CLOUDSCRAPER_AVAILABLE:
        logger.error("Ryans: cloudscraper not available. Install with: pip install cloudscraper")
        return {"products": [], "logo": "https://www.ryans.com/wp-content/themes/ryans/img/logo.png"}
    
    results = {
        "products": [],
        "logo": "https://www.ryans.com/assets/images/ryans-logo.svg"
    }
    
    # Enhanced headers to bypass cloud server detection
    custom_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,bn;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.google.com/',
    }
    
    try:
        # Create scraper instance with enhanced settings
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True,
                'mobile': False
            },
            delay=10,
            interpreter='nodejs'  # Better JS challenge solving
        )
        scraper.headers.update(custom_headers)
        
        base_url = f"https://www.ryans.com/search?q={urllib.parse.quote(category)}"
        page_num = 1
        # max_pages is now passed as argument
        consecutive_empty = 0
        
        while page_num <= max_pages:
            url = f"{base_url}&limit=30&page={page_num}"
            logger.info(f"Ryans: Scraping page {page_num} for {category}")
            
            try:
                # cloudscraper automatically handles Cloudflare challenges
                response = None
                for retry in range(3):
                    try:
                        response = scraper.get(url, timeout=45)
                        if response.status_code == 200:
                            break
                        elif response.status_code == 403:
                            logger.warning(f"Ryans: Page {page_num} returned 403 (attempt {retry+1}/3), waiting...")
                            time.sleep(15 + retry * 10)  # Increasing delay
                            # Recreate scraper with fresh session
                            scraper = cloudscraper.create_scraper(
                                browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
                                delay=10, interpreter='nodejs'
                            )
                            scraper.headers.update(custom_headers)
                        else:
                            break
                    except Exception as retry_err:
                        logger.warning(f"Ryans: Retry {retry+1} error: {retry_err}")
                        time.sleep(5)
                
                if not response or response.status_code != 200:
                    logger.error(f"Ryans: Page {page_num} failed with status {response.status_code if response else 'None'}")
                    break
                
                # Parse HTML
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Check for Cloudflare challenge page
                if "just a moment" in response.text.lower() or "checking your browser" in response.text.lower():
                    logger.warning(f"Ryans: Cloudflare challenge on page {page_num}, stopping")
                    break
                
                items = soup.select(".category-single-product")
                
                if not items:
                    consecutive_empty += 1
                    logger.info(f"Ryans: No products on page {page_num}, consecutive empty: {consecutive_empty}")
                    if consecutive_empty >= 2:
                        logger.info(f"Ryans: Stopping at page {page_num}")
                        break
                    page_num += 1
                    time.sleep(2)
                    continue
                
                consecutive_empty = 0
                logger.info(f"Ryans: Found {len(items)} products on page {page_num}")
                
                # Extract product data
                for item in items:
                    name_elem = item.select_one(".card-body .card-text a")
                    price_elem = item.select_one(".pr-text")
                    link_elem = item.select_one(".image-box a")
                    img_elem = item.select_one(".image-box img")
                    
                    if name_elem:
                        product_name = name_elem.get_text(strip=True)
                        product_link = urllib.parse.urljoin(url, link_elem["href"]) if link_elem and link_elem.has_attr("href") else "#"
                        product_price = normalize_price(price_elem.get_text(strip=True)) if price_elem else "Out of Stock"
                        product_img = img_elem["src"] if img_elem and img_elem.has_attr("src") else ""
                        
                        if product_img and not product_img.startswith(('http://', 'https://')):
                            product_img = urllib.parse.urljoin(url, product_img)
                        
                        results["products"].append({
                            "id": str(uuid.uuid4()),
                            "name": product_name,
                            "price": product_price,
                            "link": product_link,
                            "img": product_img,
                            "in_stock": True
                        })
                
                page_num += 1
                # Delay between pages to avoid rate limiting
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"Ryans: Error on page {page_num}: {e}")
                break
        
        logger.info(f"Ryans: Total scraped {len(results['products'])} products for {category}")
        return results
        
    except Exception as e:
        logger.error(f"Ryans catalog error: {e}")
        return results


def scrape_binary_catalog(category, max_pages=50):
    """Scrape all pages from Binary Logic for a category using cloudscraper"""
    
    if not CLOUDSCRAPER_AVAILABLE:
        logger.error("Binary: cloudscraper not available. Install with: pip install cloudscraper")
        return {"products": [], "logo": "https://www.binarylogic.com.bd/images/brand_image/binary-logic.webp"}
    
    results = {
        "products": [],
        "logo": "https://www.binarylogic.com.bd/images/brand_image/binary-logic.webp"
    }
    
    # Enhanced headers to bypass cloud server detection
    custom_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,bn;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.google.com/',
    }
    
    try:
        # Create scraper instance with enhanced settings
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True,
                'mobile': False
            },
            delay=5,
            interpreter='nodejs'  # Better JS challenge solving
        )
        scraper.headers.update(custom_headers)
        
        page_num = 1
        # max_pages is now passed as argument
        consecutive_empty = 0
        
        while page_num <= max_pages:
            # Binary Logic uses /search/{query} format
            if page_num == 1:
                url = f"https://www.binarylogic.com.bd/search/{urllib.parse.quote(category)}"
            else:
                url = f"https://www.binarylogic.com.bd/search/{urllib.parse.quote(category)}?page={page_num}"
            
            logger.info(f"Binary: Scraping page {page_num} for {category}")
            
            try:
                # Retry logic for 403 errors
                response = None
                for retry in range(3):
                    try:
                        response = scraper.get(url, timeout=45)
                        if response.status_code == 200:
                            break
                        elif response.status_code == 403:
                            logger.warning(f"Binary: Page {page_num} returned 403 (attempt {retry+1}/3), waiting...")
                            time.sleep(10 + retry * 5)
                            # Recreate scraper with fresh session
                            scraper = cloudscraper.create_scraper(
                                browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
                                delay=5, interpreter='nodejs'
                            )
                            scraper.headers.update(custom_headers)
                        else:
                            break
                    except Exception as retry_err:
                        logger.warning(f"Binary: Retry {retry+1} error: {retry_err}")
                        time.sleep(5)
                
                if not response or response.status_code != 200:
                    logger.error(f"Binary: Page {page_num} failed with status {response.status_code if response else 'None'}")
                    break
                
                soup = BeautifulSoup(response.text, "html.parser")
                items = soup.select(".single_product")
                
                if not items:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        logger.info(f"Binary: No more products found, stopping at page {page_num}")
                        break
                    page_num += 1
                    time.sleep(1)
                    continue
                
                consecutive_empty = 0
                logger.info(f"Binary: Found {len(items)} products on page {page_num}")
                
                for item in items:
                    name_elem = item.select_one(".p-item-name")
                    price_elem = item.select_one(".current_price")
                    img_elem = item.select_one(".p-item-img img")
                    link_elem = item.select_one(".p-item-img a")
                    
                    if name_elem:
                        results["products"].append({
                            "id": str(uuid.uuid4()),
                            "name": name_elem.get_text(strip=True),
                            "price": normalize_price(price_elem.get_text(strip=True) if price_elem else "0"),
                            "link": urllib.parse.urljoin(url, link_elem["href"]) if link_elem else "#",
                            "img": urllib.parse.urljoin(url, img_elem["src"]) if img_elem else "",
                            "in_stock": True
                        })
                
                page_num += 1
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Binary: Error on page {page_num}: {e}")
                break
        
        logger.info(f"Binary: Total scraped {len(results['products'])} products for {category}")
        return results
        
    except Exception as e:
        logger.error(f"Binary catalog error: {e}")
        return results
