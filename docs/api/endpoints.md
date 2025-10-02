# API Endpoints

## Base URL
```
http://localhost:8000/api/
```

## Price Comparison Endpoint

### GET /api/price-comparison/

Compare prices across multiple Bangladeshi tech shops.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product` | string | Yes | Product name to search for (e.g., 'laptop', 'mouse', 'keyboard') |

#### Example Request
```http
GET /api/price-comparison/?product=gaming%20mouse
```

#### Example Response
```json
[
  {
    "name": "StarTech",
    "products": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Logitech G502 Gaming Mouse",
        "price": "৳5,500",
        "img": "https://www.startech.com.bd/image/cache/catalog/mouse/logitech/g502-500x500.jpg",
        "link": "/logitech-g502-gaming-mouse"
      }
    ],
    "logo": "https://www.startech.com.bd/catalog/view/theme/starship/images/logo.png"
  },
  {
    "name": "Ryans",
    "products": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Razer DeathAdder V3",
        "price": "৳4,800",
        "img": "https://www.ryanscomputers.com/image/cache/catalog/mouse/razer-500x500.jpg",
        "link": "/razer-deathadder-v3"
      }
    ],
    "logo": "https://www.ryanscomputers.com/image/logo.png"
  }
]
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | E-commerce site name |
| `logo` | string | Site logo URL |
| `products` | array | Array of product objects |
| `products[].id` | string | Unique UUID identifier |
| `products[].name` | string | Product name |
| `products[].price` | string | Product price in BDT (or "Out Of Stock") |
| `products[].img` | string | Product image URL |
| `products[].link` | string | Relative product page URL |

#### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (missing product parameter) |
| 500 | Internal Server Error |

## Additional Endpoints

### GET /docs/
Interactive Swagger UI documentation for the API.

### GET /
Redirects to `/api/price-comparison/`

## HTTP Methods Supported

- **GET**: Main endpoint functionality
- **HEAD**: Returns headers only (for checking endpoint availability)  
- **OPTIONS**: CORS preflight support

## Response Time & Caching

- **First-time searches**: 10-20 seconds (depending on site availability)
- **Cached results**: < 100ms (instant)
- **Cache duration**: 5 minutes per product query
- **Cache cleanup**: Automatic removal of expired entries

## Error Handling

The API filters out empty results automatically. Only shops with available products are returned in the response.

## Supported E-commerce Sites

| Site Name | Internal Name | Type | Scraping Method |
|-----------|--------------|------|----------------|
| StarTech | StarTech | Static | BeautifulSoup + Requests |
| Ryans Computers | Ryans | Dynamic | Playwright (Chromium) |
| SkyLand Computer | SkyLand | Static | BeautifulSoup + Requests |
| PC House | PcHouse | Static | BeautifulSoup + Requests |
| UltraTech | UltraTech | Static | BeautifulSoup + Requests |
| Binary Logic | Binary | Dynamic | Playwright (Chromium) |
| PotakaIT | PotakaIT | Static | BeautifulSoup + Requests |

**Note**: Only shops with available products for your search query will appear in the response.