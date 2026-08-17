"""
Web Scraping Service - Scrape wholesale stores for profitable products.
Targets: Costco, Sam's Club, BJ's, Walmart, Target, Big Lots, and more.
"""
import httpx
import asyncio
import re
import json
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class ScrapedProduct:
    """A product scraped from a store."""
    store: str
    title: str
    price: float
    original_price: float = 0
    discount_pct: float = 0
    url: str = ""
    image_url: str = ""
    category: str = ""
    brand: str = ""
    upc: str = ""
    sku: str = ""
    in_stock: bool = True
    bulk_info: str = ""  # "Pack of 12", "Case quantity", etc.
    unit_price: float = 0  # Price per unit if bulk


STORE_INFO = {
    "costco_business": {
        "name": "Costco Business Center",
        "url": "https://www.costcobusinessdelivery.com",
        "wholesale": True,
        "account_type": "Business Membership",
        "membership_cost": "$60/year (Business) or $130/year (Gold Star Executive)",
        "how_to_open": """COMO ABRIR CUENTA EN COSTCO BUSINESS:
1. Ve a costcobusinessdelivery.com o visita la tienda fisica
2. Necesitas: Business license o EIN de tu empresa
3. Tipo de membresia: Business ($60/year) o Executive ($130/year con 2% cashback)
4. Puedes usar tu membresia personal de Costco si ya tienes una
5. NO necesitas Resale Certificate para comprar (pero si para evitar tax)
6. Puedes comprar en tienda o online con delivery

VENTAJAS PARA WHOLESALE:
- Precios muy bajos en productos de marca
- Packs grandes (ideal para FBA)
- Sin cantidad minima por producto
- Hay Costco Business Center en Chantilly, VA (cerca de Sterling!)
- Puedes escanear productos con la app de Costco""",
        "tips": [
            "Los mejores deals estan en la seccion de limpieza, hogar, y bebidas",
            "Revisa los precios online vs tienda - a veces hay diferencias",
            "Losproductos de Kirkland (marca Costco) no se pueden revender en Amazon",
            "Enfocate en marcas reconocidas: Tide, Bounty, Dawn, Charmin",
            "Revisa la seccion de ofertas/liquidacion en la tienda",
        ],
    },
    "sams_club": {
        "name": "Sam's Club",
        "url": "https://www.samsclub.com",
        "wholesale": True,
        "account_type": "Club Membership or Plus Membership",
        "membership_cost": "$50/year (Club) o $110/year (Plus con envio gratis)",
        "how_to_open": """COMO ABRIR CUENTA EN SAM'S CLUB:
1. Ve a samsclub.com o cualquier tienda Sam's Club
2. Membresia Club: $50/year - acceso a tienda y online
3. Membresia Plus: $110/year - envio gratis en online + 2% cashback
4. No necesitas business license para membresia personal
5. Para compra sin tax necesitas Resale Certificate
6. App "Scan & Go" para comprar mas rapido en tienda

VENTAJAS PARA WHOLESALE:
- Precios competitive con Costco
- "Scan & Go" en la app (escanea y paga sin hacer fila)
- Muchas ubicaciones en Virginia
- Ofertas flash online con descuentos grandes""",
        "tips": [
            "Usa la app de Sam's Club para escanear precios mientras caminas por la tienda",
            "Los Instant Savings son las mejores oportunidades",
            "Productos de marca Members Mark no se pueden revender en Amazon",
            "Busca productos con precio unitario bajo comparado con Amazon",
            "Revisa la seccion de Clearance en la tienda",
        ],
    },
    "bjs": {
        "name": "BJ's Wholesale Club",
        "url": "https://www.bjs.com",
        "wholesale": True,
        "account_type": "Inner Circle Membership",
        "membership_cost": "$55/year",
        "how_to_open": """COMO ABRIR CUENTA EN BJ's WHOLESALE:
1. Ve a bjs.com o visita una tienda
2. Membresia Inner Circle: $55/year
3. Aceptan cupones de fabricante (a diferencia de Costco)
4. Para compra sin tax: Resale Certificate
5. Tienen ubicaciones en Virginia y la Costa Este

VENTAJAS:
- Aceptan cupones de fabricante = precios mas bajos
- Puedes comprar unidades individuales (no solo packs grandes)
- Envio disponible en muchas areas""",
        "tips": [
            "La ventaja #1 de BJ's es que aceptan cupones de fabricante",
            "Combina cupones con ofertas de la tienda para maximizar ahorro",
            "Productos individuales facilitan el analisis de rentabilidad",
        ],
    },
    "walmart": {
        "name": "Walmart (Clearance & Online)",
        "url": "https://www.walmart.com",
        "wholesale": False,
        "account_type": "No membership required",
        "membership_cost": "Gratis (Walmart+ $12.95/mes para envio gratis)",
        "how_to_open": """COMO COMPRAR EN WALMART PARA REVENTA:
1. No necesitas cuenta especial - cualquier persona puede comprar
2. Enfocate en CLEARANCE (liquidacion) - esos son los mejores deals
3. Walmart+ ($12.95/mes) da envio gratis en ordenes $35+
4. Puedes comprar en tienda u online
5. Para arbitrage: busca precios de clearance en tienda que esten mas baratos que Amazon

VENTAJAS:
- No necesitas membresia
- Clearance deals con 50-90% descuento
- Muchas tiendas en el area de Sterling/NoVA
- Puedes devolver facilmente si el producto no se vende""",
        "tips": [
            "Los mejores deals de clearance estan al final de los pasillos",
            "Usa la app de Walmart para escanear y ver precios online vs tienda",
            "Los precios de clearance varian por tienda - visita varias",
            "Busca productos de marca con 50%+ descuento",
            "La seccion de juguetes tiene buenos deals post-navidad",
        ],
    },
    "target": {
        "name": "Target (Clearance)",
        "url": "https://www.target.com",
        "wholesale": False,
        "account_type": "No membership required",
        "membership_cost": "Gratis (RedCard 5% descuento)",
        "how_to_open": """COMO COMPRAR EN TARGET PARA REVENTA:
1. No necesitas cuenta especial
2. Target RedCard da 5% descuento en todo (credito o debito)
3. Enfocate en CLEARANCE - Target tiene ciclos de clearance predecibles
4. Circle offers + Clearance = ahorros maximos
5. Devoluciones faciles en 90 dias

VENTAJAS:
- Clearance con hasta 70% descuento
- 5% adicional con RedCard
- Marcas exclusivas que no estan en otros stores""",
        "tips": [
            "Target marca clearance por semanas: 15%, 30%, 50%, 70%",
            "Espera a que baje a 50-70% para maximizar margen",
            "Las mejores categorias: juguetes, hogar, belleza",
            "Usa la app Target para ver precios de clearance",
        ],
    },
    "big_lots": {
        "name": "Big Lots",
        "url": "https://www.biglots.com",
        "wholesale": False,
        "account_type": "No membership required",
        "membership_cost": "Gratis (BIGrewards programa gratis)",
        "how_to_open": """COMO COMPRAR EN BIG LOTS PARA REVENTA:
1. No necesitas membresia
2. Son tiendas de liquidacion/closeout
3. Precios muy bajos en productos de marca
4. Inventario cambia constantemente
5. Visita la tienda regularmente para nuevos arrivals

VENTAJAS:
- Productos de marca a precios de liquidacion
- No necesitas membresia
- Buenas categorias: hogar, alimentos, salud""",
        "tips": [
            "El inventario de Big Lots cambia SEMANALMENTE",
            "Visita la tienda 1-2 veces por semana para nuevos deals",
            "Los mejores deals se van rapido - compra cuando veas algo bueno",
        ],
    },
    "ollies": {
        "name": "Ollie's Bargain Outlet",
        "url": "https://www.ollies.us",
        "wholesale": False,
        "account_type": "No membership required",
        "membership_cost": "Gratis",
        "how_to_open": """COMO COMPRAR EN OLLIE'S PARA REVENTA:
1. No necesitas membresia
2. Son tiendas de liquidacion/closeout
3. Precios extremadamente bajos
4. Inventario impredecible - es "treasure hunt"
5. Hay ubicaciones en Virginia

VENTAJAS:
- Los precios mas bajos que encontraras
- Productos de marca conocida
- Buen margen si encuentras el producto correcto""",
        "tips": [
            "Ollie's es un 'treasure hunt' - no siempre encuentras lo mismo",
            "Los precios son imbatibles cuando hay producto bueno",
            "Revisa libros, juguetes, y hogar - son las mejores categorias",
        ],
    },
    "dollar_general": {
        "name": "Dollar General",
        "url": "https://www.dollargeneral.com",
        "wholesale": False,
        "account_type": "No membership required",
        "membership_cost": "Gratis",
        "how_to_open": """COMO COMPRAR EN DOLLAR GENERAL PARA REVENTA:
1. No necesitas membresia
2. Busca productos de marca en clearance
3. Muchos productos a $1-5 que se venden por mas en Amazon
4. Usa la app para ver ofertas y cupones digitales

VENTAJAS:
- Precios muy bajos en productos basicos
- Cupones digitales en la app
- Muchas ubicaciones""",
        "tips": [
            "La app de Dollar General tiene cupones que no estan en tienda",
            "Busca productos de marca en la seccion de clearance",
        ],
    },
    "faire": {
        "name": "Faire.com (Online Wholesale)",
        "url": "https://www.faire.com",
        "wholesale": True,
        "account_type": "Wholesale Buyer Account",
        "membership_cost": "Gratis - sin membresia",
        "how_to_open": """COMO ABRIR CUENTA EN FAIRE.COM:
1. Ve a faire.com y haz click en "Sign up as a retailer"
2. Necesitas: Business name, direccion, tipo de negocio
3. Aprobacion casi instantanea para la mayoria
4. No necesitas minimo de compra en muchas marcas
5. Envio gratis en primera orden con muchas marcas
6. Net 60 payment terms (pagan 60 dias despues)

VENTAJAS:
- Miles de marcas en un solo lugar
- Sin minimo de compra en muchas marcas
- Envio gratis en primera orden
- Terminos de pago flexibles (Net 60)
- Descubres marcas unicas que no estan en otros stores""",
        "tips": [
            "Faire es IDEAL para descubrir marcas unicas y trending",
            "Usa Net 60 payment para mejorar tu flujo de caja",
            "Revisa 'Trending' y 'Best Sellers' para encontrar oportunidades",
        ],
    },
    "tundra": {
        "name": "Tundra.com (Online Wholesale)",
        "url": "https://www.tundra.com",
        "wholesale": True,
        "account_type": "Buyer Account",
        "membership_cost": "Gratis - 0% comision para compradores",
        "how_to_open": """COMO ABRIR CUENTA EN TUNDRA.COM:
1. Ve a tundra.com y registrate como comprador
2. Necesitas: Business info basica
3. Aprobacion rapida
4. 0% comision para compradores (el vendedor paga)
5. Envio gratis en muchos productos

VENTAJAS:
- 0% comision para compradores
- Envio gratis en muchos productos
- Marcas directas (mejor precio que distribuidores)""",
        "tips": [
            "Tundra no cobra comision al comprador - ahorras vs otros plataformas",
            "Busca marcas directas para mejor precio",
        ],
    },
}


