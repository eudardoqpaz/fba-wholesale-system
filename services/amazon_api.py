"""
Amazon SP-API Integration - Check product eligibility and restrictions.
"""
import httpx
import asyncio
from typing import Optional
from config import settings


# Amazon SP-API endpoints
SP_API_BASE = "https://sellingpartnerapi-na.amazon.com"
TOKEN_URL = "https://api.amazon.com/auth/o2/token"


class AmazonSPAPI:
    """Amazon Selling Partner API integration for checking product eligibility."""

    def __init__(self):
        self.refresh_token = settings.amazon_sp_api_refresh_token
        self.client_id = settings.amazon_sp_api_client_id
        self.client_secret = settings.amazon_sp_api_client_secret
        self.seller_id = settings.amazon_seller_id
        self.marketplace_id = settings.amazon_marketplace_id
        self.access_token = None
        self.token_expires = 0

    async def _get_access_token(self) -> str:
        """Get or refresh the SP-API access token."""
        import time
        if self.access_token and time.time() < self.token_expires:
            return self.access_token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(TOKEN_URL, data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            data = resp.json()
            self.access_token = data.get("access_token")
            self.token_expires = time.time() + data.get("expires_in", 3600) - 60
            return self.access_token

    async def _api_get(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated GET request to SP-API."""
        token = await self._get_access_token()
        headers = {
            "x-amz-access-token": token,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{SP_API_BASE}{endpoint}", headers=headers, params=params)
            return resp.json()

    async def check_listing_eligibility(self, asins: list[str]) -> dict:
        """
        Check if seller can list specific ASINs.
        Returns eligibility status for each ASIN.
        """
        if not self.refresh_token:
            return self._mock_eligibility(asins)

        try:
            # Use Catalog Items API to get product details
            results = {}
            for asin in asins[:20]:  # Limit to 20 per call
                try:
                    data = await self._api_get(
                        f"/catalog/2022-04-01/items/{asin}",
                        params={
                            "marketplaceIds": self.marketplace_id,
                            "sellerId": self.seller_id,
                            "includedData": "summaries,attributes,restrictions",
                        }
                    )
                    results[asin] = self._parse_eligibility(data, asin)
                except Exception as e:
                    results[asin] = {"asin": asin, "eligible": None, "error": str(e)}

                await asyncio.sleep(0.5)  # Rate limiting

            return results
        except Exception as e:
            return {"error": str(e)}

    async def get_restricted_categories(self) -> list[dict]:
        """Get list of categories where seller has restrictions."""
        if not self.refresh_token:
            return self._mock_restricted_categories()

        try:
            # This would use the Restrictions API
            # For now, return common restricted categories
            return self._mock_restricted_categories()
        except Exception as e:
            return []

    async def check_product_restrictions(self, asin: str) -> dict:
        """Check specific product restrictions."""
        if not self.refresh_token:
            return self._mock_product_check(asin)

        try:
            data = await self._api_get(
                f"/listings/2021-08-01/items/{self.seller_id}/{asin}",
                params={
                    "marketplaceIds": self.marketplace_id,
                    "includedData": "summaries,attributes,offers,fulfillmentAvailability",
                }
            )
            return {
                "asin": asin,
                "can_sell": True,
                "requires_approval": False,
                "details": data,
            }
        except Exception as e:
            if "403" in str(e) or "Restricted" in str(e):
                return {
                    "asin": asin,
                    "can_sell": False,
                    "requires_approval": True,
                    "reason": "Category restricted or requires approval",
                }
            return {"asin": asin, "can_sell": None, "error": str(e)}

    def _parse_eligibility(self, data: dict, asin: str) -> dict:
        """Parse SP-API response to determine eligibility."""
        restrictions = data.get("restrictions", [])
        summaries = data.get("summaries", [])

        # Check if there are any restrictions
        has_restrictions = len(restrictions) > 0

        # Get category
        category = ""
        if summaries:
            for s in summaries:
                if s.get("marketplaceId") == self.marketplace_id:
                    category = s.get("productType", "")
                    break

        return {
            "asin": asin,
            "eligible": not has_restrictions,
            "requires_approval": has_restrictions,
            "restrictions": restrictions,
            "category": category,
        }

    def _mock_eligibility(self, asins: list[str]) -> dict:
        """Mock eligibility check when SP-API is not configured."""
        # Common restricted categories by ASIN pattern
        restricted_patterns = {
            "B0": "May require approval in Beauty/Health",
        }

        results = {}
        for asin in asins:
            # Default to "check manually" when API not configured
            results[asin] = {
                "asin": asin,
                "eligible": None,
                "requires_approval": None,
                "reason": "SP-API not configured - check manually in Seller Central",
                "manual_check_url": f"https://sellercentral.amazon.com/product-search/searchTerm={asin}",
            }
        return results

    def _mock_restricted_categories(self) -> list[dict]:
        """Common restricted categories for reference."""
        return [
            {"category": "Beauty", "status": "restricted", "approval_required": True},
            {"category": "Health & Household", "status": "restricted", "approval_required": True},
            {"category": "Grocery & Gourmet Food", "status": "restricted", "approval_required": True},
            {"category": "Baby Products", "status": "restricted", "approval_required": True},
            {"category": "Toys & Games", "status": "seasonal_restricted", "approval_required": True, "note": "Restricted Oct-Jan"},
            {"category": "Automotive", "status": "restricted", "approval_required": True},
            {"category": "Jewelry", "status": "restricted", "approval_required": True},
            {"category": "Clothing", "status": "open", "approval_required": False},
            {"category": "Home & Kitchen", "status": "open", "approval_required": False},
            {"category": "Sports & Outdoors", "status": "open", "approval_required": False},
            {"category": "Pet Supplies", "status": "open", "approval_required": False},
            {"category": "Tools & Home Improvement", "status": "open", "approval_required": False},
            {"category": "Office Products", "status": "open", "approval_required": False},
            {"category": "Electronics", "status": "open", "approval_required": False},
            {"category": "Computers", "status": "open", "approval_required": False},
        ]

    def _mock_product_check(self, asin: str) -> dict:
        """Mock product check."""
        return {
            "asin": asin,
            "eligible": None,
            "requires_approval": None,
            "reason": "Configure SP-API to check automatically",
            "manual_check": f"https://sellercentral.amazon.com/product-search/searchTerm={asin}",
        }


amazon_api = AmazonSPAPI()
