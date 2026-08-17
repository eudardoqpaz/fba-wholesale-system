"""
Scanner Router - Upload price lists AND search Keepa's Product Finder.
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Supplier, ScanResult, Product
from services.scanner import scanner
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class FinderQuery(BaseModel):
    root_category: Optional[int] = None
    min_price: float = 15
    max_price: float = 100
    max_bsr: int = 50000
    max_fba_sellers: int = 15
    min_monthly_sales: int = 30
    min_reviews: int = 50
    exclude_amazon: bool = True
    sort_by: str = "bsr"
    max_results: int = 50


@router.get("/", response_class=HTMLResponse)
async def scanner_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Scanner page with both CSV upload and Product Finder."""
    result = await db.execute(select(Supplier).where(Supplier.status == "active"))
    suppliers = result.scalars().all()

    scans_result = await db.execute(select(ScanResult).order_by(ScanResult.created_at.desc()).limit(10))
    recent_scans = scans_result.scalars().all()

    # Common US categories for the finder
    categories = [
        {"id": 1055398, "name": "Home & Kitchen"},
        {"id": 165796011, "name": "Tools & Home Improvement"},
        {"id": 2619533011, "name": "Sports & Outdoors"},
        {"id": 283155, "name": "Books"},
        {"id": 3760911, "name": "Health & Household"},
        {"id": 16310101, "name": "Beauty & Personal Care"},
        {"id": 2617941011, "name": "Toys & Games"},
        {"id": 3375251, "name": "Pet Supplies"},
        {"id": 2238192011, "name": "Office Products"},
        {"id": 15684181, "name": "Baby Products"},
        {"id": 172282, "name": "Electronics"},
        {"id": 281052, "name": "Camera & Photo"},
        {"id": 599676, "name": "Automotive"},
        {"id": 11091801, "name": "Grocery & Gourmet Food"},
        {"id": 3375301, "name": "Patio, Lawn & Garden"},
    ]

    return templates.TemplateResponse("scanner.html", {
        "request": request,
        "suppliers": suppliers,
        "recent_scans": recent_scans,
        "categories": categories,
    })


# ─── CSV Price List Scan ───

@router.post("/api/scan")
async def scan_price_list(
    file: UploadFile = File(...),
    supplier_id: Optional[int] = Form(None),
    min_roi: float = Form(15),
    min_profit: float = Form(2.50),
    max_sellers: int = Form(25),
    max_bsr: int = Form(100000),
    keep_amazon_sellers: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    """Upload CSV and scan against Amazon data."""
    if not file.filename.endswith((".csv", ".CSV")):
        raise HTTPException(400, "Only CSV files supported")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    price_list = scanner.parse_csv_price_list(text)
    if not price_list:
        raise HTTPException(400, "No valid products found. CSV needs ASIN and Cost columns.")

    results = await scanner.scan_price_list(price_list, min_roi, min_profit, max_sellers, max_bsr, keep_amazon_sellers)

    scan_record = ScanResult(
        scan_name=file.filename,
        supplier_id=supplier_id,
        total_products_scanned=results["stats"]["total_scanned"],
        profitable_found=results["stats"]["profitable_count"],
        marginal_found=results["stats"]["marginal_count"],
        not_profitable=results["stats"]["not_profitable_count"],
        avg_roi=results["stats"]["avg_roi"],
        scan_data=results["profitable"][:100],
    )
    db.add(scan_record)
    await db.commit()

    return results


# ─── Keepa Product Finder ───

@router.post("/api/finder")
async def product_finder(query: FinderQuery):
    """Search Keepa's Product Finder for profitable wholesale products."""
    results = await scanner.search_keepa_finder(
        root_category=query.root_category,
        min_price=query.min_price,
        max_price=query.max_price,
        max_bsr=query.max_bsr,
        max_fba_sellers=query.max_fba_sellers,
        min_monthly_sales=query.min_monthly_sales,
        min_reviews=query.min_reviews,
        exclude_amazon=query.exclude_amazon,
        sort_by=query.sort_by,
        max_results=query.max_results,
    )
    return results


# ─── Best Sellers Explorer ───

@router.get("/api/bestsellers/{category}")
async def best_sellers(category: str | int, limit: int = 50):
    """Get best sellers for a category."""
    results = await scanner.get_category_best_sellers(category, limit)
    return results


# ─── Add profitable scan results to products ───

@router.post("/api/add-to-products")
async def add_to_products(asins: list[str], db: AsyncSession = Depends(get_db)):
    """Add products from scan/finder to main product list."""
    from services.keepa_api import keepa_service
    added = 0
    for asin in asins:
        existing = await db.execute(select(Product).where(Product.asin == asin.upper()))
        if existing.scalar_one_or_none():
            continue

        kd = await keepa_service.get_product(asin.upper())
        if not kd:
            continue

        product = Product(
            asin=kd["asin"],
            title=kd.get("title", ""),
            brand=kd.get("brand", ""),
            category=kd.get("category", ""),
            image_url=kd.get("image_url", ""),
            amazon_price=kd.get("sell_price", 0),
            bsr=kd.get("bsr", 0),
            fba_seller_count=kd.get("fba_seller_count", 0),
            is_amazon_seller=kd.get("is_amazon_seller", False),
            monthly_sales_est=kd.get("monthly_sales_est", 0),
            review_count=kd.get("review_count", 0),
            rating=kd.get("rating", 0),
            weight_lbs=kd.get("weight_lbs", 0),
            referral_fee_pct=kd.get("referral_fee_pct", 15),
            fba_fee=kd.get("fba_fee", 0),
            keepa_data=kd.get("stats", {}),
        )
        db.add(product)
        added += 1

    await db.commit()
    return {"status": "ok", "added": added}
