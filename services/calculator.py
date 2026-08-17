"""
Profitability Calculator for Amazon FBA Wholesale.
Uses exact FBA fees from Keepa API when available, falls back to estimates.
"""
from config import REFERRAL_FEES, STORAGE_FEE_STANDARD, STORAGE_FEE_Q4


class ProfitCalculator:
    """Calculate all costs and profits for FBA Wholesale products."""

    @staticmethod
    def calculate(
        sell_price: float,
        buy_price: float,
        weight_lbs: float = 1.0,
        category: str = "other",
        shipping_per_unit: float = 0.50,
        other_costs: float = 0,
        # Keepa-provided exact fees (override estimates)
        keepa_fba_fee: float = None,
        keepa_referral_pct: float = None,
        keepa_referral_fee: float = None,
    ) -> dict:
        """
        Calculate complete profitability analysis.

        If keepa_fba_fee and keepa_referral_pct are provided, uses exact fees.
        Otherwise estimates based on weight and category.
        """
        # Referral fee
        if keepa_referral_fee and keepa_referral_fee > 0:
            referral_fee = keepa_referral_fee
            referral_pct = keepa_referral_pct or 15
        elif keepa_referral_pct and keepa_referral_pct > 0:
            referral_pct = keepa_referral_pct
            referral_fee = max(sell_price * (referral_pct / 100), 0.30)
        else:
            referral_pct = REFERRAL_FEES.get(category.lower(), 15)
            referral_fee = max(sell_price * (referral_pct / 100), 0.30)

        # FBA fee
        if keepa_fba_fee and keepa_fba_fee > 0:
            fba_fee = keepa_fba_fee
        else:
            fba_fee = ProfitCalculator._estimate_fba_fee(weight_lbs)

        # Storage (estimated monthly per unit)
        cubic_feet = weight_lbs * 0.15
        storage_fee = round(cubic_feet * STORAGE_FEE_STANDARD, 2)

        # Inbound placement (average)
        inbound_placement = 0.40

        # Totals
        total_amazon_fees = referral_fee + fba_fee + storage_fee + inbound_placement
        total_product_cost = buy_price + shipping_per_unit + other_costs
        total_expenses = total_product_cost + total_amazon_fees

        net_profit = sell_price - total_expenses
        roi_pct = (net_profit / total_product_cost * 100) if total_product_cost > 0 else 0
        profit_margin_pct = (net_profit / sell_price * 100) if sell_price > 0 else 0

        # Recommendation
        if roi_pct >= 25 and net_profit >= 5:
            recommendation = "BUY"
            rec_color = "green"
        elif roi_pct >= 20 and net_profit >= 3:
            recommendation = "BUY"
            rec_color = "green"
        elif roi_pct >= 10 and net_profit >= 1.5:
            recommendation = "MARGINAL"
            rec_color = "yellow"
        else:
            recommendation = "DO NOT BUY"
            rec_color = "red"

        return {
            "sell_price": round(sell_price, 2),
            "buy_price": round(buy_price, 2),
            "referral_fee": round(referral_fee, 2),
            "referral_fee_pct": round(referral_pct, 1),
            "fba_fee": round(fba_fee, 2),
            "fba_fee_source": "keepa" if (keepa_fba_fee and keepa_fba_fee > 0) else "estimated",
            "storage_fee": round(storage_fee, 2),
            "inbound_placement": round(inbound_placement, 2),
            "total_amazon_fees": round(total_amazon_fees, 2),
            "total_product_cost": round(total_product_cost, 2),
            "total_expenses": round(total_expenses, 2),
            "net_profit": round(net_profit, 2),
            "roi_pct": round(roi_pct, 1),
            "profit_margin_pct": round(profit_margin_pct, 1),
            "recommendation": recommendation,
            "recommendation_color": rec_color,
        }

    @staticmethod
    def _estimate_fba_fee(weight_lbs: float) -> float:
        """Estimate FBA fee when Keepa data is not available."""
        weight_oz = weight_lbs * 16
        if weight_oz <= 6:
            return 3.06
        elif weight_oz <= 8:
            return 4.25
        elif weight_oz <= 12:
            return 4.95
        elif weight_oz <= 16:
            return 5.40
        elif weight_oz <= 24:
            return 5.64
        elif weight_oz <= 32:
            return 5.77
        elif weight_oz <= 48:
            return 6.14
        else:
            return round(6.14 + (weight_lbs - 3) * 0.16, 2)

    @staticmethod
    def from_keepa_product(product: dict, buy_price: float, shipping: float = 0.50) -> dict:
        """Calculate profitability using exact data from a Keepa product object."""
        return ProfitCalculator.calculate(
            sell_price=product.get("sell_price", 0) or product.get("buy_box_price", 0) or product.get("amazon_price", 0),
            buy_price=buy_price,
            weight_lbs=product.get("weight_lbs", 1.0),
            shipping_per_unit=shipping,
            keepa_fba_fee=product.get("fba_fee"),
            keepa_referral_pct=product.get("referral_fee_pct"),
            keepa_referral_fee=product.get("referral_fee"),
        )


calculator = ProfitCalculator()
