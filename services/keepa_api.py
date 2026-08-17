"""
Keepa API Integration - Based on official documentation (keepa.com/api-docs/)
Endpoints: /product, /query (Product Finder), /bestsellers, /category
"""
import httpx
import asyncio
from typing import Optional
from config import settings

KEEPA_BASE = "https://api.keepa.com"
KEEPA_TIME_OFFSET = 21564000  # minutes offset for Keepa Time conversion

DOMAINS = {"US": 1, "UK": 2, "DE": 3, "FR": 4, "JP": 5, "CA": 6, "IT": 8, "ES": 9, "IN": 10, "MX": 11, "BR": 12}

# csv[] price type indices (from official docs)
AMAZON = 0
NEW = 1
USED = 2
SALES = 3
LISTPRICE = 4
COLLECTIBLE = 5
REFURBISHED = 6
NEW_FBM_SHIPPING = 7
LIGHTNING_DEAL = 8
WAREHOUSE = 9
NEW_FBA = 10
COUNT_NEW = 11
COUNT_USED = 12
COUNT_REFURBISHED = 13
COUNT_COLLECTIBLE = 14
RATING = 16
COUNT_REVIEWS = 17
BUY_BOX_SHIPPING = 18  # requires offers param
USED_NEW_SHIPPING = 19
BUY_BOX_USED_SHIPPING = 32
PRIME_EXCL = 33
COUNT_NEW_FBA = 34
COUNT_NEW_FBM = 35


def keepa_to_usd(v) -> float:
    """Convert Keepa cents to USD. -1 = no data."""
    if v is None or v < 0:
        return 0.0
    return round(v / 100, 2)


def keepa_time_to_dt(keepa_minutes):
    """Convert Keepa Time minutes to Unix epoch seconds."""
    if keepa_minutes is None or keepa_minutes < 0:
        return None
    return (keepa_minutes + KEEPA_TIME_OFFSET) * 60


def decode_csv(history, with_shipping=False):
    """Decode a csv history array into data points."""
    if history is None:
        return []
    step = 3 if with_shipping else 2
    points = []
    for i in range(0, len(history), step):
        if i + 1 >= len(history):
            break
        pt = {"t": keepa_time_to_dt(history[i]), "v": history[i + 1]}
        if with_shipping and i + 2 < len(history):
            pt["shipping"] = history[i + 2]
        points.append(pt)
    return points


