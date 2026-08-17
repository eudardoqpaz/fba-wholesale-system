"""
Alert Service - Monitors products and generates alerts for important changes.
"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import Product, PriceHistory, InventoryItem, Alert


class AlertService:
    """Monitor products and create alerts for important changes."""

    PRICE_DROP_THRESHOLD = 0.10     # 10% price drop
    PRICE_INCREASE_THRESHOLD = 0.15  # 15% price increase
    LOW_STOCK_DAYS = 14              # Alert when less than 14 days of stock

    async def check_all_products(self, db: AsyncSession) -> list[dict]:
        """Run all alert checks and return new alerts."""
        alerts = []

        # Get all active products
        result = await db.execute(select(Product).where(Product.status == "active"))
        products = result.scalars().all()

        for product in products:
            new_alerts = await self._check_product(product, db)
            alerts.extend(new_alerts)

        await db.commit()
        return alerts

    async def _check_product(self, product: Product, db: AsyncSession) -> list[dict]:
        """Check a single product for alert conditions."""
        alerts = []

        # Get price history
        result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.product_id == product.id)
            .order_by(PriceHistory.recorded_at.desc())
            .limit(30)
        )
        history = result.scalars().all()

        if len(history) < 2:
            return alerts

        current_price = product.amazon_price
        previous_price = history[1].amazon_price if history[1] else current_price

        # Price drop alert
        if previous_price > 0 and current_price > 0:
            price_change = (current_price - previous_price) / previous_price

            if price_change < -self.PRICE_DROP_THRESHOLD:
                alert = Alert(
                    product_id=product.id,
                    alert_type="price_drop",
                    severity="warning",
                    message=f"Price dropped {abs(price_change)*100:.1f}%: ${previous_price:.2f} -> ${current_price:.2f} for {product.title[:50]}",
                )
                db.add(alert)
                alerts.append({"type": "price_drop", "asin": product.asin, "change": price_change})

            elif price_change > self.PRICE_INCREASE_THRESHOLD:
                alert = Alert(
                    product_id=product.id,
                    alert_type="price_increase",
                    severity="info",
                    message=f"Price increased {price_change*100:.1f}%: ${previous_price:.2f} -> ${current_price:.2f} for {product.title[:50]}",
                )
                db.add(alert)
                alerts.append({"type": "price_increase", "asin": product.asin, "change": price_change})

        # New competitor alert
        if history[1] and product.fba_seller_count > history[1].fba_seller_count + 3:
            alert = Alert(
                product_id=product.id,
                alert_type="new_competitor",
                severity="warning",
                message=f"Seller count increased: {history[1].fba_seller_count} -> {product.fba_seller_count} for {product.title[:50]}",
            )
            db.add(alert)
            alerts.append({"type": "new_competitor", "asin": product.asin})

        # Inventory alerts
        inv_result = await db.execute(
            select(InventoryItem).where(InventoryItem.product_id == product.id)
        )
        inventory = inv_result.scalar_one_or_none()

        if inventory:
            if inventory.quantity_fba <= 0:
                alert = Alert(
                    product_id=product.id,
                    alert_type="out_of_stock",
                    severity="critical",
                    message=f"OUT OF STOCK on Amazon: {product.title[:50]}",
                )
                db.add(alert)
                alerts.append({"type": "out_of_stock", "asin": product.asin})

            elif inventory.days_of_stock > 0 and inventory.days_of_stock < self.LOW_STOCK_DAYS:
                alert = Alert(
                    product_id=product.id,
                    alert_type="low_stock",
                    severity="warning",
                    message=f"Low stock: ~{inventory.days_of_stock} days remaining for {product.title[:50]}",
                )
                db.add(alert)
                alerts.append({"type": "low_stock", "asin": product.asin, "days": inventory.days_of_stock})

        return alerts


alert_service = AlertService()
