"""
Scanner Router - Upload price lists, search Keepa, export to Excel, AI analysis, store search.
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Supplier, ScanResult, Product
from services.scanner import scanner
from services.scraper import scraper
from services.calculator import ProfitCalculator
from services.excel_export import generate_scan_results_excel, generate_shopping_list_excel
from services.eligibility import eligibility_service
from pydantic import BaseModel
from typing import Optional
import io
import csv

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


class AISelectQuery(BaseModel):
    products: list[dict]
    budget: float = 500
    max_products: int = 10


class StoreSearchQuery(BaseModel):
    products: list[dict]  # List of products with title, brand, asin


@router.get("/", response_class=HTMLResponse)
async def scanner_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Scanner page with both CSV upload and Product Finder."""
    from services.eligibility import eligibility_service, AMAZON_CATEGORIES

    result = await db.execute(select(Supplier).where(Supplier.status == "active"))
    suppliers = result.scalars().all()

    scans_result = await db.execute(select(ScanResult).order_by(ScanResult.created_at.desc()).limit(10))
    recent_scans = scans_result.scalars().all()

    # Get approved categories from settings
    approved_cats = await eligibility_service.get_approved_categories(db)

    # Map eligibility category IDs to Keepa category IDs
    eligibility_to_keepa = {
        "home_kitchen": {"id": 1055398, "name": "Home & Kitchen"},
        "tools_home_improvement": {"id": 165796011, "name": "Tools & Home Improvement"},
        "sports_outdoors": {"id": 2619533011, "name": "Sports & Outdoors"},
        "health_household": {"id": 3760911, "name": "Health & Household"},
        "beauty": {"id": 16310101, "name": "Beauty & Personal Care"},
        "toys_games": {"id": 2617941011, "name": "Toys & Games"},
        "pet_supplies": {"id": 3375251, "name": "Pet Supplies"},
        "office_products": {"id": 2238192011, "name": "Office Products"},
        "baby": {"id": 15684181, "name": "Baby Products"},
        "electronics": {"id": 172282, "name": "Electronics"},
        "automotive": {"id": 599676, "name": "Automotive"},
        "grocery": {"id": 11091801, "name": "Grocery & Gourmet Food"},
        "clothing": {"id": 15684181, "name": "Clothing & Accessories"},
        "computers": {"id": 172282, "name": "Computers"},
        "industrial": {"id": 1064954, "name": "Industrial & Scientific"},
        "musical_instruments": {"id": 119667011, "name": "Musical Instruments"},
    }

    # Only show categories that are approved
    categories = []
    for cat_id in approved_cats:
        if cat_id in eligibility_to_keepa:
            categories.append(eligibility_to_keepa[cat_id])

    # If no categories configured, show all open ones
    if not categories:
        categories = [
            {"id": 1055398, "name": "Home & Kitchen"},
            {"id": 165796011, "name": "Tools & Home Improvement"},
            {"id": 2619533011, "name": "Sports & Outdoors"},
            {"id": 3375251, "name": "Pet Supplies"},
            {"id": 2238192011, "name": "Office Products"},
            {"id": 172282, "name": "Electronics"},
            {"id": 599676, "name": "Automotive"},
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
    check_restrictions: bool = Form(False),
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

    results = await scanner.scan_price_list(price_list, min_roi, min_profit, max_sellers, max_bsr, keep_amazon_sellers, check_restrictions)

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


# ─── Export to Excel/CSV ───

@router.post("/api/export")
async def export_to_csv(data: dict):
    """Export scan results to CSV file."""
    products = data.get("products", [])
    if not products:
        raise HTTPException(400, "No products to export")

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ASIN", "Titulo", "Marca", "Precio Amazon", "Costo Proveedor",
        "FBA Fee", "Referral Fee", "Ganancia Neta", "ROI %", "BSR",
        "Sellers FBA", "Ventas/mes", "Reviews", "Rating", "Recomendacion",
        "Link Amazon"
    ])

    # Data
    for p in products:
        calc = p.get("calc", {})
        writer.writerow([
            p.get("asin", ""),
            p.get("title", "")[:80],
            p.get("brand", ""),
            f"${p.get('amazon_price', 0):.2f}",
            f"${p.get('supplier_cost', 0):.2f}",
            f"${p.get('fba_fee', 0):.2f}",
            f"${calc.get('referral_fee', 0):.2f}",
            f"${calc.get('net_profit', 0):.2f}",
            f"{calc.get('roi_pct', 0)}%",
            p.get("bsr", ""),
            p.get("fba_seller_count", ""),
            p.get("monthly_sales_est", ""),
            p.get("review_count", ""),
            p.get("rating", ""),
            calc.get("recommendation", ""),
            f"https://www.amazon.com/dp/{p.get('asin', '')}",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fba_productos.csv"}
    )


# ─── AI Select Best Products ───

@router.post("/api/ai-select")
async def ai_select_best(query: AISelectQuery, db: AsyncSession = Depends(get_db)):
    """AI analyzes all products and selects the best ones within budget."""
    products = query.products
    budget = query.budget
    max_products = query.max_products

    # Filter by eligibility - remove restricted categories
    approved_products, restricted_products = await eligibility_service.filter_approved_products(products, db)

    # Debug counters
    debug = {
        "total_products": len(products),
        "restricted_category": len(restricted_products),
        "no_price": 0,
        "low_volume": 0,
        "low_profit": 0,
        "passed_filters": 0,
    }

    # Only process approved products
    products = approved_products

    # Minimum thresholds
    MIN_MONTHLY_SALES = 100  # Lowered to include more products
    MIN_PROFIT = 1.50        # Lowered minimum profit
    MIN_PRICE = 10.00        # Minimum sell price

    # Calculate profitability for each product
    analyzed = []
    for p in products:
        # Get sell price - try ALL possible field names
        sell_price = (
            p.get("sell_price", 0) or
            p.get("amazon_price", 0) or
            p.get("price", 0) or
            0
        )

        # Debug: count products with no price
        if sell_price < MIN_PRICE:
            debug["no_price"] += 1
            continue

        # Get monthly sales
        monthly_sales = (
            p.get("monthly_sales_est", 0) or
            p.get("monthly_sales", 0) or
            p.get("sales_monthly", 0) or
            0
        )

        # Debug: count low volume products
        if monthly_sales < MIN_MONTHLY_SALES:
            debug["low_volume"] += 1
            continue

        # Get supplier cost (estimate if not provided)
        supplier_cost = p.get("supplier_cost", 0) or (sell_price * 0.55)

        # Get FBA fee from product data
        fba_fee = p.get("fba_fee", 0) or 0

        # Calculate profitability
        calc = ProfitCalculator.calculate(
            sell_price=sell_price,
            buy_price=supplier_cost,
            weight_lbs=p.get("weight_lbs", 1.0),
            keepa_fba_fee=fba_fee if fba_fee > 0 else None,
            keepa_referral_pct=p.get("referral_fee_pct"),
        )

        roi = calc.get("roi_pct", 0)
        profit = calc.get("net_profit", 0)

        # Debug: count low profit products
        if profit < MIN_PROFIT:
            debug["low_profit"] += 1
            continue

        debug["passed_filters"] += 1

        sellers = p.get("fba_seller_count", 99) or 99
        bsr = p.get("bsr", 999999) or 999999
        is_amazon = p.get("is_amazon_seller", False)

        # SCORING - Volume is KING
        score = 0

        # VOLUME (0-40 points)
        if monthly_sales >= 10000:
            score += 40
        elif monthly_sales >= 5000:
            score += 32
        elif monthly_sales >= 2000:
            score += 24
        elif monthly_sales >= 1000:
            score += 20
        elif monthly_sales >= 500:
            score += 12
        elif monthly_sales >= 300:
            score += 8
        elif monthly_sales >= 100:
            score += 4

        # ROI (0-20 points)
        if roi >= 30:
            score += 20
        elif roi >= 25:
            score += 16
        elif roi >= 20:
            score += 12
        elif roi >= 15:
            score += 8

        # PROFIT (0-10 points)
        if profit >= 8:
            score += 10
        elif profit >= 5:
            score += 8
        elif profit >= 3:
            score += 5
        elif profit >= 2:
            score += 2

        # COMPETITION (0-30 points) - NOW MUCH MORE IMPORTANT!
        if sellers <= 1:
            score += 30  # MONOPOLY - best case
        elif sellers <= 2:
            score += 25
        elif sellers <= 3:
            score += 20
        elif sellers <= 5:
            score += 12
        elif sellers <= 8:
            score += 5
        elif sellers <= 10:
            score += 0
        elif sellers <= 15:
            score -= 10  # Penalty for high competition
        else:
            score -= 20  # Big penalty

        # PENALTIES
        if is_amazon:
            score -= 50  # NEVER compete with Amazon
        if bsr > 50000:
            score -= 10

        # Risk
        risk = "BAJO"
        if is_amazon or sellers > 15 or bsr > 50000:
            risk = "ALTO"
        elif sellers > 5 or bsr > 20000 or monthly_sales < 500:
            risk = "MEDIO"

        analyzed.append({
            **p,
            "sell_price": sell_price,
            "amazon_price": sell_price,
            "supplier_cost_estimated": round(supplier_cost, 2),
            "calc": calc,
            "score": score,
            "risk": risk,
            "priority_reasons": _get_priority_reasons(roi, profit, monthly_sales, sellers, is_amazon),
        })

    # Sort by score
    analyzed.sort(key=lambda x: x["score"], reverse=True)

    # Select top products within budget
    selected = []
    remaining = budget
    for p in analyzed[:max_products * 3]:
        cost = p.get("supplier_cost_estimated", 0)
        if cost <= 0:
            continue

        qty = min(int(remaining / cost), 30)
        if qty < 3:
            continue

        total_cost = round(qty * cost, 2)
        if total_cost > remaining:
            continue

        p["recommended_qty"] = qty
        p["total_cost"] = total_cost
        p["expected_profit"] = round(qty * p["calc"]["net_profit"], 2)
        selected.append(p)
        remaining -= total_cost

        if len(selected) >= max_products:
            break

    return {
        "selected": selected,
        "total_investment": round(budget - remaining, 2),
        "expected_profit": round(sum(p["expected_profit"] for p in selected), 2),
        "expected_roi": round(
            sum(p["expected_profit"] for p in selected) / max(budget - remaining, 1) * 100, 1
        ),
        "total_candidates": len(analyzed),
        "budget_used_pct": round((budget - remaining) / budget * 100, 1),
        "debug": debug,  # Show what happened
        "restricted_products": [
            {"asin": p.get("asin"), "title": p.get("title", "")[:60], "category": p.get("_category_name", "")}
            for p in restricted_products[:10]
        ],
    }


def _get_priority_reasons(roi, profit, sales, sellers, is_amazon):
    """Generate reasons why a product is prioritized."""
    reasons = []
    if sales >= 5000:
        reasons.append(f"ALTA demanda ({sales:,}/mes)")
    elif sales >= 1000:
        reasons.append(f"Buena demanda ({sales:,}/mes)")
    elif sales >= 500:
        reasons.append(f"Demanda aceptable ({sales:,}/mes)")

    if roi >= 25:
        reasons.append(f"ROI excelente ({roi}%)")
    elif roi >= 20:
        reasons.append(f"Buen ROI ({roi}%)")

    if profit >= 5:
        reasons.append(f"Ganancia alta (${profit:.2f}/unidad)")

    if sellers <= 3:
        reasons.append("Poca competencia")

    if is_amazon:
        reasons.append("CUIDADO: Amazon vende este producto")

    if sales < 500:
        reasons.append("ALERTA: Ventas bajas - producto lento")

    return reasons


# ─── Search Products in Stores ───

@router.post("/api/search-stores")
async def search_products_in_stores(query: StoreSearchQuery):
    """Search for products in retail stores and return direct links."""
    products = query.products
    results = []

    for p in products[:10]:  # Limit to 10 products
        title = p.get("title", "")
        brand = p.get("brand", "")
        asin = p.get("asin", "")

        # Extract key search terms from title
        search_terms = _extract_search_terms(title, brand)

        store_links = {
            "asin": asin,
            "title": title[:60],
            "search_terms": search_terms,
            "stores": {
                "amazon": f"https://www.amazon.com/dp/{asin}",
                "walmart": f"https://www.walmart.com/search?q={search_terms.replace(' ', '+')}",
                "target": f"https://www.target.com/s?searchTerm={search_terms.replace(' ', '+')}",
                "costco": f"https://www.costco.com/CatalogSearch?dept=All&keyword={search_terms.replace(' ', '+')}",
                "sams": f"https://www.samsclub.com/search/{search_terms.replace(' ', '%20')}",
                "faire": f"https://www.faire.com/search?q={search_terms.replace(' ', '+')}",
                "tundra": f"https://www.tundra.com/search?q={search_terms.replace(' ', '+')}",
                "biglots": f"https://www.biglots.com/search?q={search_terms.replace(' ', '+')}",
                "google_shopping": f"https://www.google.com/search?q={search_terms.replace(' ', '+')}+wholesale+price&tbm=shop",
            },
            "wholesale_tips": _get_wholesale_tips(title, brand),
        }
        results.append(store_links)

    return {"results": results}


def _extract_search_terms(title: str, brand: str) -> str:
    """Extract useful search terms from product title."""
    # Use brand + first key words from title
    if brand and len(brand) > 2:
        # Remove brand from title to avoid duplication
        clean_title = title.replace(brand, "").strip()
        words = clean_title.split()[:4]
        return f"{brand} {' '.join(words)}"
    else:
        words = title.split()[:6]
        return " ".join(words)


def _get_wholesale_tips(title: str, brand: str) -> list:
    """Get tips on where to find this product wholesale."""
    tips = []
    title_lower = title.lower()
    brand_lower = (brand or "").lower()

    # Brand-specific tips
    brand_wholesale = {
        "medicube": "Busca en Faire.com o contacta directamente a medicube para wholesale",
        "owala": "Busca en Faire.com o Tundra.com - marca popular con buen margen",
        "drift": "Busca en Faire.com - marca de lifestyle con precios wholesale accesibles",
        "zevo": "Busca en Costco, Sam's Club, o contacta a Zevo directamente",
        "brita": "Disponible en Costco y Sam's Club en packs grandes",
        "harry potter": "Busca en distribuidores de juguetes como D&H o Almo",
        "lego": "Contacta LEGO directamente o distribuidores autorizados",
        "huggies": "Disponible en Costco, Sam's Club, y distribuidores como UNFI",
        "pampers": "Disponible en Costco, Sam's Club, y distribuidores como UNFI",
        "tide": "Disponible en Costco, Sam's Club, y distribuidores como UNFI",
    }

    for b, tip in brand_wholesale.items():
        if b in brand_lower or b in title_lower:
            tips.append(tip)
            break

    if not tips:
        tips.append(f"Busca '{brand or title[:30]}' en Faire.com, Tundra.com, y Google Shopping wholesale")

    tips.append("Compara precios en Costco Business Center (Chantilly, VA)")
    tips.append("Revisa Walmart Clearance en tienda para posibles deals")

    return tips


# ─── Excel Export Endpoints ───

@router.post("/api/export-excel")
async def export_scan_to_excel(data: dict):
    """Export scan results to formatted Excel file."""
    products = data.get("products", [])
    stats = data.get("stats", {})

    if not products:
        raise HTTPException(400, "No products to export")

    buffer = generate_scan_results_excel(products, stats)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=fba_escaneo_productos.xlsx"}
    )


@router.post("/api/export-shopping-excel")
async def export_shopping_to_excel(data: dict):
    """Export AI-selected shopping list to formatted Excel with store links."""
    shopping_list = data.get("products", [])
    summary = data.get("summary", {})

    if not shopping_list:
        raise HTTPException(400, "No products to export")

    buffer = generate_shopping_list_excel(shopping_list, summary)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=fba_lista_compras.xlsx"}
    )
