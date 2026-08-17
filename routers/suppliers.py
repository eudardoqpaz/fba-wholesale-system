"""
Suppliers Router - Manage wholesale suppliers.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Supplier
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class SupplierCreate(BaseModel):
    name: str
    contact_name: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    website: Optional[str] = ""
    address: Optional[str] = ""
    supplier_type: Optional[str] = "distributor"
    payment_terms: Optional[str] = ""
    min_order: Optional[float] = 0
    notes: Optional[str] = ""


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    supplier_type: Optional[str] = None
    payment_terms: Optional[str] = None
    min_order: Optional[float] = None
    notes: Optional[str] = None
    resale_cert_registered: Optional[bool] = None
    status: Optional[str] = None


@router.get("/api/list")
async def list_suppliers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).order_by(Supplier.name))
    suppliers = result.scalars().all()
    return {
        "suppliers": [
            {
                "id": s.id,
                "name": s.name,
                "contact_name": s.contact_name,
                "email": s.email,
                "phone": s.phone,
                "website": s.website,
                "supplier_type": s.supplier_type,
                "payment_terms": s.payment_terms,
                "min_order": s.min_order,
                "resale_cert_registered": s.resale_cert_registered,
                "status": s.status,
            }
            for s in suppliers
        ]
    }


@router.post("/api/add")
async def add_supplier(data: SupplierCreate, db: AsyncSession = Depends(get_db)):
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return {"status": "ok", "supplier_id": supplier.id}


@router.put("/api/{supplier_id}")
async def update_supplier(supplier_id: int, data: SupplierUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, key, value)

    await db.commit()
    return {"status": "ok"}


@router.delete("/api/{supplier_id}")
async def delete_supplier(supplier_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")

    supplier.status = "inactive"
    await db.commit()
    return {"status": "ok"}
