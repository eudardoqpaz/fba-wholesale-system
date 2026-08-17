"""
Products Router - CRUD operations for products and profitability analysis.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database import get_db
from models import Product, SupplierProduct, PriceHistory, Supplier
from services.calculator import ProfitCalculator
from services.keepa_api import keepa_service
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class ProductCreate(BaseModel):
    asin: str
    title: Optional[str] = ""
    brand: Optional[str] = ""
    category: Optional[str] = ""
    weight_lbs: Optional[float] = 1.0


class ProductUpdate(BaseModel):
    title: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    weight_lbs: Optional[float] = None
    referral_fee_pct: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("/", response_class=HTMLResponse)
async def products_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Products listing page."""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.supplier_products).selectinload(SupplierProduct.supplier))
        .options(selectinload(Product.inventory_items))
        .where(Product.status != "archived")
        .order_by(Product.created_at.desc())
    )
    products = result.scalars().all()
    return templates.TemplateResponse("products.html", {"request": request, "products": products})


@router.get("/api/list")
async def list_products(
    status: str = "active",
    search: str = "",
    sort_by: str = "roi",
    db: AsyncSession = Depends(get_db),
):
    """API: List all products with optional filters."""
    query = select(Product).options(
        selectinload(Product.supplier_products).selectinload(SupplierProduct.supplier),
        selectinload(Product.inventory_items),
    )

    if status != "all":
        query = query.where(Product.status == status)

    if search:
        query = query.where(
            or_(
                Product.asin.ilike(f"%{search}%"),
                Product.title.ilike(f"%{search}%"),
                Product.brand.ilike(f"%{search}%"),
            )
        )

    result = await db.execute(query)
    products = result.scalars().all()

    # Sort
    if sort_by == "roi":
        products.sort(key=lambda p: p.roi, reverse=True)
    elif sort_by == "profit":
        products.sort(key=lambda p: p.net_profit, reverse=True)
    elif sort_by == "price":
        products.sort(key=lambda p: p.amazon_price, reverse=True)
    elif sort_by == "bsr":
        products.sort(key=lambda p: p.bsr if p.bsr > 0 else 999999999)
    elif sort_by == "newest":
        products.sort(key=lambda p: p.created_at or "", reverse=True)

    return {
        "products": [
            {
                "id": p.id,
                "asin": p.asin,
                "title": p.title,
                "brand": p.brand,
                "category": p.category,
                "image_url": p.image_url,
                "amazon_price": p.amazon_price,
                "best_supplier_price": p.best_supplier_price,
                "bsr": p.bsr,
                "fba_seller_count": p.fba_seller_count,
                "is_amazon_seller": p.is_amazon_seller,
                "monthly_sales_est": p.monthly_sales_est,
                "roi": p.roi,
                "net_profit": p.net_profit,
                "is_profitable": p.is_profitable,
                "referral_fee_pct": p.referral_fee_pct,
                "fba_fee": p.fba_fee,
                "weight_lbs": p.weight_lbs,
                "status": p.status,
                "suppliers": [
                    {"name": sp.supplier.name if sp.supplier else "Unknown", "cost": sp.cost, "sku": sp.supplier_sku}
                    for sp in p.supplier_products
                ],
                "inventory": {
                    "fba": p.inventory_items[0].quantity_fba if p.inventory_items else 0,
                    "inbound": p.inventory_items[0].quantity_inbound if p.inventory_items else 0,
                    "local": p.inventory_items[0].quantity_local if p.inventory_items else 0,
                } if p.inventory_items else None,
            }
            for p in products
        ]
    }


@router.post("/api/add")
async def add_product(data: ProductCreate, db: AsyncSession = Depends(get_db)):
    """Add a product and fetch its Amazon data."""
    # Check if exists
    existing = await db.execute(select(Product).where(Product.asin == data.asin.upper()))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Product already exists")

    # Fetch from Keepa
    keepa_data = await keepa_service.get_product(data.asin.upper())

    product = Product(
        asin=data.asin.upper(),
        title=keepa_data.get("title", data.title) if keepa_data else data.title,
        brand=keepa_data.get("brand", data.brand) if keepa_data else data.brand,
        category=keepa_data.get("category", data.category) if keepa_data else data.category,
        image_url=keepa_data.get("image_url", "") if keepa_data else "",
        amazon_price=keepa_data.get("amazon_price", 0) if keepa_data else 0,
        bsr=keepa_data.get("bsr", 0) if keepa_data else 0,
        fba_seller_count=keepa_data.get("fba_seller_count", 0) if keepa_data else 0,
        is_amazon_seller=keepa_data.get("is_amazon_seller", False) if keepa_data else False,
        monthly_sales_est=keepa_data.get("monthly_sales_est", 0) if keepa_data else 0,
        review_count=keepa_data.get("review_count", 0) if keepa_data else 0,
        rating=keepa_data.get("rating", 0) if keepa_data else 0,
        weight_lbs=keepa_data.get("weight_lbs", data.weight_lbs) if keepa_data else data.weight_lbs,
        keepa_data=keepa_data.get("keepa_data", {}) if keepa_data else {},
    )

    db.add(product)
    await db.commit()
    await db.refresh(product)

    return {"status": "ok", "product_id": product.id, "asin": product.asin}


@router.post("/api/{product_id}/refresh")
async def refresh_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Refresh product data from Keepa."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")

    keepa_data = await keepa_service.get_product(product.asin)
    if keepa_data:
        # Save price history first
        history = PriceHistory(
            product_id=product.id,
            amazon_price=product.amazon_price,
            bsr=product.bsr,
            fba_seller_count=product.fba_seller_count,
        )
        db.add(history)

        # Update product
        product.amazon_price = keepa_data.get("amazon_price", product.amazon_price)
        product.bsr = keepa_data.get("bsr", product.bsr)
        product.fba_seller_count = keepa_data.get("fba_seller_count", product.fba_seller_count)
        product.is_amazon_seller = keepa_data.get("is_amazon_seller", product.is_amazon_seller)
        product.monthly_sales_est = keepa_data.get("monthly_sales_est", product.monthly_sales_est)
        product.keepa_data = keepa_data.get("keepa_data", product.keepa_data)

        await db.commit()
        return {"status": "ok", "updated": True}

    return {"status": "error", "message": "Could not fetch data from Keepa"}


@router.post("/api/{product_id}/calculate")
async def calculate_profit(product_id: int, supplier_cost: float = 0, db: AsyncSession = Depends(get_db)):
    """Calculate profitability for a product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")

    cost = supplier_cost or product.best_supplier_price or 0
    if cost <= 0:
        raise HTTPException(400, "Supplier cost required")

    calc = ProfitCalculator.calculate(
        sell_price=product.amazon_price,
        buy_price=cost,
        weight_lbs=product.weight_lbs,
        category=product.category,
    )
    return calc


@router.delete("/api/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Archive a product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")

    product.status = "archived"
    await db.commit()
    return {"status": "ok"}
