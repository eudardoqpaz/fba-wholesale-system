"""
Report Service - Generates automated business reports.
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models import Product, InventoryItem, PurchaseOrder, PriceHistory, Alert


class ReportService:
    """Generate business reports for the FBA Wholesale operation."""

    async def generate_daily_report(self, db: AsyncSession) -> dict:
        """Generate a daily business summary."""
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Active products count
        products_result = await db.execute(
            select(func.count(Product.id)).where(Product.status == "active")
        )
        total_products = products_result.scalar() or 0

        # Profitable products
        profitable_result = await db.execute(select(Product).where(Product.status == "active"))
        products = profitable_result.scalars().all()
        profitable_count = sum(1 for p in products if p.is_profitable)

        # Inventory summary
        inv_result = await db.execute(select(InventoryItem))
        inventory_items = inv_result.scalars().all()

        total_fba_units = sum(i.quantity_fba for i in inventory_items)
        total_invested = sum(i.total_invested for i in inventory_items)
        low_stock_count = sum(1 for i in inventory_items if i.status == "low_stock")
        out_of_stock_count = sum(1 for i in inventory_items if i.status == "out_of_stock")

        # Recent alerts
        alerts_result = await db.execute(
            select(Alert)
            .where(Alert.created_at >= today)
            .order_by(Alert.created_at.desc())
            .limit(10)
        )
        recent_alerts = alerts_result.scalars().all()

        # Open POs
        po_result = await db.execute(
            select(func.count(PurchaseOrder.id))
            .where(PurchaseOrder.status.in_(["draft", "submitted"]))
        )
        open_pos = po_result.scalar() or 0

        # Products needing reorder
        reorder_list = []
        for item in inventory_items:
            if item.quantity_fba <= item.reorder_point and item.quantity_fba > 0:
                product = next((p for p in products if p.id == item.product_id), None)
                if product:
                    reorder_list.append({
                        "asin": product.asin,
                        "title": product.title[:60],
                        "current_stock": item.quantity_fba,
                        "reorder_point": item.reorder_point,
                        "reorder_qty": item.reorder_quantity,
                        "days_of_stock": item.days_of_stock,
                    })

        return {
            "report_type": "daily",
            "generated_at": now.isoformat(),
            "summary": {
                "total_active_products": total_products,
                "profitable_products": profitable_count,
                "total_fba_units": total_fba_units,
                "total_invested": round(total_invested, 2),
                "low_stock_alerts": low_stock_count,
                "out_of_stock_alerts": out_of_stock_count,
                "open_purchase_orders": open_pos,
            },
            "reorder_needed": reorder_list,
            "recent_alerts": [
                {
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "time": a.created_at.isoformat() if a.created_at else "",
                }
                for a in recent_alerts
            ],
        }

    async def generate_weekly_report(self, db: AsyncSession) -> dict:
        """Generate a weekly business report."""
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        # Get products with price changes this week
        price_changes_result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.recorded_at >= week_ago)
            .order_by(PriceHistory.recorded_at.desc())
        )
        price_changes = price_changes_result.scalars().all()

        # Group by product
        changes_by_product = {}
        for pc in price_changes:
            if pc.product_id not in changes_by_product:
                changes_by_product[pc.product_id] = []
            changes_by_product[pc.product_id].append(pc)

        # Identify significant movers
        significant_movers = []
        for product_id, changes in changes_by_product.items():
            if len(changes) >= 2:
                first_price = changes[-1].amazon_price
                last_price = changes[0].amazon_price
                if first_price > 0:
                    pct_change = (last_price - first_price) / first_price
                    if abs(pct_change) > 0.05:
                        product_result = await db.execute(select(Product).where(Product.id == product_id))
                        product = product_result.scalar_one_or_none()
                        if product:
                            significant_movers.append({
                                "asin": product.asin,
                                "title": product.title[:60],
                                "price_change_pct": round(pct_change * 100, 1),
                                "from_price": first_price,
                                "to_price": last_price,
                            })

        # POs received this week
        pos_result = await db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.received_date >= week_ago)
            .where(PurchaseOrder.status == "received")
        )
        received_pos = pos_result.scalars().all()

        return {
            "report_type": "weekly",
            "generated_at": now.isoformat(),
            "period": f"{week_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
            "significant_price_movers": significant_movers[:20],
            "pos_received": [
                {"po_number": po.po_number, "total": po.total_amount}
                for po in received_pos
            ],
        }


report_service = ReportService()
