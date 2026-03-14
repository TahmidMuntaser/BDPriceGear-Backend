import asyncio
import logging
import re
import uuid
import urllib.parse
import time
import random

from bs4 import BeautifulSoup
import requests
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("catalog_scraper")

# Rotating user agents to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

def get_random_user_agent():
    # Return a random user agent to avoid detection
    return random.choice(USER_AGENTS)

def create_session():
    """Create a requests session with connection pooling and retry logic"""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=3,
        pool_block=False
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def smart_delay(min_delay=0.2, max_delay=0.5):
    """Random delay between requests to avoid rate limiting"""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)

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
        return "Out of Stock"


def normalize_product_url(url):
    """
    Normalize product URL by removing pagination and search query parameters.
    This prevents duplicate products from being created when the same product
    appears on different search result pages.
    
    Examples:
    - https://example.com/product?search=Keyboard&page=21 -> https://example.com/product
    - https://example.com/product?id=123&page=5 -> https://example.com/product?id=123
    """
    if not url or url in ['#', 'Link not found', '']:
        return url
    
    try:
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        # Remove pagination and search-related query parameters
        params_to_remove = ['page', 'search', 'q', 'keyword', 'sort', 'order', 'limit']
        filtered_params = {
            k: v for k, v in query_params.items() 
            if k.lower() not in params_to_remove
        }
        
        # Rebuild the URL without the removed parameters
        new_query = urllib.parse.urlencode(filtered_params, doseq=True) if filtered_params else ''
        normalized = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            ''  # Remove fragment
        ))
        
        return normalized
    except Exception:
        # If parsing fails, return the original URL
        return url


def scrape_startech_catalog(category, max_pages=50):
    """Scrape all pages from StarTech for a category"""
    session = create_session()
    try:
        base_url = "https://www.startech.com.bd/product/search"
        products = []
        logo_url = "https://www.startech.com.bd/catalog/view/theme/starship/images/logo.png"
        page = 1
        consecutive_empty = 0
        
        while page <= max_pages:
            url = f"{base_url}?search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"StarTech: Scraping page {page} for {category}")
            
            headers = {
                "User-Agent": get_random_user_agent(),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://www.startech.com.bd/"
            }
            
            retry_count = 0
            max_retries = 3
            response = None
            
            while retry_count < max_retries:
                try:
                    response = session.get(url, headers=headers, timeout=30)
                    if response.status_code == 200:
                        break
                    logger.warning(f"StarTech: Page {page} returned {response.status_code}, retry {retry_count+1}/{max_retries}")
                    smart_delay(2, 4)
                    retry_count += 1
                except (requests.Timeout, requests.ConnectionError) as e:
                    logger.warning(f"StarTech: Connection error on page {page}: {e}, retry {retry_count+1}/{max_retries}")
                    smart_delay(3, 6)
                    retry_count += 1
            
            if not response or response.status_code != 200:
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
                        "price": normalize_price(price.text.strip()) if price else "Out of Stock",
                        "img": (img.get("data-src") or img.get("src") or "") if img else "",
                        "link": link["href"] if link else ""
                    })
            
            page += 1
            smart_delay(0.2, 0.5)  # Small delay between pages
        
        logger.info(f"StarTech: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"StarTech catalog error: {e}", exc_info=True)
        return {"products": [], "logo": ""}
    finally:
        session.close()


def scrape_skyland_catalog(category, max_pages=50):
    """Scrape all pages from SkyLand for a category"""
    session = create_session()
    try:
        base_url = "https://www.skyland.com.bd/"
        products = []
        page = 1
        consecutive_empty = 0
        
        logo = None
        logo_url = "https://www.skyland.com.bd/image/cache/wp/gp/skyland-logo-1398x471.webp"
        
        while page <= max_pages:
            url = f"{base_url}index.php?route=product/search&search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"SkyLand: Scraping page {page} for {category}")
            
            headers = {
                "User-Agent": get_random_user_agent(),
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.skyland.com.bd/"
            }
            
            retry_count = 0
            max_retries = 3
            soup = None
            
            while retry_count < max_retries:
                try:
                    response = session.get(url, headers=headers, timeout=30, allow_redirects=True)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "html.parser")
                        break
                    logger.warning(f"SkyLand: Page {page} returned {response.status_code}, retry {retry_count+1}/{max_retries}")
                    smart_delay(2, 5)
                    retry_count += 1
                except (requests.exceptions.Timeout, requests.ConnectionError) as e:
                    logger.warning(f"SkyLand: Connection error on page {page}: {e}, retry {retry_count+1}/{max_retries}")
                    smart_delay(3, 6)
                    retry_count += 1
            
            if not soup:
                logger.error(f"SkyLand: Failed to fetch page {page} after {max_retries} retries")
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
                # Try multiple price selectors - SkyLand uses different classes
                price = item.select_one(".price-new") or item.select_one(".price-normal") or item.select_one(".price")
                img = item.select_one(".image img") or item.select_one(".product-img img") or item.select_one("img")
                link = item.select_one(".product-img") or item.select_one(".name a")
                
                img_url = ""
                if img:
                    img_url = img.get("data-src") or img.get("src") or ""
                    if img_url and not img_url.startswith(('http://', 'https://')):
                        img_url = urllib.parse.urljoin(base_url, img_url)
                
                link_url = ""
                if link and link.has_attr("href"):
                    link_url = link["href"]
                    if not link_url.startswith(('http://', 'https://')):
                        link_url = urllib.parse.urljoin(base_url, link_url)
                
                if name and link_url:
                    # Normalize URL to prevent duplicates from pagination
                    normalized_link = normalize_product_url(link_url)
                    products.append({
                        "id": str(uuid.uuid4()),
                        "name": name.text.strip(),
                        "price": normalize_price(price.text.strip()) if price else "Out of Stock",
                        "img": img_url,
                        "link": normalized_link
                    })
            
            page += 1
            smart_delay(0.2, 0.5)  # Small delay between pages
        
        # Remove duplicates based on normalized URL before returning
        seen_urls = set()
        unique_products = []
        for p in products:
            if p['link'] not in seen_urls:
                seen_urls.add(p['link'])
                unique_products.append(p)
        
        logger.info(f"SkyLand: Total scraped {len(unique_products)} unique products for {category} (from {len(products)} raw)")
        return {"products": unique_products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"SkyLand catalog error: {e}")
        return {"products": [], "logo": ""}
    finally:
        session.close()


