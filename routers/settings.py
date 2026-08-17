"""
Settings Router - Configure seller eligibility and preferences.
"""
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from services.eligibility import eligibility_service, AMAZON_CATEGORIES
from services.amazon_api import amazon_api, TOKEN_URL, SP_API_BASE
from config import settings
from pydantic import BaseModel

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Amazon OAuth constants
AMAZON_AUTH_URL = "https://sellercentral.amazon.com/apps/authorize/consent"
LWA_AUTH_URL = "https://www.amazon.com/ap/oa"
REDIRECT_URI = "http://localhost:8000/settings/amazon/callback"


class EligibilityUpdate(BaseModel):
    categories: list[str]


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Settings page for configuring seller eligibility."""
    approved = await eligibility_service.get_approved_categories(db)
    all_cats = eligibility_service.get_all_categories()
    amazon_connected = amazon_api.is_configured

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "approved_categories": approved,
        "all_categories": all_cats,
        "amazon_connected": amazon_connected,
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


@router.get("/api/amazon/status")
async def amazon_connection_status():
    """Check Amazon SP-API connection status."""
    if not amazon_api.is_configured:
        return {
            "connected": False,
            "configured": False,
            "message": "SP-API credentials not configured. Add them to .env file.",
        }

    account_info = await amazon_api.get_seller_account_info()
    return {
        "connected": account_info.get("connected", False),
        "configured": True,
        "seller_id": amazon_api.seller_id,
        "marketplace_id": amazon_api.marketplace_id,
        "details": account_info,
    }


# ─── OAuth Flow for getting Refresh Token ───

@router.get("/api/amazon/auth-url")
async def get_amazon_auth_url():
    """
    Generate Amazon OAuth authorization URL.
    User clicks this to authorize the app and get a refresh token.
    """
    if not settings.amazon_sp_api_client_id:
        return {
            "status": "error",
            "message": "AMAZON_SP_API_CLIENT_ID not configured in .env",
        }

    auth_url = (
        f"{LWA_AUTH_URL}"
        f"?client_id={settings.amazon_sp_api_client_id}"
        f"&scope=catalog::items"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state=amazon_auth"
    )

    return {
        "status": "ok",
        "auth_url": auth_url,
        "instructions": [
            "1. Abre el link de autorizacion en tu navegador",
            "2. Inicia sesion con tu cuenta de Amazon Seller",
            "3. Autoriza la aplicacion",
            "4. Amazon te redirigira a esta app con el refresh token",
        ],
    }


@router.get("/amazon/callback")
async def amazon_oauth_callback(request: Request):
    """
    OAuth callback endpoint. Amazon redirects here after user authorizes.
    Exchanges the authorization code for a refresh token.
    """
    code = request.query_params.get("spapi_oauth_code") or request.query_params.get("code")
    error = request.query_params.get("error")

    if error:
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "oauth_error": f"Amazon returned error: {error}",
            "oauth_success": None,
        })

    if not code:
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "oauth_error": "No authorization code received from Amazon",
            "oauth_success": None,
        })

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(TOKEN_URL, data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.amazon_sp_api_client_id,
                "client_secret": settings.amazon_sp_api_client_secret,
                "redirect_uri": REDIRECT_URI,
            })
            resp.raise_for_status()
            token_data = resp.json()

        refresh_token = token_data.get("refresh_token")
        access_token = token_data.get("access_token")

        if not refresh_token:
            return templates.TemplateResponse("settings.html", {
                "request": request,
                "oauth_error": f"No refresh token in response. Got: {list(token_data.keys())}",
                "oauth_success": None,
            })

        return templates.TemplateResponse("settings.html", {
            "request": request,
            "oauth_error": None,
            "oauth_success": {
                "refresh_token": refresh_token,
                "message": "Autorizacion exitosa! Copia el refresh token y agregalo a tu .env",
            },
        })

    except httpx.HTTPStatusError as e:
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "oauth_error": f"Error exchanging code: HTTP {e.response.status_code} - {e.response.text[:200]}",
            "oauth_success": None,
        })
    except Exception as e:
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "oauth_error": f"Error: {str(e)}",
            "oauth_success": None,
        })


@router.get("/api/amazon/test-connection")
async def test_amazon_connection():
    """
    Test SP-API connection by calling a simple endpoint.
    Useful after configuring credentials.
    """
    if not amazon_api.is_configured:
        return {
            "success": False,
            "error": "Credentials not configured. Set AMAZON_SP_API_CLIENT_ID, AMAZON_SP_API_CLIENT_SECRET, and AMAZON_SP_API_REFRESH_TOKEN in .env",
        }

    try:
        token = await amazon_api._get_access_token()
        return {
            "success": True,
            "message": "Connection successful! Access token obtained.",
            "token_preview": f"{token[:20]}..." if token else None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get access token: {str(e)}",
        }


# ─── Existing endpoints ───

@router.post("/api/amazon/sync-restrictions")
async def sync_amazon_restrictions(db: AsyncSession = Depends(get_db)):
    """
    Sync restrictions from Amazon SP-API.
    Probes common categories via SP-API and updates local eligibility settings.
    """
    if not amazon_api.is_configured:
        return {
            "status": "error",
            "message": "SP-API not configured. Add credentials to .env first.",
        }

    try:
        sync_result = await amazon_api.sync_eligibility_to_categories()
        approved = sync_result["approved_categories"]

        # Save the synced categories
        await eligibility_service.set_approved_categories(db, approved)

        return {
            "status": "ok",
            "source": "amazon_sp_api",
            "approved_categories": approved,
            "restricted_categories": sync_result["restricted_categories"],
            "total_approved": sync_result["total_approved"],
            "total_restricted": sync_result["total_restricted"],
            "probe_results": sync_result["probe_results"],
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Sync failed: {str(e)}",
        }


@router.get("/api/amazon/check-asin/{asin}")
async def check_asin_restriction(asin: str):
    """Check if a specific ASIN is restricted for this seller."""
    result = await amazon_api.check_restriction_for_asin(asin)
    return result
