# API Examples

## Basic Usage

### Simple Product Search

**Request:**
```http
GET /api/price-comparison/?product=laptop
```

**Response:**
```json
[
  {
    "name": "StarTech",
    "logo": "https://www.startech.com.bd/catalog/view/theme/starship/images/logo.png",
    "products": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "ASUS VivoBook 15 X515EA",
        "price": "৳45,000",
        "image": "https://example.com/laptop1.jpg",
        "url": "https://www.startech.com.bd/asus-vivobook-15"
      },
      {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "HP Pavilion 14-dv0",
        "price": "৳42,500",
        "image": "https://example.com/laptop2.jpg",
        "url": "https://www.startech.com.bd/hp-pavilion-14"
      }
    ]
  }
]
```

### Multiple Shops Response

**Request:**
```http
GET /api/price-comparison/?product=mouse
```

**Response:**
```json
[
  {
    "name": "StarTech",
    "products": [
      {
        "id": "uuid-here-001",
        "name": "Logitech G502 HERO Gaming Mouse",
        "price": "৳5,500",
        "img": "/path/to/image1.jpg",
        "link": "/logitech-g502-hero"
      }
    ],
    "logo": "https://www.startech.com.bd/catalog/view/theme/starship/images/logo.png"
  },
  {
    "name": "Binary",
    "products": [
      {
        "id": "uuid-here-002",
        "name": "Razer DeathAdder V3 Gaming Mouse",
        "price": "৳4,800",
        "img": "/path/to/image2.jpg", 
        "link": "/razer-deathadder-v3"
      }
    ],
    "logo": "https://www.binarylogic.com.bd/images/logo.png"
  }
]
```

## JavaScript/Frontend Integration

### Using Fetch API

```javascript
async function searchProduct(productName) {
  try {
    const response = await fetch(
      `http://localhost:8000/api/price-comparison/?product=${encodeURIComponent(productName)}`
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching prices:', error);
    throw error;
  }
}

// Usage
searchProduct('gaming keyboard')
  .then(results => {
    results.forEach(shop => {
      console.log(`${shop.name}: ${shop.products.length} products found`);
    });
  })
  .catch(error => {
    console.error('Search failed:', error);
  });
```

### Using Axios

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api/',
  timeout: 30000, // 30 seconds timeout
});

async function getPrices(product) {
  try {
    const response = await api.get('price-comparison/', {
      params: { product }
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      // Server responded with error status
      console.error('API Error:', error.response.data);
    } else if (error.request) {
      // Request timeout or network error
      console.error('Network Error:', error.message);
    }
    throw error;
  }
}
```

## Python Client Example

```python
import requests
import json

class BDPriceGearClient:
    def __init__(self, base_url="http://localhost:8000/api/"):
        self.base_url = base_url
        
    def search_product(self, product):
        """Search for product prices across multiple stores"""
        url = f"{self.base_url}price-comparison/"
        params = {
            'product': product
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error searching for {product}: {e}")
            return None
    
    def find_cheapest(self, product):
        """Find the cheapest price for a product"""
        results = self.search_product(product)
        if not results:
            return None
            
        cheapest = None
        lowest_price = float('inf')
        
        for shop in results:
            for product_item in shop['products']:
                # Extract numeric price (assuming ৳X,XXX format)
                price_str = product_item['price'].replace('৳', '').replace(',', '')
                try:
                    price = float(price_str)
                    if price < lowest_price:
                        lowest_price = price
                        cheapest = {
                            'shop': shop['name'],
                            'product': product_item,
                            'price': price
                        }
                except ValueError:
                    continue
                    
        return cheapest

# Usage
client = BDPriceGearClient()

# Search for products
results = client.search_product("gaming headset")
print(json.dumps(results, indent=2))

# Find cheapest option
cheapest = client.find_cheapest("mechanical keyboard")
if cheapest:
    print(f"Cheapest: {cheapest['product']['name']} at {cheapest['shop']} for ৳{cheapest['price']}")
```

## cURL Examples

### Basic Search
```bash
curl "http://localhost:8000/api/price-comparison/?product=smartphone"
```

### With Headers
```bash
curl -H "Accept: application/json" \
     -H "User-Agent: MyApp/1.0" \
     "http://localhost:8000/api/price-comparison/?product=laptop"
```

### With URL Encoding
```bash
curl -X GET \
     -H "Content-Type: application/json" \
     "http://localhost:8000/api/price-comparison/?product=gaming%20keyboard"
```

## Error Handling Examples

### Handling Missing Product Parameter
```javascript
fetch('http://localhost:8000/api/price-comparison/')
  .then(response => {
    if (response.status === 400) {
      return response.json().then(error => {
        console.error('Bad Request:', error.error); // "Missing 'product' query parameter"
      });
    }
    return response.json();
  })
  .catch(error => console.error('Network error:', error));
```

### Handling Network Timeouts
```python
import requests
from requests.exceptions import Timeout, ConnectionError

try:
    response = requests.get(
        'http://localhost:8000/api/price-comparison/',
        params={'product': 'mouse'},
        timeout=30  # 30 second timeout for scraping
    )
    data = response.json()
except Timeout:
    print("Request timed out - the scraping might be taking longer than usual")
except ConnectionError:
    print("Could not connect to the API server")
except requests.exceptions.HTTPError as e:
    print(f"HTTP error occurred: {e}")
```

## Performance Tips

1. **Cache results**: The API automatically caches for 5 minutes, but consider client-side caching too
2. **Set proper timeouts**: Web scraping can take 10-20 seconds, set timeouts to 30+ seconds
3. **Handle empty responses**: Some shops may not have your product, the API filters these out
4. **Retry logic**: Implement retry with exponential backoff for network failures
5. **Use specific product names**: More specific queries tend to return better results