def scrape_pchouse_catalog(category, max_pages=50):
    """Scrape all pages from PcHouse for a category"""
    session = create_session()
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
                response = session.get(url, headers=headers, timeout=30, allow_redirects=True)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
            except requests.exceptions.Timeout:
                logger.warning(f"PcHouse: Timeout on page {page}, retrying once...")
                try:
                    response = session.get(url, headers=headers, timeout=45)
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
                        "price": normalize_price(price_elem.text.strip()) if price_elem else "Out of Stock",
                        "img": (img_elem.get("data-src") or img_elem.get("src") or "") if img_elem else "",
                        "link": link_elem.get("href", "") if link_elem else ""
                    })
            
            page += 1
            smart_delay(0.2, 0.5)  # Small delay between pages
        
        logger.info(f"PcHouse: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"PcHouse catalog error: {e}")
        return {"products": [], "logo": ""}
    finally:
        session.close()


def scrape_ultratech_catalog(category, max_pages=50):
    """Scrape all pages from UltraTech for a category"""
    session = create_session()
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
                    response = session.get(url, headers=headers, timeout=60)  # Increased to 60s
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
                        "price": normalize_price(price.text.strip()) if price else "Out of Stock",
                        "img": (img.get("data-src") or img.get("src") or "") if img else "",
                        "link": link["href"] if link else ""
                    })

            page += 1
            smart_delay(0.2, 0.5)  # Small delay between pages

        logger.info(f"UltraTech: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"UltraTech catalog error: {e}")
        return {"products": products if 'products' in locals() else [], "logo": logo_url if 'logo_url' in locals() else ""}
    finally:
        session.close()


def scrape_potakait_catalog(category, max_pages=50):
    """Scrape all pages from PotakaIT for a category"""
    session = create_session()
    try:
        products = []
        logo_url = "https://potakait.com/image/catalog/logo.png"
        page = 1
        consecutive_empty = 0
        headers = {"User-Agent": get_random_user_agent()}

        while page <= max_pages:
            url = f"https://potakait.com/product/search?&search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"PotakaIT: Scraping page {page} for {category}")

            try:
                response = session.get(url, headers=headers, timeout=60)
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
                name_tag = item.select_one(".title a")
                price_tag = item.select_one(".price-info .price")
                img_tag = item.select_one(".product-img img")
                stock_tag = item.select_one(".add-to-cart")
                
                if not name_tag:
                    continue
                
                in_stock = True
                if stock_tag and "Out Of Stock" in stock_tag.get("class", []):
                    in_stock = False
                
                products.append({
                    "id": str(uuid.uuid4()),
                    "name": name_tag.text.strip(),
                    "price": normalize_price(price_tag.text.strip()) if price_tag else "Out of Stock",
                    "img": (img_tag.get("data-src") or img_tag.get("src") or "") if img_tag else "",
                    "link": name_tag["href"] if name_tag else "",
                    "in_stock": in_stock
                })

            page += 1
            smart_delay(0.2, 0.5)  # Small delay between pages

        logger.info(f"PotakaIT: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"PotakaIT catalog error: {e}", exc_info=True)
        return {"products": [], "logo": ""}
    finally:
        session.close()


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
                    logger.info(f"Ryans: Cloudflare blocking detected. Skipping remaining pages.")
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
                    name_elem = item.select_one(".product-title a")
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


def scrape_computervillage_catalog(category, max_pages=50):
    """Scrape all pages from Computer Village for a category"""
    session = create_session()
    try:
        products = []
        logo_url = "https://www.computervillage.com.bd/image/cache/catalog/logo/Computer-Village-Logo-358x90.png"
        page = 1
        consecutive_empty = 0
        headers = {"User-Agent": get_random_user_agent()}

        while page <= max_pages:
            url = f"https://www.computervillage.com.bd/index.php?route=product/search&search={urllib.parse.quote(category)}&page={page}"
            logger.info(f"ComputerVillage: Scraping page {page} for {category}")

            try:
                response = session.get(url, headers=headers, timeout=30)
                if response.status_code != 200:
                    logger.warning(f"ComputerVillage: Page {page} returned {response.status_code}")
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                    page += 1
                    continue
            except (requests.Timeout, requests.ConnectionError) as e:
                logger.warning(f"ComputerVillage: Error on page {page}: {e}")
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                page += 1
                continue
            
            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select(".product-thumb")
            
            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info(f"ComputerVillage: No more products found, stopping at page {page}")
                    break
                page += 1
                continue
            
            consecutive_empty = 0
            
            for item in items:
                name_tag = item.select_one(".name a")
                price_tag = item.select_one(".price")
                img_tag = item.select_one(".image img")
                stock_tag = item.select_one(".product-label")
                
                if not name_tag:
                    continue
                
                in_stock = True
                if stock_tag and "Out Of Stock" in stock_tag.text:
                    in_stock = False
                
                products.append({
                    "id": str(uuid.uuid4()),
                    "name": name_tag.text.strip(),
                    "price": normalize_price(price_tag.text.strip()) if price_tag else "Out of Stock",
                    "img": (img_tag.get("data-src") or img_tag.get("src") or "") if img_tag else "",
                    "link": name_tag["href"] if name_tag else "",
                    "in_stock": in_stock
                })

            page += 1
            smart_delay(0.2, 0.5)  # Small delay between pages

        logger.info(f"ComputerVillage: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"ComputerVillage catalog error: {e}", exc_info=True)
        return {"products": [], "logo": ""}
    finally:
        session.close()


def scrape_smartbd_catalog(category, max_pages=50):
    """Scrape all pages from SmartBD for a category"""
    session = create_session()
    try:
        products = []
        logo_url = "https://smartbd.com/wp-content/uploads/2021/01/smartbd-logo.png"
        page = 1
        consecutive_empty = 0
        headers = {"User-Agent": get_random_user_agent()}

        while page <= max_pages:
            if page == 1:
                url = f"https://smartbd.com/?s={urllib.parse.quote(category)}&post_type=product"
            else:
                url = f"https://smartbd.com/page/{page}/?s={urllib.parse.quote(category)}&post_type=product"

            logger.info(f"SmartBD: Scraping page {page} for {category}")

            try:
                response = session.get(url, headers=headers, timeout=30)
                if response.status_code != 200:
                    logger.warning(f"SmartBD: Page {page} returned {response.status_code}")
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                    page += 1
                    continue
            except (requests.Timeout, requests.ConnectionError) as e:
                logger.warning(f"SmartBD: Error on page {page}: {e}")
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                page += 1
                continue
            
            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("div.product-block.grid")
            
            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info(f"SmartBD: No more products found, stopping at page {page}")
                    break
                page += 1
                continue
            
            consecutive_empty = 0
            
            for item in items:
                name_tag = item.select_one("h3.name a")
                price_tag = item.select_one(".price")
                img_tag = item.select_one("img")
                
                if not name_tag:
                    continue
                
                img_url = ""
                if img_tag:
                    img_url = img_tag.get("data-src") or img_tag.get("src") or ""
                
                price_text = ""
                if price_tag:
                    price_text = price_tag.text.replace("\xa0", "").strip()
                
                products.append({
                    "id": str(uuid.uuid4()),
                    "name": name_tag.text.strip(),
                    "price": normalize_price(price_text) if price_text else "Out of Stock",
                    "img": img_url,
                    "link": name_tag["href"] if name_tag else "",
                    "in_stock": True
                })
            
            page += 1
            smart_delay(0.2, 0.5)  # Small delay between pages
        
        logger.info(f"SmartBD: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"SmartBD catalog error: {e}", exc_info=True)
        return {"products": [], "logo": ""}
    finally:
        session.close()


def scrape_selltech_catalog(category, max_pages=50):
    """Scrape all pages from SellTech for a category"""
    session = create_session()
    try:
        products = []
        logo_url = "https://www.selltech.com.bd/image/cache/catalog/logo-200x50.png"
        page = 1
        consecutive_empty = 0
        headers = {"User-Agent": get_random_user_agent()}
        base_url = f"https://www.selltech.com.bd/index.php?route=product/search&search={urllib.parse.quote(category)}"

        while page <= max_pages:
            url = base_url if page == 1 else f"{base_url}&page={page}"
            logger.info(f"SellTech: Scraping page {page} for {category}")

            try:
                response = session.get(url, headers=headers, timeout=30)
                if response.status_code != 200:
                    logger.warning(f"SellTech: Page {page} returned {response.status_code}")
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                    page += 1
                    continue
            except (requests.Timeout, requests.ConnectionError) as e:
                logger.warning(f"SellTech: Error on page {page}: {e}")
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                page += 1
                continue
            
            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("div.product-layout")
            
            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info(f"SellTech: No more products found, stopping at page {page}")
                    break
                page += 1
                continue
            
            consecutive_empty = 0
            
            for item in items:
                name_tag = item.select_one(".name a")
                price_tag = item.select_one(".price")
                img_tag = item.select_one(".image img")
                stock_tag = item.select_one(".stock")
                
                if not name_tag:
                    continue
                
                in_stock = True
                if stock_tag and "Out" in stock_tag.text:
                    in_stock = False
                
                products.append({
                    "id": str(uuid.uuid4()),
                    "name": name_tag.text.strip(),
                    "price": normalize_price(price_tag.text.strip()) if price_tag else "Out of Stock",
                    "img": (img_tag.get("data-src") or img_tag.get("src") or "") if img_tag else "",
                    "link": name_tag["href"] if name_tag else "",
                    "in_stock": in_stock
                })

            page += 1
            smart_delay(0.2, 0.5)  # Small delay between pages

        logger.info(f"SellTech: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"SellTech catalog error: {e}", exc_info=True)
        return {"products": [], "logo": ""}
    finally:
        session.close()


def scrape_globalbrand_catalog(category, max_pages=50):
    """Scrape all pages from GlobalBrand for a category"""
    session = create_session()
    try:
        products = []
        logo_url = "https://www.globalbrand.com.bd/image/cache/catalog/logo-200x50.png"
        page = 1
        consecutive_empty = 0
        headers = {"User-Agent": get_random_user_agent()}
        base_url = f"https://www.globalbrand.com.bd/index.php?route=product/search&search={urllib.parse.quote(category)}"

        while page <= max_pages:
            url = base_url if page == 1 else f"{base_url}&page={page}"
            logger.info(f"GlobalBrand: Scraping page {page} for {category}")

            try:
                response = session.get(url, headers=headers, timeout=30)
                if response.status_code != 200:
                    logger.warning(f"GlobalBrand: Page {page} returned {response.status_code}")
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                    page += 1
                    continue
            except (requests.Timeout, requests.ConnectionError) as e:
                logger.warning(f"GlobalBrand: Error on page {page}: {e}")
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                page += 1
                continue
            
            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("div.product-layout")
            
            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info(f"GlobalBrand: No more products found, stopping at page {page}")
                    break
                page += 1
                continue
            
            consecutive_empty = 0
            
            for item in items:
                name_tag = item.select_one(".name a")
                price_tag = item.select_one(".price")
                img_tag = item.select_one(".image img")
                stock_tag = item.select_one(".stock")
                
                if not name_tag:
                    continue
                
                in_stock = True
                if stock_tag and "Out" in stock_tag.text:
                    in_stock = False
                
                products.append({
                    "id": str(uuid.uuid4()),
                    "name": name_tag.text.strip(),
                    "price": normalize_price(price_tag.text.strip()) if price_tag else "Out of Stock",
                    "img": (img_tag.get("data-src") or img_tag.get("src") or "") if img_tag else "",
                    "link": name_tag["href"] if name_tag else "",
                    "in_stock": in_stock
                })

            page += 1
            smart_delay(0.2, 0.5)  # Small delay between pages

        logger.info(f"GlobalBrand: Total scraped {len(products)} products for {category}")
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        logger.error(f"GlobalBrand catalog error: {e}", exc_info=True)
        return {"products": [], "logo": ""}
    finally:
        session.close()


async def scrape_ryans_playwright(playwright_page, category, max_pages=50):
    """Scrape Ryans using an existing Playwright page instance.

    The browser and context must already be created by the caller.
    This avoids launching a new browser for every category, saving RAM.
    """
    products = []
    logo_url = "https://www.ryans.com/assets/images/ryans-logo.svg"
    base_url = f"https://www.ryans.com/search?q={urllib.parse.quote(category)}"
    page_num = 1
    consecutive_empty = 0

    while page_num <= max_pages:
        url = f"{base_url}&limit=30&page={page_num}"
        logger.info(f"Ryans (Playwright): page {page_num} for {category}")

        try:
            await playwright_page.goto(url, wait_until="load", timeout=60000)

            # Wait for Cloudflare Rocket Loader to finish re-executing scripts,
            # then confirm the product grid is rendered before reading content.
            try:
                await playwright_page.wait_for_selector(
                    ".category-single-product", timeout=15000
                )
            except PlaywrightTimeout:
                # Product grid didn't appear — may be CF challenge or empty page
                pass

            await asyncio.sleep(random.uniform(1.0, 2.0))
            content = await playwright_page.content()

            # If Cloudflare challenge appears, wait and retry once
            if "just a moment" in content.lower() or "checking your browser" in content.lower():
                logger.warning(f"Ryans: Cloudflare challenge on page {page_num}, waiting 12s...")
                await asyncio.sleep(12)
                content = await playwright_page.content()
                if "just a moment" in content.lower() or "checking your browser" in content.lower():
                    logger.warning(f"Ryans: Cloudflare persists on page {page_num}, stopping")
                    break

            soup = BeautifulSoup(content, "html.parser")
            items = soup.select(".category-single-product")

            if not items:
                consecutive_empty += 1
                logger.info(f"Ryans: No products on page {page_num}, consecutive empty: {consecutive_empty}")
                if consecutive_empty >= 2:
                    logger.info(f"Ryans: No more products, stopping at page {page_num}")
                    break
                page_num += 1
                await asyncio.sleep(0.3)
                continue

            consecutive_empty = 0

            for item in items:
                name_elem = item.select_one(".product-title a")
                price_elem = item.select_one(".pr-text")
                link_elem = item.select_one(".image-box a")
                img_elem = item.select_one(".image-box img")

                if name_elem:
                    product_link = (
                        urllib.parse.urljoin(url, link_elem["href"])
                        if link_elem and link_elem.has_attr("href")
                        else "#"
                    )
                    product_price = (
                        normalize_price(price_elem.get_text(strip=True))
                        if price_elem
                        else "Out of Stock"
                    )
                    product_img = (
                        img_elem["src"] if img_elem and img_elem.has_attr("src") else ""
                    )
                    if product_img and not product_img.startswith(("http://", "https://")):
                        product_img = urllib.parse.urljoin(url, product_img)

                    products.append({
                        "id": str(uuid.uuid4()),
                        "name": name_elem.get_text(strip=True),
                        "price": product_price,
                        "link": product_link,
                        "img": product_img,
                        "in_stock": True,
                    })

        except PlaywrightTimeout:
            logger.warning(f"Ryans: Timeout on page {page_num}, skipping")
        except Exception as e:
            logger.error(f"Ryans: Error on page {page_num}: {e}")
            break

        page_num += 1
        await asyncio.sleep(random.uniform(3.0, 5.0))  # Delay between pages to avoid CF rate limit

    logger.info(f"Ryans (Playwright): Total {len(products)} products for {category}")
    return {"products": products, "logo": logo_url}

