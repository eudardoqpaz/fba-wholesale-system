"""
Scraper Router - Search stores and get wholesale account info.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.scraper import scraper, STORE_INFO
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class SearchQuery(BaseModel):
    store: str
    query: str
    max_results: int = 20


@router.get("/", response_class=HTMLResponse)
async def scraper_page(request: Request):
    """Store scraper and wholesale info page."""
    stores = scraper.get_all_stores()
    return templates.TemplateResponse("scraper.html", {
        "request": request,
        "stores": stores,
        "store_info": STORE_INFO,
    })


@router.post("/api/search")
async def search_store(query: SearchQuery):
    """Search a store for products."""
    results = await scraper.search_store(query.store, query.query, query.max_results)
    return {"results": results, "store": query.store, "query": query.query}


@router.get("/api/store/{store_id}")
async def get_store_info(store_id: str):
    """Get detailed info about a store and how to open a wholesale account."""
    info = scraper.get_store_info(store_id)
    return info


@router.get("/api/stores")
async def list_stores():
    """List all supported stores."""
    return {"stores": scraper.get_all_stores()}