class KeepaService:
    """Keepa API client for Amazon FBA Wholesale."""

    def __init__(self):
        self.api_key = settings.keepa_api_key

    # ─────────────────────────────────────────
    # PRODUCT REQUEST (/product)
    # ─────────────────────────────────────────

    async def get_product(self, asin: str, with_offers: bool = False) -> Optional[dict]:
        """
        Get product data from Keepa.
        
        Args:
            asin: Amazon ASIN
            with_offers: If True, fetch live offers (6 tokens per offer page).
                         Enables Buy Box data, FBA/FBM prices, rating history.
                         If False, uses 1 token per product.
        """
        params = {
            "key": self.api_key,
            "domain": 1,  # US
            "asin": asin,
            "stats": 180,  # 180-day stats interval
            "history": 1,  # include price history
            "days": 180,   # limit history to 180 days (saves bandwidth)
        }
        if with_offers:
            params["offers"] = 20  # up to 20 offers

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(f"{KEEPA_BASE}/product", params=params)
                data = resp.json()
                if resp.status_code == 200 and data.get("products"):
                    return self._parse_product(data["products"][0], data.get("tokensConsumed", 0))
                return None
            except Exception as e:
                print(f"Keepa error for {asin}: {e}")
                return None

    async def get_products_batch(self, asins: list[str], with_offers: bool = False) -> list[dict]:
        """Get data for up to 100 ASINs per request."""
        results = []
        for i in range(0, len(asins), 100):
            batch = asins[i:i + 100]
            params = {
                "key": self.api_key,
                "domain": 1,
                "asin": ",".join(batch),
                "stats": 180,
                "history": 1,
                "days": 180,
            }
            if with_offers:
                params["offers"] = 20

            async with httpx.AsyncClient(timeout=60) as client:
                try:
                    resp = await client.get(f"{KEEPA_BASE}/product", params=params)
                    data = resp.json()
                    if resp.status_code == 200:
                        for p in data.get("products", []):
                            results.append(self._parse_product(p, data.get("tokensConsumed", 0)))
                    elif resp.status_code == 429:
                        print("Keepa rate limit - waiting 60s")
                        await asyncio.sleep(60)
                except Exception as e:
                    print(f"Keepa batch error: {e}")

            if i + 100 < len(asins):
                await asyncio.sleep(1.5)

        return results

    # ─────────────────────────────────────────
    # PRODUCT FINDER (/query)
    # ─────────────────────────────────────────

    async def product_finder(
        self,
        selection: dict,
        with_stats: bool = False,
    ) -> dict:
        """
        Search Keepa's product database with complex filters.
        
        Token cost: 10 base + 1 per 100 ASINs returned.
        With stats=1: +30 tokens + 1 per 1M products matched.
        
        Args:
            selection: Query JSON following Keepa Product Finder format.
                       Example: {"rootCategory": 1055398, "current_BUY_BOX_SHIPPING_gte": 1500, "offerCountFBA_lte": 15}
            with_stats: Include Search Insights (aggregated KPIs).
        """
        params = {"key": self.api_key, "domain": 1}
        if with_stats:
            params["stats"] = 1

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(
                    f"{KEEPA_BASE}/query",
                    params=params,
                    json=selection,
                )
                data = resp.json()
                if resp.status_code == 200:
                    return {
                        "asins": data.get("asinList", []),
                        "total_results": data.get("totalResults", 0),
                        "search_insights": data.get("searchInsights", {}),
                        "tokens_consumed": data.get("tokensConsumed", 0),
                    }
                elif resp.status_code == 429:
                    return {"error": "Rate limit hit", "asins": [], "total_results": 0}
            except Exception as e:
                return {"error": str(e), "asins": [], "total_results": 0}
        return {"asins": [], "total_results": 0}

    # ─────────────────────────────────────────
    # BEST SELLERS (/bestsellers)
    # ─────────────────────────────────────────

    async def get_best_sellers(self, category: str | int, range_days: int = 0) -> dict:
        """
        Get best seller list for a category or product group.
        
        Token cost: 50 flat.
        
        Args:
            category: Category node ID (int) or product group name (str like "Beauty").
            range_days: 0=current, 30=30-day avg, 90=90-day avg, 180=180-day avg.
        """
        params = {
            "key": self.api_key,
            "domain": 1,
            "category": category,
        }
        if range_days > 0:
            params["range"] = range_days

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(f"{KEEPA_BASE}/bestsellers", params=params)
                data = resp.json()
                if resp.status_code == 200 and "bestSellersList" in data:
                    bs = data["bestSellersList"]
                    return {
                        "asins": bs.get("asinList", []),
                        "category_id": bs.get("categoryId", 0),
                        "last_update": bs.get("lastUpdate", 0),
                        "tokens_consumed": data.get("tokensConsumed", 0),
                    }
            except Exception as e:
                print(f"Keepa bestsellers error: {e}")
        return {"asins": []}

    # ─────────────────────────────────────────
    # CATEGORY LOOKUP (/category)
    # ─────────────────────────────────────────

    async def get_categories(self, category_id: int = 0) -> list[dict]:
        """
        Look up categories. categoryId=0 returns all root categories.
        Token cost: 1 per category + 1 for parent tree.
        """
        params = {
            "key": self.api_key,
            "domain": 1,
            "category": category_id,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(f"{KEEPA_BASE}/category", params=params)
                data = resp.json()
                cats = []
                for cat_id, cat_data in data.get("categories", {}).items():
                    cats.append({
                        "id": int(cat_id),
                        "name": cat_data.get("name", ""),
                        "parent": cat_data.get("parent", 0),
                    })
                return cats
            except Exception as e:
                print(f"Keepa categories error: {e}")
        return []

    # ─────────────────────────────────────────
    # PARSING
    # ─────────────────────────────────────────

    def _parse_product(self, product: dict, tokens_used: int = 0) -> dict:
        """Parse a Keepa product object into our format."""
        stats = product.get("stats", {})
        csv_data = product.get("csv", [])
        current = stats.get("current", [])

        # ── Prices (from stats.current) ──
        amazon_price = keepa_to_usd(current[AMAZON] if len(current) > AMAZON else -1)
        marketplace_new = keepa_to_usd(current[NEW] if len(current) > NEW else -1)
        buy_box_price = keepa_to_usd(current[BUY_BOX_SHIPPING] if len(current) > BUY_BOX_SHIPPING else -1)
        buy_box_used = keepa_to_usd(current[BUY_BOX_USED_SHIPPING] if len(current) > BUY_BOX_USED_SHIPPING else -1)

        # Best sell price: Buy Box > Marketplace New > Amazon
        sell_price = buy_box_price if buy_box_price > 0 else (marketplace_new if marketplace_new > 0 else amazon_price)

        # ── BSR (csv index 3) ──
        bsr = 0
        if csv_data and len(csv_data) > SALES and csv_data[SALES]:
            last = csv_data[SALES][-1]
            bsr = last if last and last > 0 else 0

        # ── Offer counts ──
        fba_count = current[COUNT_NEW_FBA] if len(current) > COUNT_NEW_FBA else (current[COUNT_NEW] if len(current) > COUNT_NEW else 0)
        fbm_count = current[COUNT_NEW_FBM] if len(current) > COUNT_NEW_FBM else 0
        total_new_offers = current[COUNT_NEW] if len(current) > COUNT_NEW else 0

        # ── Amazon as seller ──
        is_amazon = False
        if stats.get("buyBoxIsAmazon"):
            is_amazon = True
        elif amazon_price > 0 and stats.get("buyBoxSellerId") == "ATVPDKIKX0DER":
            is_amazon = True

        # ── Monthly sales ──
        monthly_sold = product.get("monthlySold") or stats.get("monthlySold") or 0

        # ── Rating & Reviews (from csv) ──
        rating = 0
        review_count = 0
        if csv_data and len(csv_data) > RATING and csv_data[RATING]:
            rating_val = csv_data[RATING][-1]
            rating = (rating_val / 10) if rating_val and rating_val > 0 else 0
        if csv_data and len(csv_data) > COUNT_REVIEWS and csv_data[COUNT_REVIEWS]:
            review_count = csv_data[COUNT_REVIEWS][-1] or 0

        # ── FBA Fees (EXACT from Keepa) ──
        fba_fees_obj = product.get("fbaFees") or {}
        pick_and_pack = fba_fees_obj.get("pickAndPackFee", 0) or 0
        fba_fee = round(pick_and_pack / 100, 2) if pick_and_pack > 0 else 0
        referral_pct = product.get("referralFeePercentage") or 0
        variable_closing = product.get("variableClosingFee") or 0
        referral_fee = round(sell_price * referral_pct / 100, 2) if sell_price > 0 and referral_pct > 0 else 0

        # ── Weight & Dimensions ──
        weight_grams = product.get("packageWeight") or product.get("itemWeight") or 0
        weight_lbs = round(weight_grams / 453.592, 2) if weight_grams > 0 else 0

        # ── Category ──
        cat_tree = product.get("categoryTree", [])
        category = cat_tree[-1].get("name", "") if cat_tree else ""
        root_cat_id = product.get("rootCategory", 0)

        # ── Image ──
        images = product.get("images", [])
        image_url = ""
        if images:
            img_name = images[0].get("l") or images[0].get("m", "")
            if img_name:
                image_url = f"https://m.media-amazon.com/images/I/{img_name}"

        # ── Identifiers ──
        upc = (product.get("upcList") or [""])[0]
        ean = (product.get("eanList") or [""])[0]

        # ── Buy Box analysis ──
        buy_box_is_fba = stats.get("buyBoxIsFBA", False)
        buy_box_seller_id = stats.get("buyBoxSellerId", "")

        # ── Price history for charts ──
        bb_history = decode_csv(csv_data[BUY_BOX_SHIPPING] if csv_data and len(csv_data) > BUY_BOX_SHIPPING else None, with_shipping=True)
        bsr_history = decode_csv(csv_data[SALES] if csv_data and len(csv_data) > SALES else None)

        # ── Sales rank drops (demand indicator) ──
        sr_drops_30 = stats.get("salesRankDrops30", 0)
        sr_drops_90 = stats.get("salesRankDrops90", 0)

        # ── Out of stock % ──
        oos_90 = -1
        oos_arr = stats.get("outOfStockPercentage90", [])
        if oos_arr and len(oos_arr) > AMAZON:
            oos_90 = oos_arr[AMAZON]

        return {
            "asin": product.get("asin", ""),
            "title": product.get("title", ""),
            "brand": product.get("brand", ""),
            "manufacturer": product.get("manufacturer", ""),
            "category": category,
            "root_category_id": root_cat_id,
            "category_tree": [{"id": c.get("catId", 0), "name": c.get("name", "")} for c in cat_tree],
            "image_url": image_url,
            "upc": upc,
            "ean": ean,

            # Prices
            "amazon_price": amazon_price,
            "marketplace_new_price": marketplace_new,
            "buy_box_price": buy_box_price,
            "buy_box_used_price": buy_box_used,
            "sell_price": sell_price,

            # Metrics
            "bsr": bsr,
            "monthly_sales_est": monthly_sold,
            "fba_seller_count": fba_count,
            "fbm_seller_count": fbm_count,
            "total_new_offers": total_new_offers,
            "is_amazon_seller": is_amazon,
            "review_count": review_count,
            "rating": rating,
            "sr_drops_30": sr_drops_30,
            "sr_drops_90": sr_drops_90,
            "oos_pct_90": oos_90,

            # FBA Fees (EXACT)
            "fba_fee": fba_fee,
            "referral_fee_pct": referral_pct,
            "referral_fee": referral_fee,
            "variable_closing_fee": round(variable_closing / 100, 2) if variable_closing else 0,

            # Buy Box
            "buy_box_is_fba": buy_box_is_fba,
            "buy_box_is_amazon": is_amazon,
            "buy_box_seller_id": buy_box_seller_id,

            # Product details
            "weight_lbs": weight_lbs,
            "weight_grams": weight_grams,

            # History for charts
            "buy_box_history": [{"t": p["t"], "price": keepa_to_usd(p["v"] + p.get("shipping", 0))} for p in bb_history[-60:]],
            "bsr_history": [{"t": p["t"], "bsr": p["v"]} for p in bsr_history[-60:]],

            # Stats
            "stats": {
                "avg90_new": keepa_to_usd(stats.get("avg90", [])[NEW] if len(stats.get("avg90", [])) > NEW else -1),
                "avg90_buybox": keepa_to_usd(stats.get("avg90", [])[BUY_BOX_SHIPPING] if len(stats.get("avg90", [])) > BUY_BOX_SHIPPING else -1),
                "min_buybox": keepa_to_usd(stats.get("min", [None] * 36)[BUY_BOX_SHIPPING][1] if len(stats.get("min", [])) > BUY_BOX_SHIPPING and stats.get("min", [])[BUY_BOX_SHIPPING] else -1),
                "offer_count_fba": stats.get("offerCountFBA", 0),
                "offer_count_fbm": stats.get("offerCountFBM", 0),
            },

            "tokens_used": tokens_used,
        }


keepa_service = KeepaService()
