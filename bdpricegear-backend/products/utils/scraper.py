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
    results = {"products": [], "logo": "https://www.ryans.com/assets/images/ryans-logo.svg"}
    page = None
    try:
        url = f"https://www.ryans.com/search?q={urllib.parse.quote(product)}"
        page = await context.new_page()
        
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        await page.goto(url, timeout=15000, wait_until="load")
        await asyncio.sleep(2)
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        soup = BeautifulSoup(await page.content(), "html.parser")
        items = soup.select(".category-single-product")
        
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

        logger.info(f"Ryans: Scraped {len(results['products'])} products")
        return results
    except Exception as e:
        logger.error(f"Ryans error: {e}")
        return results
    finally:
        if page:
            await page.close()


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
        url = f"https://www.pchouse.com.bd/product/search?search={urllib.parse.quote(product)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=10)
        soap = BeautifulSoup(response.text, "html.parser")
        
        products = []
        
        # Get logo
        logo = soap.select_one(".logo img")
        if logo:
            logo_url = logo.get("src", "https://www.pchouse.com.bd/image/catalog/unnamed.png")
        else:
            logo_url = "https://www.pchouse.com.bd/image/catalog/unnamed.png"
            
        # Correct selector for PCHouse products
        product_items = soap.select(".single-product-item")
        
        for item in product_items:
            # Name 
            name_elem = item.select_one("h4 a")
            
            # Price 
            price_elem = item.select_one(".special-price") or item.select_one(".regular-price")
            
            # Image
            img_elem = item.select_one("img")
            
            # Link is the
            link_elem = item.select_one("h4 a")
            
            if name_elem:  
                products.append({
                    "id": str(uuid.uuid4()),
                    "name": name_elem.text.strip() if name_elem else "Name not found",
                    "price": normalize_price(price_elem.text.strip()) if price_elem else "Out Of Stock",
                    "img": img_elem.get("src", "Image not found") if img_elem else "Image not found",
                    "link": link_elem.get("href", "Link not found") if link_elem else "Link not found"
                })
            
        return {"products": products, "logo": logo_url}
    
    except Exception as e:
        
        logger.error(f"pchouse error: {e}")
        return {"products": [], "logo": "logo not found"}
    

# ultratech 
def scrape_ultratech(product):
    try:
        url = f"https://www.ultratech.com.bd/index.php?route=product/search&search={urllib.parse.quote(product)}"
        response = requests.get(url, timeout=10)
        soap = BeautifulSoup(response.text, "html.parser")
        
        products = []
        
        logo_url = "https://www.ultratech.com.bd/image/cache/catalog/website/logo/ultra-technology-header-logo-500x500.png.webp"
            
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

    
# potakaIT 
def scrape_potakait(product):
    try:
        url = f"https://www.potakait.com/index.php?route=product/search&search={urllib.parse.quote(product)}"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        products = []
        
        logo_url = "https://potakait.com/image/catalog/potaka-logo.png"
        
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