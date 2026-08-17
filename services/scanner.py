"""
Product Scanner - Scans supplier price lists OR searches Keepa directly.
"""
import csv
import io
import asyncio
from services.calculator import ProfitCalculator
from services.keepa_api import keepa_service


class ProductScanner:
    """Scan supplier price lists or search Keepa's database for profitable products."""

    async def scan_price_list(
        self,
        price_list: list[dict],
        min_roi: float = 15,
        min_profit: float = 2.50,
        max_sellers: int = 25,
        max_bsr: int = 100000,
        keep_amazon_sellers: bool = False,
    ) -> dict:
        """Scan a supplier price list against Amazon data from Keepa."""
        asins = [p["asin"] for p in price_list if p.get("asin")]
        keepa_data = {}
        batch_results = await keepa_service.get_products_batch(asins)
        for pd in batch_results:
            if pd and pd.get("asin"):
                keepa_data[pd["asin"]] = pd

        return self._analyze(price_list, keepa_data, min_roi, min_profit, max_sellers, max_bsr, keep_amazon_sellers)

    async def search_keepa_finder(
        self,
        root_category: int = None,
        min_price: float = 15,
        max_price: float = 100,
        max_bsr: int = 50000,
        max_fba_sellers: int = 15,
        min_monthly_sales: int = 30,
        min_reviews: int = 50,
        exclude_amazon: bool = True,
        sort_by: str = "bsr",
        max_results: int = 100,
    ) -> dict:
        """
        Search Keepa's Product Finder for profitable wholesale opportunities.
        Returns ASINs matching criteria, then fetches full product data.
        """
        selection = {
            "perPage": min(max_results, 200),
            "page": 0,
        }

        # Category filter
        if root_category:
            selection["rootCategory"] = [root_category]

        # Price range (in cents)
        if min_price:
            selection["current_BUY_BOX_SHIPPING_gte"] = int(min_price * 100)
        if max_price:
            selection["current_BUY_BOX_SHIPPING_lte"] = int(max_price * 100)

        # BSR filter
        if max_bsr:
            selection["current_SALES_lte"] = max_bsr

        # Offer count filter
        if max_fba_sellers:
            selection["offerCountFBA_lte"] = max_fba_sellers

        # Monthly sales
        if min_monthly_sales:
            selection["monthlySold_gte"] = min_monthly_sales

        # Reviews
        if min_reviews:
            selection["variationReviewCount_gte"] = min_reviews

        # Exclude Amazon as Buy Box holder
        if exclude_amazon:
            selection["buyBoxIsAmazon"] = False

        # Sort
        sort_map = {
            "bsr": ["current_SALES", "asc"],
            "price_low": ["current_BUY_BOX_SHIPPING", "asc"],
            "price_high": ["current_BUY_BOX_SHIPPING", "desc"],
            "sales": ["monthlySold", "desc"],
            "reviews": ["variationReviewCount", "desc"],
        }
        selection["sort"] = [sort_map.get(sort_by, sort_map["bsr"])]

        # Call Product Finder
        finder_result = await keepa_service.product_finder(selection, with_stats=False)

        if finder_result.get("error"):
            return {"error": finder_result["error"], "products": [], "total_found": 0}

        asins = finder_result.get("asins", [])
        total_found = finder_result.get("total_results", 0)

        if not asins:
            return {"products": [], "total_found": 0, "message": "No products found matching criteria"}

        # Fetch full product data for the ASINs
        products = await keepa_service.get_products_batch(asins[:max_results])

        # Calculate profitability for each
        analyzed = []
        for p in products:
            if not p or not p.get("asin"):
                continue
            calc = ProfitCalculator.from_keepa_product(p, buy_price=0)
            analyzed.append({
                **p,
                "calc": calc,
            })

        return {
            "products": analyzed,
            "total_found": total_found,
            "tokens_used": finder_result.get("tokens_consumed", 0),
        }

    async def get_category_best_sellers(self, category: str | int, limit: int = 50) -> dict:
        """Get best sellers for a category and analyze them."""
        bs = await keepa_service.get_best_sellers(category)
        asins = bs.get("asins", [])[:limit]

        if not asins:
            return {"products": [], "total": 0}

        products = await keepa_service.get_products_batch(asins)
        return {
            "products": [p for p in products if p],
            "total": len(asins),
        }

    def parse_csv_price_list(self, file_content: str) -> list[dict]:
        """Parse a CSV price list from a supplier."""
        reader = csv.DictReader(io.StringIO(file_content))
        products = []
        for row in reader:
            asin = ""
            cost = 0
            sku = ""
            for key, value in row.items():
                k = key.lower().strip()
                if k in ("asin", "asin/upc", "asin number", "amazon_asin"):
                    asin = value.strip()
                elif k in ("cost", "price", "unit_cost", "buy_price", "supplier_cost", "wholesale_price"):
                    try:
                        cost = float(value.replace("$", "").replace(",", "").strip())
                    except (ValueError, AttributeError):
                        cost = 0
                elif k in ("sku", "supplier_sku", "item_number", "item #", "product_sku"):
                    sku = value.strip()
            if asin and len(asin) == 10:
                products.append({"asin": asin.upper(), "supplier_cost": cost, "supplier_sku": sku})
        return products

    def _analyze(self, price_list, keepa_data, min_roi, min_profit, max_sellers, max_bsr, keep_amazon_sellers):
        """Analyze price list against Keepa data."""
        results = {
            "profitable": [],
            "marginal": [],
            "not_profitable": [],
            "errors": [],
            "stats": {"total_scanned": len(price_list), "profitable_count": 0, "marginal_count": 0, "not_profitable_count": 0, "error_count": 0, "avg_roi": 0, "avg_profit": 0, "best_roi": 0},
        }

        roi_sum = profit_sum = valid = 0

        for item in price_list:
            asin = item.get("asin", "")
            cost = float(item.get("supplier_cost", 0))
            kd = keepa_data.get(asin)

            if not kd:
                results["errors"].append({"asin": asin, "error": "No data"})
                continue
            if cost <= 0:
                results["errors"].append({"asin": asin, "error": "No cost"})
                continue

            # Filters
            reasons = []
            if kd["is_amazon_seller"] and not keep_amazon_sellers:
                reasons.append("Amazon sells this")
            if kd["fba_seller_count"] > max_sellers:
                reasons.append(f"Too many FBA sellers ({kd['fba_seller_count']})")
            if kd["bsr"] > max_bsr and kd["bsr"] > 0:
                reasons.append(f"BSR too high ({kd['bsr']:,})")
            if kd["sell_price"] <= 0:
                reasons.append("No sell price")

            if reasons:
                results["not_profitable"].append({"asin": asin, "title": kd.get("title", ""), "reasons": reasons})
                results["stats"]["not_profitable_count"] += 1
                continue

            calc = ProfitCalculator.from_keepa_product(kd, buy_price=cost)
            entry = {
                "asin": asin,
                "title": kd.get("title", ""),
                "brand": kd.get("brand", ""),
                "image_url": kd.get("image_url", ""),
                "supplier_cost": cost,
                "amazon_price": kd["sell_price"],
                "bsr": kd["bsr"],
                "monthly_sales_est": kd["monthly_sales_est"],
                "fba_seller_count": kd["fba_seller_count"],
                "is_amazon_seller": kd["is_amazon_seller"],
                "review_count": kd.get("review_count", 0),
                "rating": kd.get("rating", 0),
                "fba_fee": kd.get("fba_fee", 0),
                **calc,
            }

            if calc["roi_pct"] >= min_roi and calc["net_profit"] >= min_profit:
                results["profitable"].append(entry)
                results["stats"]["profitable_count"] += 1
            elif calc["roi_pct"] >= 10 and calc["net_profit"] >= 1.5:
                results["marginal"].append(entry)
                results["stats"]["marginal_count"] += 1
            else:
                results["not_profitable"].append(entry)
                results["stats"]["not_profitable_count"] += 1

            roi_sum += calc["roi_pct"]
            profit_sum += calc["net_profit"]
            valid += 1

            if calc["roi_pct"] > results["stats"]["best_roi"]:
                results["stats"]["best_roi"] = calc["roi_pct"]

        if valid:
            results["stats"]["avg_roi"] = round(roi_sum / valid, 1)
            results["stats"]["avg_profit"] = round(profit_sum / valid, 2)

        results["profitable"].sort(key=lambda x: x["roi_pct"], reverse=True)
        results["stats"]["error_count"] = len(results["errors"])
        return results


scanner = ProductScanner()
