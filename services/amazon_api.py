"""
Amazon SP-API Integration - Check product eligibility and restrictions.
"""
import httpx
import asyncio
import time
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

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
        self.access_token: Optional[str] = None
        self.token_expires: float = 0

    @property
    def is_configured(self) -> bool:
        """Check if SP-API credentials are configured."""
        return bool(self.refresh_token and self.client_id and self.client_secret)

    async def _get_access_token(self) -> str:
        """Get or refresh the SP-API access token."""
        if self.access_token and time.time() < self.token_expires:
            return self.access_token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(TOKEN_URL, data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            resp.raise_for_status()
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
            if resp.status_code == 429:
                # Rate limited - wait and retry once
                await asyncio.sleep(2)
                resp = await client.get(f"{SP_API_BASE}{endpoint}", headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_seller_account_info(self) -> dict:
        """
        Get seller account information to verify connection works.
        Uses the Sellers API to get marketplace participation info.
        """
        if not self.is_configured:
            return {"connected": False, "error": "SP-API not configured"}

        try:
            data = await self._api_get(
                "/sellers/v1/marketplaceParticipations"
            )
            marketplaces = data.get("payload", [])
            return {
                "connected": True,
                "marketplaces": marketplaces,
                "seller_id": self.seller_id,
            }
        except httpx.HTTPStatusError as e:
            return {"connected": False, "error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def check_listing_eligibility(self, asins: list[str]) -> dict:
        """
        Check if seller can list specific ASINs using Catalog Items API v2022-04-01.
        Returns eligibility status and restriction details for each ASIN.
        """
        if not self.is_configured:
            return self._mock_eligibility(asins)

        results = {}
        for asin in asins[:20]:
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
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    results[asin] = {
                        "asin": asin,
                        "eligible": False,
                        "requires_approval": True,
                        "reason": "Restricted - seller not authorized for this product",
                    }
                else:
                    results[asin] = {"asin": asin, "eligible": None, "error": str(e)}
            except Exception as e:
                results[asin] = {"asin": asin, "eligible": None, "error": str(e)}

            await asyncio.sleep(0.5)

        return results

    async def get_restricted_categories(self) -> list[dict]:
        """
        Probe common categories to determine which ones the seller is restricted in.
        Uses the Catalog Items API with known ASINs from each category.
        """
        if not self.is_configured:
            return self._mock_restricted_categories()

        # Representative ASINs for probing category restrictions
        # These are well-known products in each category
        probe_asins = {
            "beauty": "B00B9AD6HQ",
            "health_household": "B000GG0BNE",
            "grocery": "B000E1DSMC",
            "baby": "B00E2VK6B0",
            "toys_games": "B00NHQFA1I",
            "jewelry": "B00BAXFKKW",
        }

        restricted = []
        for cat_id, probe_asin in probe_asins.items():
            try:
                data = await self._api_get(
                    f"/catalog/2022-04-01/items/{probe_asin}",
                    params={
                        "marketplaceIds": self.marketplace_id,
                        "sellerId": self.seller_id,
                        "includedData": "restrictions",
                    }
                )
                restrictions = data.get("restrictions", [])
                is_restricted = len(restrictions) > 0
                restricted.append({
                    "category_id": cat_id,
                    "restricted": is_restricted,
                    "restrictions": restrictions,
                })
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    restricted.append({
                        "category_id": cat_id,
                        "restricted": True,
                        "restrictions": [{"reason": "Seller not authorized"}],
                    })
                else:
                    restricted.append({
                        "category_id": cat_id,
                        "restricted": None,
                        "error": str(e),
                    })
            except Exception as e:
                restricted.append({
                    "category_id": cat_id,
                    "restricted": None,
                    "error": str(e),
                })
            await asyncio.sleep(0.5)

        return restricted

    async def check_product_restrictions(self, asin: str) -> dict:
        """Check specific product restrictions using Listings Items API."""
        if not self.is_configured:
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
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return {
                    "asin": asin,
                    "can_sell": False,
                    "requires_approval": True,
                    "reason": "Category restricted or requires approval",
                }
            if e.response.status_code == 404:
                return {
                    "asin": asin,
                    "can_sell": None,
                    "requires_approval": None,
                    "reason": "Product not found in catalog",
                }
            return {"asin": asin, "can_sell": None, "error": str(e)}
        except Exception as e:
            return {"asin": asin, "can_sell": None, "error": str(e)}

    async def check_restriction_for_asin(self, asin: str) -> dict:
        """
        Lightweight check: does this ASIN have restrictions for the current seller?
        Returns a simple dict suitable for integration into scanner results.
        """
        if not self.is_configured:
            return {"restricted": None, "reason": "SP-API not configured"}

        try:
            data = await self._api_get(
                f"/catalog/2022-04-01/items/{asin}",
                params={
                    "marketplaceIds": self.marketplace_id,
                    "sellerId": self.seller_id,
                    "includedData": "restrictions",
                }
            )
            restrictions = data.get("restrictions", [])
            if restrictions:
                reasons = [r.get("reason", "Unknown") for r in restrictions]
                return {
                    "restricted": True,
                    "reason": "; ".join(reasons),
                    "restrictions": restrictions,
                }
            return {"restricted": False, "reason": None}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return {"restricted": True, "reason": "Seller not authorized"}
            return {"restricted": None, "reason": f"API error: {e.response.status_code}"}
        except Exception as e:
            return {"restricted": None, "reason": str(e)}

    async def sync_eligibility_to_categories(self) -> dict:
        """
        Probe common categories and return a list of approved category IDs.
        This is the main sync method that connects SP-API to the local eligibility system.
        """
        restricted = await self.get_restricted_categories()

        # Map probe results to category IDs
        restricted_ids = set()
        for r in restricted:
            if r.get("restricted") is True:
                restricted_ids.add(r["category_id"])

        # All known categories
        all_categories = [
            "home_kitchen", "tools_home_improvement", "sports_outdoors",
            "pet_supplies", "office_products", "electronics", "computers",
            "clothing", "shoes", "automotive", "beauty", "health_household",
            "baby", "grocery", "toys_games", "jewelry", "watches",
            "luggage", "musical_instruments", "industrial",
        ]

        approved = [cat for cat in all_categories if cat not in restricted_ids]

        return {
            "approved_categories": approved,
            "restricted_categories": list(restricted_ids),
            "probe_results": restricted,
            "total_approved": len(approved),
            "total_restricted": len(restricted_ids),
        }

    # ─── Inventory Management ───

    async def _api_put(self, endpoint: str, json_data: dict = None, params: dict = None) -> dict:
        """Make authenticated PUT request to SP-API."""
        token = await self._get_access_token()
        headers = {
            "x-amz-access-token": token,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"{SP_API_BASE}{endpoint}",
                headers=headers,
                json=json_data,
                params=params,
            )
            if resp.status_code == 429:
                await asyncio.sleep(2)
                resp = await client.put(
                    f"{SP_API_BASE}{endpoint}",
                    headers=headers,
                    json=json_data,
                    params=params,
                )
            resp.raise_for_status()
            return resp.json() if resp.text else {"status": "ok"}

    async def _api_patch(self, endpoint: str, json_data: dict = None, params: dict = None) -> dict:
        """Make authenticated PATCH request to SP-API."""
        token = await self._get_access_token()
        headers = {
            "x-amz-access-token": token,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{SP_API_BASE}{endpoint}",
                headers=headers,
                json=json_data,
                params=params,
            )
            if resp.status_code == 429:
                await asyncio.sleep(2)
                resp = await client.patch(
                    f"{SP_API_BASE}{endpoint}",
                    headers=headers,
                    json=json_data,
                    params=params,
                )
            resp.raise_for_status()
            return resp.json() if resp.text else {"status": "ok"}

    async def get_inventory_summaries(self, granularity_type: str = "Marketplace", next_token: str = None) -> dict:
        """
        Get FBA inventory summaries.
        Returns list of products with quantities, status, and condition.
        """
        if not self.is_configured:
            return {"error": "SP-API not configured", "items": []}

        try:
            params = {
                "details": "true",
                "granularityType": granularity_type,
                "granularityId": self.marketplace_id,
                "marketplaceIds": self.marketplace_id,
            }
            if next_token:
                params["nextToken"] = next_token

            data = await self._api_get("/fba/inventory/v1/summaries", params=params)

            items = []
            for summary in data.get("payload", {}).get("inventorySummaries", []):
                items.append({
                    "asin": summary.get("asin", ""),
                    "sku": summary.get("sellerSku", ""),
                    "fn_sku": summary.get("fnSku", ""),
                    "product_name": summary.get("productName", ""),
                    "condition": summary.get("condition", ""),
                    "total_quantity": summary.get("totalQuantity", 0),
                    "fulfillable_quantity": 0,
                    "inbound_quantity": 0,
                    "reserved_quantity": 0,
                    "unfulfillable_quantity": 0,
                })

                # Parse inventory details
                details = summary.get("inventoryDetails", {})
                if details:
                    items[-1]["fulfillable_quantity"] = details.get("fulfillableQuantity", 0)
                    items[-1]["inbound_quantity"] = details.get("inboundQuantity", 0)
                    items[-1]["reserved_quantity"] = details.get("reservedQuantity", 0)
                    items[-1]["unfulfillable_quantity"] = details.get("unfulfillableQuantity", 0)

            return {
                "items": items,
                "next_token": data.get("pagination", {}).get("nextToken"),
                "total": len(items),
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}", "items": []}
        except Exception as e:
            return {"error": str(e), "items": []}

    async def get_all_inventory(self) -> dict:
        """Get all FBA inventory items, handling pagination."""
        all_items = []
        next_token = None

        while True:
            result = await self.get_inventory_summaries(next_token=next_token)
            if result.get("error"):
                return result

            all_items.extend(result.get("items", []))
            next_token = result.get("next_token")

            if not next_token:
                break

            await asyncio.sleep(0.5)

        return {"items": all_items, "total": len(all_items)}

    async def update_listing_price(self, sku: str, price: float, currency: str = "USD") -> dict:
        """
        Update the price of a listing.
        Uses the Listings Items API v2021-08-01.
        """
        if not self.is_configured:
            return {"error": "SP-API not configured"}

        try:
            endpoint = f"/listings/2021-08-01/items/{self.seller_id}/{sku}"
            params = {"marketplaceIds": self.marketplace_id}

            patch_data = {
                "productType": "",  # Will be auto-detected
                "patches": [
                    {
                        "op": "replace",
                        "path": "/attributes/purchasable_offer",
                        "value": [
                            {
                                "currency": currency,
                                "our_price": [
                                    {
                                        "schedule": [
                                            {
                                                "value_with_tax": price,
                                            }
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }

            result = await self._api_patch(endpoint, json_data=patch_data, params=params)
            return {
                "status": "ok",
                "sku": sku,
                "new_price": price,
                "currency": currency,
                "details": result,
            }
        except httpx.HTTPStatusError as e:
            return {
                "status": "error",
                "sku": sku,
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
        except Exception as e:
            return {"status": "error", "sku": sku, "error": str(e)}

    async def update_listing_quantity(self, sku: str, quantity: int) -> dict:
        """
        Update the quantity of an FBM listing.
        For FBA listings, inventory is managed by Amazon.
        """
        if not self.is_configured:
            return {"error": "SP-API not configured"}

        try:
            endpoint = f"/listings/2021-08-01/items/{self.seller_id}/{sku}"
            params = {"marketplaceIds": self.marketplace_id}

            patch_data = {
                "productType": "",
                "patches": [
                    {
                        "op": "replace",
                        "path": "/attributes/fulfillment_availability",
                        "value": [
                            {
                                "fulfillment_channel": "DEFAULT",
                                "quantity": quantity,
                            }
                        ],
                    }
                ],
            }

            result = await self._api_patch(endpoint, json_data=patch_data, params=params)
            return {
                "status": "ok",
                "sku": sku,
                "new_quantity": quantity,
                "details": result,
            }
        except httpx.HTTPStatusError as e:
            return {
                "status": "error",
                "sku": sku,
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
        except Exception as e:
            return {"status": "error", "sku": sku, "error": str(e)}

    async def get_listing_details(self, sku: str) -> dict:
        """Get details of a specific listing by SKU."""
        if not self.is_configured:
            return {"error": "SP-API not configured"}

        try:
            endpoint = f"/listings/2021-08-01/items/{self.seller_id}/{sku}"
            params = {
                "marketplaceIds": self.marketplace_id,
                "includedData": "summaries,attributes,offers,fulfillmentAvailability",
            }
            data = await self._api_get(endpoint, params=params)
            return {"status": "ok", "sku": sku, "details": data}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"status": "not_found", "sku": sku}
            return {"status": "error", "sku": sku, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {"status": "error", "sku": sku, "error": str(e)}

    async def batch_update_prices(self, updates: list[dict]) -> dict:
        """
        Batch update prices for multiple listings.
        Each update should have: {"sku": "...", "price": 29.99}
        """
        results = []
        success = 0
        failed = 0

        for update in updates[:50]:  # Limit to 50 per batch
            sku = update.get("sku")
            price = update.get("price")

            if not sku or price is None:
                results.append({"sku": sku, "status": "error", "error": "Missing sku or price"})
                failed += 1
                continue

            result = await self.update_listing_price(sku, float(price))
            results.append(result)

            if result.get("status") == "ok":
                success += 1
            else:
                failed += 1

            await asyncio.sleep(0.5)  # Rate limiting

        return {
            "total": len(updates[:50]),
            "success": success,
            "failed": failed,
            "results": results,
        }

    def _parse_eligibility(self, data: dict, asin: str) -> dict:
        """Parse SP-API response to determine eligibility."""
        restrictions = data.get("restrictions", [])
        summaries = data.get("summaries", [])

        has_restrictions = len(restrictions) > 0

        category = ""
        if summaries:
            for s in summaries:
                if s.get("marketplaceId") == self.marketplace_id:
                    category = s.get("productType", "")
                    break

        reasons = []
        for r in restrictions:
            reason = r.get("reason", "")
            if reason:
                reasons.append(reason)

        return {
            "asin": asin,
            "eligible": not has_restrictions,
            "requires_approval": has_restrictions,
            "restrictions": restrictions,
            "restriction_reason": "; ".join(reasons) if reasons else None,
            "category": category,
        }

    def _mock_eligibility(self, asins: list[str]) -> dict:
        """Mock eligibility check when SP-API is not configured."""
        results = {}
        for asin in asins:
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
            {"category_id": "beauty", "restricted": True, "restrictions": [{"reason": "Typically restricted - Beauty category"}]},
            {"category_id": "health_household", "restricted": True, "restrictions": [{"reason": "Typically restricted - Health category"}]},
            {"category_id": "grocery", "restricted": True, "restrictions": [{"reason": "Typically restricted - Grocery category"}]},
            {"category_id": "baby", "restricted": True, "restrictions": [{"reason": "Typically restricted - Baby category"}]},
            {"category_id": "toys_games", "restricted": True, "restrictions": [{"reason": "Seasonal restriction Oct-Jan"}]},
            {"category_id": "jewelry", "restricted": True, "restrictions": [{"reason": "Typically restricted - Jewelry category"}]},
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
