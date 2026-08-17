"""
Auto-Discovery Router - AI finds products for you.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.auto_discovery import auto_discovery
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class DiscoveryQuery(BaseModel):
    budget: float = 1000
    risk_level: str = "conservative"
    categories: Optional[list[str]] = None


@router.get("/", response_class=HTMLResponse)
async def discovery_page(request: Request):
    """Auto-discovery page - AI finds products for you."""
    return templates.TemplateResponse("discovery.html", {"request": request})


@router.post("/api/find")
async def find_products(query: DiscoveryQuery):
    """AI-powered product discovery."""
    results = await auto_discovery.find_products(
        budget=query.budget,
        risk_level=query.risk_level,
        categories=query.categories,
    )
    return results
