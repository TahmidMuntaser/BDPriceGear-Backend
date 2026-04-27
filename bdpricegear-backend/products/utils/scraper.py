import asyncio
import logging
import re
import uuid
import urllib.parse

from bs4 import BeautifulSoup
import requests

from playwright.async_api import async_playwright
from .catalog_scraper import (
    scrape_ryans_catalog,
    get_ryans_category_url,
    scrape_pchouse_catalog,
    scrape_computervillage_catalog,
    scrape_smartbd_catalog,
    scrape_selltech_catalog,
    scrape_globalbrand_catalog,
    create_session,
    get_random_user_agent,
)

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

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
def scrape_ryans(product):
    # Reuse catalog strategy so Render can use Playwright and local can use cloudscraper.
    # Keep first-page-only behavior for realtime endpoint.
    result = scrape_ryans_catalog(product, max_pages=1)
    if result.get("products"):
        return result

    # Fallback for cloud services where Playwright may not be installed.
    if not CLOUDSCRAPER_AVAILABLE:
        return result

    logo_url = "https://www.ryans.com/assets/images/ryans-logo.svg"
    base_url = get_ryans_category_url(product)
    url = f"{base_url}&limit=30&page=1" if 'search?q=' in base_url else f"{base_url}?limit=30&page=1"

    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True,
            },
            delay=5,
            interpreter='nodejs'
        )
        scraper.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
            "Referer": "https://www.google.com/",
        })
        response = scraper.get(url, timeout=45)
        if response.status_code != 200:
            return result

        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select(".category-single-product")
        products = []
        for item in items:
            name_elem = item.select_one(".product-name a") or item.select_one(".card-body .card-text a")
            price_elem = item.select_one(".pr-text")
            link_elem = item.select_one(".image-box a")
            img_elem = item.select_one(".image-box img")
            if not name_elem:
                continue

            product_link = urllib.parse.urljoin(url, link_elem["href"]) if link_elem and link_elem.has_attr("href") else "#"
            product_img = (img_elem.get("data-src") or img_elem.get("src") or "") if img_elem else ""
            if product_img and not product_img.startswith(("http://", "https://")):
                product_img = urllib.parse.urljoin(url, product_img)

            products.append({
                "id": str(uuid.uuid4()),
                "name": name_elem.get_text(strip=True),
                "price": normalize_price(price_elem.get_text(strip=True)) if price_elem else "Out of Stock",
                "link": product_link,
                "img": product_img,
                "in_stock": True,
            })

        if products:
            return {"products": products, "logo": logo_url}
    except Exception:
        return result

    return result


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
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        products = []
        logo_url = "https://www.startech.com.bd/image/catalog/logo.png"

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

    
# skyland     
def scrape_skyland(product):
    try:
        base_url = "https://www.skyland.com.bd/"
        url = f"{base_url}index.php?route=product/search&search={urllib.parse.quote(product)}"
        response = requests.get(url, timeout=10)
        soap = BeautifulSoup(response.text, "html.parser")
        
        products = []
        
        logo_url = "https://www.skyland.com.bd/image/cache/wp/gp/skyland-logo-1398x471.webp"
            
        for item in soap.select(".product-layout"):
            name = item.select_one(".name")
            price = item.select_one(".price-new")
            # Try multiple selector patterns for the image
            img = item.select_one(".image img") or item.select_one(".product-img img") or item.select_one("img")
            link = item.select_one(".product-img") or item.select_one(".name a")
            
            # Extract image URL properly
            img_url = "Image not found"
            if img and img.has_attr("src"):
                img_url = img["src"]
                # Make sure it's an absolute URL
                if not img_url.startswith(('http://', 'https://')):
                    img_url = urllib.parse.urljoin(base_url, img_url)
            elif img and img.has_attr("data-src"):
                img_url = img["data-src"]
                if not img_url.startswith(('http://', 'https://')):
                    img_url = urllib.parse.urljoin(base_url, img_url)
                    
            # Get product link
            link_url = "Link not found"
            if link and link.has_attr("href"):
                link_url = link["href"]
                if not link_url.startswith(('http://', 'https://')):
                    link_url = urllib.parse.urljoin(base_url, link_url)
            
            products.append({
                    "id": str(uuid.uuid4()),
                    "name": name.text.strip() if name else "Name not found",
                    "price": normalize_price(price.text.strip()) if price else "Out Of Stock",
                    "img": img_url,
                    "link": link_url
            })
            
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        
        logger.error(f"skyland error: {e}")
        return {"products": [], "logo": "logo not found"}    
    
    

