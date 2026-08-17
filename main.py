"""
Amazon FBA Wholesale Automation System
Main application entry point.
"""
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import init_db
from config import settings
from routers import dashboard, products, scanner, inventory, suppliers, ai_chat, scraper


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


app = FastAPI(
    title="Amazon FBA Wholesale System",
    description="Automated product scanning, profitability analysis, and inventory management for Amazon FBA Wholesale",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(scanner.router, prefix="/scanner", tags=["Scanner"])
app.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
app.include_router(suppliers.router, prefix="/suppliers", tags=["Suppliers"])
app.include_router(ai_chat.router, prefix="/ai", tags=["AI Advisor"])
app.include_router(scraper.router, prefix="/stores", tags=["Store Scraper"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "system": "Amazon FBA Wholesale"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
