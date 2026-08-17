"""
Auto-Discovery Service - AI-powered product discovery.
The system finds profitable products and tells the user EXACTLY what to buy.
"""
from services.keepa_api import keepa_service
from services.calculator import ProfitCalculator
from services.scanner import scanner


class AutoDiscovery:
    """
    Automatically discovers profitable products for wholesale.
    Instead of giving tools, it gives ANSWERS: "Buy this, here, for this much."
    """

    # Conservative criteria for beginners (minimize risk)
    BEGINNER_CRITERIA = {
        "min_price": 15,
        "max_price": 60,
        "max_bsr": 30000,
        "max_fba_sellers": 12,
        "min_monthly_sales": 50,
        "min_reviews": 100,
        "min_rating": 4.0,
        "exclude_amazon": True,
        "min_roi": 25,
        "min_profit": 4.0,
        "max_investment_per_product": 300,
    }

    async def find_products(
        self,
        budget: float = 1000,
        risk_level: str = "conservative",
        categories: list[str] = None,
    ) -> dict:
        """
        Find profitable products based on budget and risk tolerance.
        
        Args:
            budget: Total budget to invest
            risk_level: "conservative", "moderate", or "aggressive"
            categories: List of category names to search (default: best beginner categories)
        
        Returns:
            Shopping list with exact products, quantities, costs, and expected returns.
        """
        # Adjust criteria based on risk level
        criteria = self._get_criteria(risk_level)

        # Default categories for beginners
        if not categories:
            categories = ["home", "toys", "health", "pet", "baby"]

        # Category IDs for Keepa Product Finder
        category_map = {
            "home": 1055398,        # Home & Kitchen
            "toys": 165796011,      # Toys & Games
            "health": 3760911,      # Health & Household
            "pet": 3375251,         # Pet Supplies
            "baby": 15684181,       # Baby Products
            "sports": 3375301,      # Sports & Outdoors
            "beauty": 3760901,      # Beauty
            "office": 1064954,      # Office Products
            "tools": 2238192011,    # Tools & Home Improvement
        }

        all_products = []

        # Search each category
        for cat_name in categories:
            cat_id = category_map.get(cat_name)
            if not cat_id:
                continue

            result = await scanner.search_keepa_finder(
                root_category=cat_id,
                min_price=criteria["min_price"],
                max_price=criteria["max_price"],
                max_bsr=criteria["max_bsr"],
                max_fba_sellers=criteria["max_fba_sellers"],
                min_monthly_sales=criteria["min_monthly_sales"],
                min_reviews=criteria["min_reviews"],
                exclude_amazon=criteria["exclude_amazon"],
                sort_by="bsr",
                max_results=30,
            )

            if result.get("error"):
                continue

            for p in result.get("products", []):
                # Calculate with estimated wholesale cost (typically 40-60% of Amazon price)
                estimated_cost = p.get("sell_price", 0) * 0.55  # Conservative: 55% of retail
                calc = ProfitCalculator.from_keepa_product(p, buy_price=estimated_cost)

                if calc["roi_pct"] >= criteria["min_roi"] and calc["net_profit"] >= criteria["min_profit"]:
                    all_products.append({
                        **p,
                        "estimated_wholesale_cost": round(estimated_cost, 2),
                        "calc": calc,
                        "category_searched": cat_name,
                        "risk_score": self._calculate_risk(p),
                    })

        # Sort by best opportunity (combination of ROI, low risk, good sales)
        all_products.sort(key=lambda x: (
            x["calc"]["roi_pct"] * 0.4 +
            (100 - x["risk_score"]) * 0.3 +
            min(x.get("monthly_sales_est", 0) / 10, 100) * 0.3
        ), reverse=True)

        # Build shopping list within budget
        shopping_list = self._build_shopping_list(all_products, budget, criteria)

        return {
            "shopping_list": shopping_list,
            "total_products": len(shopping_list),
            "total_investment": sum(item["total_cost"] for item in shopping_list),
            "expected_revenue": sum(item["expected_revenue"] for item in shopping_list),
            "expected_profit": sum(item["expected_profit"] for item in shopping_list),
            "expected_roi": round(
                sum(item["expected_profit"] for item in shopping_list) /
                max(sum(item["total_cost"] for item in shopping_list), 1) * 100, 1
            ),
            "risk_level": risk_level,
            "budget_used": round(sum(item["total_cost"] for item in shopping_list) / budget * 100, 1),
            "all_candidates": len(all_products),
            "criteria_used": criteria,
        }

    def _get_criteria(self, risk_level: str) -> dict:
        """Get search criteria based on risk tolerance."""
        base = self.BEGINNER_CRITERIA.copy()

        if risk_level == "conservative":
            return base
        elif risk_level == "moderate":
            base["max_bsr"] = 50000
            base["max_fba_sellers"] = 18
            base["min_roi"] = 20
            base["min_profit"] = 3.0
            base["max_investment_per_product"] = 500
            return base
        elif risk_level == "aggressive":
            base["max_bsr"] = 80000
            base["max_fba_sellers"] = 25
            base["min_roi"] = 15
            base["min_profit"] = 2.0
            base["max_price"] = 100
            base["max_investment_per_product"] = 800
            return base
        return base

    def _calculate_risk(self, product: dict) -> int:
        """Calculate risk score 0-100 (lower = less risky)."""
        risk = 0

        # BSR risk
        bsr = product.get("bsr", 0)
        if bsr > 50000:
            risk += 25
        elif bsr > 20000:
            risk += 15
        elif bsr > 10000:
            risk += 5

        # Competition risk
        sellers = product.get("fba_seller_count", 0)
        if sellers > 20:
            risk += 25
        elif sellers > 15:
            risk += 15
        elif sellers > 10:
            risk += 5

        # Amazon competition
        if product.get("is_amazon_seller"):
            risk += 30

        # Review risk (few reviews = less proven product)
        reviews = product.get("review_count", 0)
        if reviews < 50:
            risk += 15
        elif reviews < 100:
            risk += 10

        # Rating risk
        rating = product.get("rating", 0)
        if rating > 0 and rating < 4.0:
            risk += 20
        elif rating > 0 and rating < 4.3:
            risk += 10

        return min(risk, 100)

    def _build_shopping_list(self, products: list, budget: float, criteria: dict) -> list:
        """Build a shopping list within the budget."""
        shopping_list = []
        remaining_budget = budget
        max_per_product = criteria["max_investment_per_product"]

        for product in products[:20]:  # Top 20 candidates
            if remaining_budget <= 0:
                break

            wholesale_cost = product["estimated_wholesale_cost"]
            if wholesale_cost <= 0:
                continue

            # How many can we buy?
            max_qty_by_budget = int(remaining_budget / wholesale_cost)
            max_qty_by_limit = int(max_per_product / wholesale_cost)
            qty = min(max_qty_by_budget, max_qty_by_limit, 30)  # Max 30 units per product

            if qty < 5:  # Minimum viable order
                continue

            total_cost = round(qty * wholesale_cost, 2)
            expected_revenue = round(qty * product.get("sell_price", 0), 2)
            expected_profit = round(qty * product["calc"]["net_profit"], 2)

            shopping_list.append({
                "asin": product.get("asin", ""),
                "title": product.get("title", "")[:80],
                "brand": product.get("brand", ""),
                "category": product.get("category_searched", ""),
                "amazon_price": product.get("sell_price", 0),
                "estimated_wholesale_cost": wholesale_cost,
                "quantity": qty,
                "total_cost": total_cost,
                "expected_revenue": expected_revenue,
                "expected_profit": expected_profit,
                "roi_pct": product["calc"]["roi_pct"],
                "bsr": product.get("bsr", 0),
                "monthly_sales": product.get("monthly_sales_est", 0),
                "sellers": product.get("fba_seller_count", 0),
                "risk_score": product.get("risk_score", 50),
                "image_url": product.get("image_url", ""),
                "notes": self._get_product_notes(product),
            })

            remaining_budget -= total_cost

        return shopping_list

    def _get_product_notes(self, product: dict) -> str:
        """Generate notes/recommendations for a product."""
        notes = []

        if product.get("monthly_sales_est", 0) >= 200:
            notes.append("Alta demanda - se vende rapido")
        if product.get("fba_seller_count", 99) <= 5:
            notes.append("Poca competencia")
        if product.get("bsr", 999999) <= 5000:
            notes.append("Top seller en su categoria")
        if product.get("rating", 0) >= 4.5:
            notes.append("Excelente rating")
        if product.get("review_count", 0) >= 500:
            notes.append("Producto bien establecido")

        return " | ".join(notes) if notes else "Producto viable"


auto_discovery = AutoDiscovery()
