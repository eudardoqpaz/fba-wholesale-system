"""
Brand Approvals Router - Track brand approval requests for Amazon.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import BrandApproval
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class ApprovalCreate(BaseModel):
    brand_name: str
    category: Optional[str] = ""
    requirements: Optional[str] = ""
    amazon_request_url: Optional[str] = ""
    priority: Optional[str] = "medium"
    notes: Optional[str] = ""


class ApprovalUpdate(BaseModel):
    status: Optional[str] = None
    invoice_sent: Optional[bool] = None
    invoice_date: Optional[str] = None
    invoice_supplier: Optional[str] = None
    invoice_units: Optional[int] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[str] = None


@router.get("/", response_class=HTMLResponse)
async def approvals_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Brand approvals tracking page."""
    result = await db.execute(
        select(BrandApproval).order_by(BrandApproval.created_at.desc())
    )
    approvals = result.scalars().all()

    stats = {
        "total": len(approvals),
        "pending": sum(1 for a in approvals if a.status == "pending"),
        "submitted": sum(1 for a in approvals if a.status == "submitted"),
        "approved": sum(1 for a in approvals if a.status == "approved"),
        "rejected": sum(1 for a in approvals if a.status == "rejected"),
    }

    return templates.TemplateResponse("approvals.html", {
        "request": request,
        "approvals": approvals,
        "stats": stats,
    })


@router.get("/api/list")
async def list_approvals(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """List all brand approvals, optionally filtered by status."""
    query = select(BrandApproval).order_by(BrandApproval.created_at.desc())
    if status:
        query = query.where(BrandApproval.status == status)

    result = await db.execute(query)
    approvals = result.scalars().all()

    return {
        "approvals": [
            {
                "id": a.id,
                "brand_name": a.brand_name,
                "category": a.category,
                "status": a.status,
                "priority": a.priority,
                "requirements": a.requirements,
                "invoice_sent": a.invoice_sent,
                "invoice_date": a.invoice_date.isoformat() if a.invoice_date else None,
                "invoice_supplier": a.invoice_supplier,
                "invoice_units": a.invoice_units,
                "contact_email": a.contact_email,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                "notes": a.notes,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in approvals
        ],
        "total": len(approvals),
    }


@router.post("/api/create")
async def create_approval(data: ApprovalCreate, db: AsyncSession = Depends(get_db)):
    """Create a new brand approval tracking entry."""
    approval = BrandApproval(
        brand_name=data.brand_name,
        category=data.category,
        requirements=data.requirements,
        amazon_request_url=data.amazon_request_url,
        priority=data.priority,
        notes=data.notes,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)

    return {
        "status": "ok",
        "id": approval.id,
        "message": f"Tracking {data.brand_name} approval",
    }


@router.put("/api/{approval_id}")
async def update_approval(approval_id: int, data: ApprovalUpdate, db: AsyncSession = Depends(get_db)):
    """Update a brand approval entry."""
    result = await db.execute(
        select(BrandApproval).where(BrandApproval.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(404, "Approval not found")

    if data.status is not None:
        approval.status = data.status
        if data.status == "submitted":
            approval.submitted_at = datetime.now(timezone.utc)
        elif data.status in ("approved", "rejected"):
            approval.resolved_at = datetime.now(timezone.utc)

    if data.invoice_sent is not None:
        approval.invoice_sent = data.invoice_sent
    if data.invoice_date is not None:
        try:
            approval.invoice_date = datetime.fromisoformat(data.invoice_date)
        except ValueError:
            pass
    if data.invoice_supplier is not None:
        approval.invoice_supplier = data.invoice_supplier
    if data.invoice_units is not None:
        approval.invoice_units = data.invoice_units
    if data.contact_email is not None:
        approval.contact_email = data.contact_email
    if data.contact_phone is not None:
        approval.contact_phone = data.contact_phone
    if data.notes is not None:
        approval.notes = data.notes
    if data.priority is not None:
        approval.priority = data.priority

    await db.commit()
    return {"status": "ok", "new_status": approval.status}


@router.delete("/api/{approval_id}")
async def delete_approval(approval_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a brand approval entry."""
    result = await db.execute(
        select(BrandApproval).where(BrandApproval.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(404, "Approval not found")

    await db.delete(approval)
    await db.commit()
    return {"status": "ok", "message": "Deleted"}


@router.post("/api/{approval_id}/submit")
async def mark_submitted(approval_id: int, db: AsyncSession = Depends(get_db)):
    """Mark an approval as submitted to Amazon."""
    result = await db.execute(
        select(BrandApproval).where(BrandApproval.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(404, "Approval not found")

    approval.status = "submitted"
    approval.submitted_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "ok", "message": f"Marked {approval.brand_name} as submitted"}


@router.post("/api/{approval_id}/approve")
async def mark_approved(approval_id: int, db: AsyncSession = Depends(get_db)):
    """Mark an approval as approved by Amazon."""
    result = await db.execute(
        select(BrandApproval).where(BrandApproval.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(404, "Approval not found")

    approval.status = "approved"
    approval.resolved_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "ok", "message": f"{approval.brand_name} approved!"}


@router.post("/api/{approval_id}/reject")
async def mark_rejected(approval_id: int, db: AsyncSession = Depends(get_db)):
    """Mark an approval as rejected by Amazon."""
    result = await db.execute(
        select(BrandApproval).where(BrandApproval.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(404, "Approval not found")

    approval.status = "rejected"
    approval.resolved_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "ok", "message": f"{approval.brand_name} rejected"}
