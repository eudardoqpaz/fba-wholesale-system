"""
Inventory Router - Manage FBA inventory, track stock levels, and reorder alerts.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database import get_db
from models import InventoryItem, Product, PurchaseOrder, PurchaseOrderItem, Supplier
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class InventoryUpdate(BaseModel):
    product_id: int
    quantity_fba: Optional[int] = None
    quantity_inbound: Optional[int] = None
    quantity_local: Optional[int] = None
    reorder_point: Optional[int] = None
    reorder_quantity: Optional[int] = None
    avg_cost: Optional[float] = None


class POCreate(BaseModel):
    supplier_id: int
    items: list[dict]  # [{product_id, quantity, unit_cost}]
    notes: Optional[str] = ""


@router.get("/", response_class=HTMLResponse)
async def inventory_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Inventory management page."""
    result = await db.execute(
        select(InventoryItem)
        .options(selectinload(InventoryItem.product))
        .order_by(InventoryItem.updated_at.desc())
    )
    items = result.scalars().all()

    # Get products without inventory records
    products_result = await db.execute(select(Product).where(Product.status == "active"))
    products = products_result.scalars().all()
    products_with_inv = {item.product_id for item in items}
    products_no_inv = [p for p in products if p.id not in products_with_inv]

    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "items": items,
        "products_no_inv": products_no_inv,
    })


@router.get("/api/list")
async def list_inventory(db: AsyncSession = Depends(get_db)):
    """API: Get all inventory items."""
    result = await db.execute(
        select(InventoryItem).options(selectinload(InventoryItem.product))
    )
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "asin": i.product.asin if i.product else "",
                "title": i.product.title if i.product else "",
                "amazon_price": i.product.amazon_price if i.product else 0,
                "quantity_fba": i.quantity_fba,
                "quantity_inbound": i.quantity_inbound,
                "quantity_local": i.quantity_local,
                "reorder_point": i.reorder_point,
                "reorder_quantity": i.reorder_quantity,
                "avg_cost": i.avg_cost,
                "total_invested": i.total_invested,
                "days_of_stock": i.days_of_stock,
                "status": i.status,
            }
            for i in items
        ]
    }


@router.post("/api/update")
async def update_inventory(data: InventoryUpdate, db: AsyncSession = Depends(get_db)):
    """Update inventory for a product."""
    result = await db.execute(
        select(InventoryItem).where(InventoryItem.product_id == data.product_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        # Create new inventory record
        item = InventoryItem(product_id=data.product_id)
        db.add(item)

    if data.quantity_fba is not None:
        item.quantity_fba = data.quantity_fba
    if data.quantity_inbound is not None:
        item.quantity_inbound = data.quantity_inbound
    if data.quantity_local is not None:
        item.quantity_local = data.quantity_local
    if data.reorder_point is not None:
        item.reorder_point = data.reorder_point
    if data.reorder_quantity is not None:
        item.reorder_quantity = data.reorder_quantity
    if data.avg_cost is not None:
        item.avg_cost = data.avg_cost
        item.total_invested = (item.quantity_fba + item.quantity_inbound + item.quantity_local) * data.avg_cost

    # Update status
    if item.quantity_fba <= 0:
        item.status = "out_of_stock"
    elif item.quantity_fba <= item.reorder_point:
        item.status = "low_stock"
    elif item.quantity_fba > item.reorder_quantity * 3:
        item.status = "overstock"
    else:
        item.status = "in_stock"

    await db.commit()
    return {"status": "ok", "new_status": item.status}


@router.post("/api/po/create")
async def create_purchase_order(data: POCreate, db: AsyncSession = Depends(get_db)):
    """Create a new purchase order."""
    # Generate PO number
    count_result = await db.execute(select(PurchaseOrder))
    po_count = len(count_result.scalars().all())
    po_number = f"PO-{po_count + 1:04d}"

    total = sum(item["quantity"] * item["unit_cost"] for item in data.items)

    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=data.supplier_id,
        total_amount=total,
        items_count=len(data.items),
        notes=data.notes or "",
    )
    db.add(po)
    await db.flush()

    for item_data in data.items:
        po_item = PurchaseOrderItem(
            po_id=po.id,
            product_id=item_data["product_id"],
            quantity=item_data["quantity"],
            unit_cost=item_data["unit_cost"],
            total_cost=item_data["quantity"] * item_data["unit_cost"],
        )
        db.add(po_item)

    await db.commit()
    return {"status": "ok", "po_number": po_number, "po_id": po.id}


@router.get("/api/po/list")
async def list_purchase_orders(db: AsyncSession = Depends(get_db)):
    """List all purchase orders."""
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.supplier))
        .options(selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.product))
        .order_by(PurchaseOrder.created_at.desc())
    )
    pos = result.scalars().all()
    return {
        "purchase_orders": [
            {
                "id": po.id,
                "po_number": po.po_number,
                "supplier": po.supplier.name if po.supplier else "Unknown",
                "status": po.status,
                "total_amount": po.total_amount,
                "items_count": po.items_count,
                "order_date": po.order_date.isoformat() if po.order_date else None,
                "expected_date": po.expected_date.isoformat() if po.expected_date else None,
                "items": [
                    {
                        "product_id": item.product_id,
                        "asin": item.product.asin if item.product else "",
                        "title": item.product.title[:50] if item.product else "",
                        "quantity": item.quantity,
                        "unit_cost": item.unit_cost,
                        "total_cost": item.total_cost,
                    }
                    for item in po.items
                ],
            }
            for po in pos
        ]
    }


@router.post("/api/reorder-check")
async def check_reorder(db: AsyncSession = Depends(get_db)):
    """Check which products need reordering."""
    result = await db.execute(
        select(InventoryItem).options(selectinload(InventoryItem.product))
    )
    items = result.scalars().all()

    reorder_needed = []
    for item in items:
        if item.quantity_fba <= item.reorder_point and item.product:
            reorder_needed.append({
                "product_id": item.product_id,
                "asin": item.product.asin,
                "title": item.product.title[:60],
                "current_stock": item.quantity_fba,
                "reorder_point": item.reorder_point,
                "suggested_order": item.reorder_quantity,
                "best_supplier_price": item.product.best_supplier_price,
                "estimated_cost": (item.product.best_supplier_price or 0) * item.reorder_quantity,
            })

    return {
        "reorder_needed": sorted(reorder_needed, key=lambda x: x["current_stock"]),
        "total_items": len(reorder_needed),
        "estimated_total_cost": sum(r["estimated_cost"] for r in reorder_needed),
    }