# pchouse 
def scrape_pchouse(product):
    try:
        # Reuse the more resilient catalog scraper path for realtime requests.
        # That version already uses a pooled session, longer timeouts, redirects,
        # and retry handling that behaves better on hosted servers.
        return scrape_pchouse_catalog(product, max_pages=1)
    except Exception as e:
        logger.error(f"pchouse error: {e}")
        return {"products": [], "logo": "logo not found"}
    

# ultratech 
def scrape_ultratech(product):
    session = create_session()
    try:
        url = f"https://www.ultratech.com.bd/index.php?route=product/search&search={urllib.parse.quote(product)}"
        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        products = []
        
        logo_url = "https://www.ultratech.com.bd/image/cache/catalog/website/logo/ultra-technology-header-logo-500x500.png.webp"

        for item in soup.select(".product-layout"):
            name = (
                item.select_one(".caption .name a")
                or item.select_one(".name a")
                or item.select_one(".caption .name")
            )
            price = (
                item.select_one(".price-new")
                or item.select_one(".price-normal")
                or item.select_one(".price")
            )
            img = item.select_one(".product-img img")
            link = item.select_one("a.product-img")

            if not name or not link:
                continue

            image_url = ""
            if img:
                image_url = img.get("data-src") or img.get("src") or ""
                if image_url and not image_url.startswith(("http://", "https://")):
                    image_url = urllib.parse.urljoin(url, image_url)

            product_link = link.get("href", "")
            if product_link and not product_link.startswith(("http://", "https://")):
                product_link = urllib.parse.urljoin(url, product_link)
            
            products.append({
                    "id": str(uuid.uuid4()),
                    "name": name.get_text(strip=True),
                    "price": normalize_price(price.get_text(" ", strip=True)) if price else "Out Of Stock",
                    "img": image_url or "Image not found",
                    "link": product_link or "Link not found"
            })
            
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        
        logger.error(f"UltraTech error: {e}")
        return {"products": [], "logo": "logo not found"}
    finally:
        session.close()


# binary playwright
async def scrape_binary_playwright(product, context):
    results = {"products": [], "logo": "https://www.binarylogic.com.bd/images/brand_image/binary-logic.webp"}
    try:
        url = f"https://www.binarylogic.com.bd/search/{urllib.parse.quote(product)}"
        page = await context.new_page()
        await page.goto(url, timeout=12000, wait_until="domcontentloaded")
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        soup = BeautifulSoup(await page.content(), "html.parser")

        for item in soup.select(".single_product"):
            name_elem = item.select_one(".p-item-name")
            price_elem = item.select_one(".current_price")
            img_elem = item.select_one(".p-item-img img")
            link_elem = item.select_one(".p-item-img a")

            results["products"].append({
                "id": str(uuid.uuid4()),
                "name": name_elem.get_text(strip=True) if name_elem else "Name not found",
                "price": normalize_price(price_elem.get_text(strip=True) if price_elem else "0"),
                "link": urllib.parse.urljoin(url, link_elem["href"]) if link_elem else "#",
                "img": urllib.parse.urljoin(url, img_elem["src"]) if img_elem else "",
                "in_stock": True
            })

        await page.close()
        return results
    except Exception as e:
        logger.error(f"Binary Playwright error: {e}")
        return results

def scrape_computervillage(product):
    try:
        return scrape_computervillage_catalog(product, max_pages=1)
    except Exception as e:
        logger.error(f"ComputerVillage error: {e}")
        return {"products": [], "logo": "logo not found"}


def scrape_smartbd(product):
    try:
        return scrape_smartbd_catalog(product, max_pages=1)
    except Exception as e:
        logger.error(f"SmartBD error: {e}")
        return {"products": [], "logo": "logo not found"}


def scrape_selltech(product):
    try:
        return scrape_selltech_catalog(product, max_pages=1)
    except Exception as e:
        logger.error(f"SellTech error: {e}")
        return {"products": [], "logo": "logo not found"}


def scrape_globalbrand(product):
    try:
        return scrape_globalbrand_catalog(product, max_pages=1)
    except Exception as e:
        logger.error(f"GlobalBrand error: {e}")
        return {"products": [], "logo": "logo not found"}
