"""
AI Advisor Router - Chat interface and AI-powered analysis.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocket
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database import get_db
from models import Product, InventoryItem, Alert
from services.ai_advisor import ai_advisor
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class ChatMessage(BaseModel):
    message: str
    history: Optional[list[dict]] = []


class ProductAnalysis(BaseModel):
    product_id: int


@router.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    """AI Advisor chat page."""
    return templates.TemplateResponse("ai_chat.html", {"request": request})


@router.post("/api/chat")
async def chat(msg: ChatMessage, db: AsyncSession = Depends(get_db)):
    """Send a message to the AI advisor."""
    # Build business context from DB
    context = await _build_context(db)

    response = await ai_advisor.ask(
        question=msg.message,
        context=context,
        conversation_history=msg.history,
    )

    return {"response": response}


@router.post("/api/analyze/{product_id}")
async def analyze_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """AI analysis of a specific product."""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.supplier_products))
        .options(selectinload(Product.inventory_items))
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return {"error": "Product not found"}

    product_data = {
        "asin": product.asin,
        "title": product.title,
        "amazon_price": product.amazon_price,
        "supplier_cost": product.best_supplier_price or 0,
        "bsr": product.bsr,
        "fba_seller_count": product.fba_seller_count,
        "is_amazon_seller": product.is_amazon_seller,
        "monthly_sales_est": product.monthly_sales_est,
        "review_count": product.review_count,
        "rating": product.rating,
        "roi_pct": product.roi,
        "net_profit": product.net_profit,
        "fba_fee": product.fba_fee,
    }

    analysis = await ai_advisor.analyze_product(product_data)
    return {"analysis": analysis, "product": product_data}


@router.post("/api/briefing")
async def daily_briefing(db: AsyncSession = Depends(get_db)):
    """Generate AI daily business briefing."""
    # Gather business data
    products_result = await db.execute(select(Product).where(Product.status == "active"))
    products = products_result.scalars().all()

    inv_result = await db.execute(select(InventoryItem))
    inventory = inv_result.scalars().all()

    alerts_result = await db.execute(select(Alert).where(Alert.is_read == False))
    alerts = alerts_result.scalars().all()

    business_data = {
        "total_products": len(products),
        "profitable_count": sum(1 for p in products if p.is_profitable),
        "total_fba_units": sum(i.quantity_fba for i in inventory),
        "total_invested": sum(i.total_invested for i in inventory),
        "low_stock": sum(1 for i in inventory if i.status == "low_stock"),
        "out_of_stock": sum(1 for i in inventory if i.status == "out_of_stock"),
        "alerts_count": len(alerts),
    }

    briefing = await ai_advisor.daily_briefing(business_data)
    return {"briefing": briefing, "data": business_data}


@router.get("/api/explain/{concept}")
async def explain_concept(concept: str):
    """Explain an FBA/wholesale concept."""
    explanation = await ai_advisor.explain_concept(concept)
    return {"concept": concept, "explanation": explanation}


@router.get("/api/suggestions")
async def get_suggestions(db: AsyncSession = Depends(get_db)):
    """Get AI-powered action suggestions based on current business state."""
    suggestions = []

    # Check products
    products_result = await db.execute(select(Product).where(Product.status == "active"))
    products = products_result.scalars().all()

    if len(products) == 0:
        suggestions.append({
            "priority": "high",
            "icon": "bi-search",
            "title": "Encuentra tus primeros productos",
            "description": "Usa el Product Finder en el Scanner para buscar productos rentables en Keepa.",
            "action": "/scanner",
        })
    elif len(products) < 10:
        suggestions.append({
            "priority": "medium",
            "icon": "bi-plus-circle",
            "title": "Diversifica tu catalogo",
            "description": f"Tienes {len(products)} productos. Agrega mas para reducir riesgo.",
            "action": "/scanner",
        })

    # Check inventory
    inv_result = await db.execute(select(InventoryItem))
    inventory = inv_result.scalars().all()
    low_stock = [i for i in inventory if i.status == "low_stock"]
    if low_stock:
        suggestions.append({
            "priority": "high",
            "icon": "bi-exclamation-triangle",
            "title": f"{len(low_stock)} productos con stock bajo",
            "description": "Reordena pronto para evitar quedarte sin stock.",
            "action": "/inventory",
        })

    # Check profitable products
    profitable = [p for p in products if p.is_profitable]
    if profitable and len(profitable) < len(products) * 0.5:
        suggestions.append({
            "priority": "medium",
            "icon": "bi-graph-down",
            "title": "Revisa productos no rentables",
            "description": f"Solo {len(profitable)}/{len(products)} productos son rentables.",
            "action": "/products",
        })

    if not suggestions:
        suggestions.append({
            "priority": "low",
            "icon": "bi-check-circle",
            "title": "Todo parece bien",
            "description": "Revisa el Scanner para encontrar nuevas oportunidades.",
            "action": "/scanner",
        })

    return {"suggestions": suggestions}


async def _build_context(db: AsyncSession) -> str:
    """Build business context string for the AI."""
    products_result = await db.execute(select(Product).where(Product.status == "active"))
    products = products_result.scalars().all()

    inv_result = await db.execute(select(InventoryItem))
    inventory = inv_result.scalars().all()

    top_products = sorted(products, key=lambda p: p.roi, reverse=True)[:5]
    top_info = "\n".join([
        f"- {p.title[:40]} ({p.asin}): ${p.amazon_price}, ROI {p.roi}%, Ganancia ${p.net_profit}"
        for p in top_products if p.amazon_price > 0
    ]) if top_products else "Sin productos aun"

    return f"""Ubicacion: Sterling, Virginia, USA
Productos activos: {len(products)}
Productos rentables: {sum(1 for p in products if p.is_profitable)}
Unidades en FBA: {sum(i.quantity_fba for i in inventory)}
Invertido total: ${sum(i.total_invested for i in inventory):.2f}
Stock bajo: {sum(1 for i in inventory if i.status == 'low_stock')}

Top productos por ROI:
{top_info}
"""
