"""
Dashboard Router - Main dashboard views and API endpoints.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Product, InventoryItem, Supplier, PurchaseOrder, Alert, ScanResult
from services.reports import report_service

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Main dashboard page."""
    # Products stats
    products_result = await db.execute(select(Product).where(Product.status == "active"))
    products = products_result.scalars().all()
    total_products = len(products)
    profitable_count = sum(1 for p in products if p.is_profitable)

    # Inventory stats
    inv_result = await db.execute(select(InventoryItem))
    inventory_items = inv_result.scalars().all()
    total_fba_units = sum(i.quantity_fba for i in inventory_items)
    total_invested = sum(i.total_invested for i in inventory_items)
    low_stock = sum(1 for i in inventory_items if i.status == "low_stock")
    out_of_stock = sum(1 for i in inventory_items if i.status == "out_of_stock")

    # Suppliers
    supp_result = await db.execute(select(func.count(Supplier.id)).where(Supplier.status == "active"))
    active_suppliers = supp_result.scalar() or 0

    # Open POs
    po_result = await db.execute(
        select(func.count(PurchaseOrder.id)).where(PurchaseOrder.status.in_(["draft", "submitted"]))
    )
    open_pos = po_result.scalar() or 0

    # Recent alerts
    alerts_result = await db.execute(
        select(Alert).where(Alert.is_read == False).order_by(Alert.created_at.desc()).limit(10)
    )
    alerts = alerts_result.scalars().all()

    # Top profitable products
    top_products = sorted(products, key=lambda p: p.roi, reverse=True)[:10]

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_products": total_products,
        "profitable_count": profitable_count,
        "total_fba_units": total_fba_units,
        "total_invested": round(total_invested, 2),
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "active_suppliers": active_suppliers,
        "open_pos": open_pos,
        "alerts": alerts,
        "top_products": top_products,
    })


@router.get("/api/report/daily")
async def daily_report(db: AsyncSession = Depends(get_db)):
    """Get daily report data."""
    return await report_service.generate_daily_report(db)


@router.get("/api/report/weekly")
async def weekly_report(db: AsyncSession = Depends(get_db)):
    """Get weekly report data."""
    return await report_service.generate_weekly_report(db)