class StoreScraper:
    """Scrape products from wholesale stores."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    async def search_store(self, store_id: str, query: str, max_results: int = 20) -> list[dict]:
        """Search a store for products matching the query."""
        scrapers = {
            "walmart": self._scrape_walmart,
            "costco_business": self._scrape_costco,
            "sams_club": self._scrape_sams,
            "target": self._scrape_target,
            "big_lots": self._scrape_biglots,
        }

        scraper = scrapers.get(store_id)
        if not scraper:
            return [{"error": f"Scraper for {store_id} not available yet"}]

        try:
            return await scraper(query, max_results)
        except Exception as e:
            return [{"error": f"Scraping error: {str(e)}"}]

    async def _scrape_walmart(self, query: str, max_results: int) -> list[dict]:
        """Scrape Walmart search results."""
        url = "https://www.walmart.com/search"
        params = {"q": query, "sort": "best_seller"}

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url, params=params, headers=self.headers)
                if resp.status_code != 200:
                    return [{"error": f"Walmart returned status {resp.status_code}"}]

                # Try to extract JSON data from the page
                text = resp.text
                products = []

                # Look for product data in script tags
                json_match = re.search(r'__NEXT_DATA__.*?>(.*?)</script>', text, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        items = data.get("props", {}).get("pageProps", {}).get("initialData", {}).get("searchResult", {}).get("itemStacks", [{}])[0].get("items", [])
                        for item in items[:max_results]:
                            if item.get("__typename") == "Product":
                                products.append({
                                    "store": "Walmart",
                                    "title": item.get("name", ""),
                                    "price": item.get("priceInfo", {}).get("currentPrice", {}).get("price", 0),
                                    "original_price": item.get("priceInfo", {}).get("wasPrice", {}).get("price", 0),
                                    "url": f"https://www.walmart.com{item.get('canonicalUrl', '')}",
                                    "image_url": item.get("image", ""),
                                    "brand": item.get("brand", ""),
                                    "category": item.get("category", ""),
                                })
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass

                if not products:
                    # Fallback: basic HTML parsing
                    products = self._parse_basic_html(text, "Walmart", query)

                return products if products else [{"message": "No products found. Try a different search term."}]

            except Exception as e:
                return [{"error": str(e)}]

    async def _scrape_costco(self, query: str, max_results: int) -> list[dict]:
        """Scrape Costco Business Delivery."""
        url = f"https://www.costcobusinessdelivery.com/search?keyword={query.replace(' ', '+')}"

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers=self.headers)
                text = resp.text
                products = self._parse_basic_html(text, "Costco Business", query)
                return products if products else [{"message": "No products found. Costco Business Center is best visited in person."}]
            except Exception as e:
                return [{"error": str(e)}]

    async def _scrape_sams(self, query: str, max_results: int) -> list[dict]:
        """Scrape Sam's Club search."""
        url = f"https://www.samsclub.com/search/{query.replace(' ', '%20')}"

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers=self.headers)
                text = resp.text
                products = self._parse_basic_html(text, "Sam's Club", query)
                return products if products else [{"message": "No products found. Visit samsclub.com directly for best results."}]
            except Exception as e:
                return [{"error": str(e)}]

    async def _scrape_target(self, query: str, max_results: int) -> list[dict]:
        """Scrape Target search."""
        url = f"https://www.target.com/s?searchTerm={query.replace(' ', '+')}"

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers=self.headers)
                text = resp.text
                products = self._parse_basic_html(text, "Target", query)
                return products if products else [{"message": "No products found. Visit target.com directly."}]
            except Exception as e:
                return [{"error": str(e)}]

    async def _scrape_biglots(self, query: str, max_results: int) -> list[dict]:
        """Scrape Big Lots search."""
        url = f"https://www.biglots.com/search?q={query.replace(' ', '+')}"

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers=self.headers)
                text = resp.text
                products = self._parse_basic_html(text, "Big Lots", query)
                return products if products else [{"message": "No products found. Big Lots inventory varies by store - visit in person for best results."}]
            except Exception as e:
                return [{"error": str(e)}]

    def _parse_basic_html(self, html: str, store_name: str, query: str) -> list[dict]:
        """Basic HTML parsing fallback for product data."""
        products = []
        # Try to find price patterns
        price_pattern = r'\$(\d+\.?\d*)'
        title_pattern = r'<h[1-3][^>]*>(.*?)</h[1-3]>'

        # Look for structured data (JSON-LD)
        json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
        matches = re.findall(json_ld_pattern, html, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict) and data.get("@type") == "Product":
                    products.append({
                        "store": store_name,
                        "title": data.get("name", ""),
                        "price": float(data.get("offers", {}).get("price", 0)),
                        "url": data.get("url", ""),
                        "image_url": data.get("image", ""),
                        "brand": data.get("brand", {}).get("name", "") if isinstance(data.get("brand"), dict) else str(data.get("brand", "")),
                    })
            except (json.JSONDecodeError, ValueError):
                continue

        return products[:10]

    @staticmethod
    def get_store_info(store_id: str) -> dict:
        """Get information about a store and how to open an account."""
        return STORE_INFO.get(store_id, {"error": "Store not found"})

    @staticmethod
    def get_all_stores() -> list[dict]:
        """Get list of all supported stores."""
        return [
            {"id": sid, "name": info["name"], "wholesale": info["wholesale"], "membership": info["membership_cost"]}
            for sid, info in STORE_INFO.items()
        ]


scraper = StoreScraper()
