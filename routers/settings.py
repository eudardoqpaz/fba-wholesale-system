"""
Settings Router - Configure seller eligibility and preferences.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from services.eligibility import eligibility_service, AMAZON_CATEGORIES
from pydantic import BaseModel

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class EligibilityUpdate(BaseModel):
    categories: list[str]


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Settings page for configuring seller eligibility."""
    approved = await eligibility_service.get_approved_categories(db)
    all_cats = eligibility_service.get_all_categories()

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "approved_categories": approved,
        "all_categories": all_cats,
    })


@router.get("/api/eligibility")
async def get_eligibility(db: AsyncSession = Depends(get_db)):
    """Get current eligibility settings."""
    approved = await eligibility_service.get_approved_categories(db)
    all_cats = eligibility_service.get_all_categories()

    categories = []
    for cat_id, cat_info in all_cats.items():
        categories.append({
            "id": cat_id,
            "name": cat_info["name"],
            "typically_open": cat_info["typically_open"],
            "approval_difficulty": cat_info["approval_difficulty"],
            "approved": cat_id in approved,
            "note": cat_info.get("note", ""),
        })

    return {"categories": categories, "approved_count": len(approved)}


@router.post("/api/eligibility")
async def update_eligibility(data: EligibilityUpdate, db: AsyncSession = Depends(get_db)):
    """Update approved categories."""
    await eligibility_service.set_approved_categories(db, data.categories)
    return {"status": "ok", "approved": len(data.categories)}
