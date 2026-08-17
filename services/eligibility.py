"""
Seller Eligibility - Track which categories the seller can sell in.
Simple system that works without SP-API - user manually configures their approved categories.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import Setting


# All Amazon categories with their typical restriction status
AMAZON_CATEGORIES = {
    "home_kitchen": {
        "name": "Home & Kitchen",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "tools_home_improvement": {
        "name": "Tools & Home Improvement",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "sports_outdoors": {
        "name": "Sports & Outdoors",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "pet_supplies": {
        "name": "Pet Supplies",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "office_products": {
        "name": "Office Products",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "electronics": {
        "name": "Electronics",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "computers": {
        "name": "Computers",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "clothing": {
        "name": "Clothing & Accessories",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "shoes": {
        "name": "Shoes & Handbags",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "automotive": {
        "name": "Automotive",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "beauty": {
        "name": "Beauty & Personal Care",
        "typically_open": False,
        "approval_difficulty": "medium",
    },
    "health_household": {
        "name": "Health & Household",
        "typically_open": False,
        "approval_difficulty": "medium",
    },
    "baby": {
        "name": "Baby Products",
        "typically_open": False,
        "approval_difficulty": "medium",
    },
    "grocery": {
        "name": "Grocery & Gourmet Food",
        "typically_open": False,
        "approval_difficulty": "hard",
    },
    "toys_games": {
        "name": "Toys & Games",
        "typically_open": False,
        "approval_difficulty": "medium",
        "note": "Seasonal restriction Oct-Jan",
    },
    "jewelry": {
        "name": "Jewelry",
        "typically_open": False,
        "approval_difficulty": "hard",
    },
    "watches": {
        "name": "Watches",
        "typically_open": False,
        "approval_difficulty": "medium",
    },
    "luggage": {
        "name": "Backpacks, Handbags & Luggage",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "musical_instruments": {
        "name": "Musical Instruments",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
    "industrial": {
        "name": "Industrial & Scientific",
        "typically_open": True,
        "approval_difficulty": "easy",
    },
}


class EligibilityService:
    """Manage seller category eligibility."""

    @staticmethod
    async def get_approved_categories(db: AsyncSession) -> list[str]:
        """Get list of approved category IDs from database."""
        result = await db.execute(
            select(Setting).where(Setting.key == "approved_categories")
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            return setting.value.split(",")
        # Default: all typically open categories
        return [k for k, v in AMAZON_CATEGORIES.items() if v.get("typically_open")]

    @staticmethod
    async def set_approved_categories(db: AsyncSession, categories: list[str]):
        """Save approved categories to database."""
        result = await db.execute(
            select(Setting).where(Setting.key == "approved_categories")
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = ",".join(categories)
        else:
            setting = Setting(key="approved_categories", value=",".join(categories))
            db.add(setting)
        await db.commit()

    @staticmethod
    def categorize_product(product: dict) -> str:
        """Determine which category a product belongs to based on its data."""
        title = (product.get("title", "") or "").lower()
        category = (product.get("category", "") or "").lower()
        brand = (product.get("brand", "") or "").lower()

        # Category detection based on keywords
        category_keywords = {
            "beauty": ["skincare", "moisturizer", "serum", "cream", "mask", "toner", "cleanser",
                       "makeup", "lipstick", "foundation", "mascara", "beauty", "cosmetic",
                       "collagen", "hyaluronic", "vitamin c serum", "retinol"],
            "health_household": ["vitamin", "supplement", "protein", "probiotic", "pain relief",
                                 "first aid", "medicine", "health", "wellness", "multivitamin",
                                 "cleaning", "detergent", "disinfectant", "laundry"],
            "grocery": ["coffee", "tea", "snack", "food", "organic", "k-cup", "pod", "chocolate",
                        "candy", "nut", "granola", "protein bar", "gummy", "vitamin gummy"],
            "baby": ["diaper", "wipe", "baby", "infant", "toddler", "nursing", "pacifier",
                     "formula", "baby food", "stroller", "car seat"],
            "toys_games": ["toy", "game", "puzzle", "lego", "action figure", "doll",
                           "board game", "card game", "nerf", "hot wheels"],
            "pet_supplies": ["dog", "cat", "pet", "dog food", "cat food", "pet toy",
                             "leash", "collar", "pet bed", "litter"],
            "home_kitchen": ["kitchen", "cookware", "utensil", "plate", "cup", "mug",
                             "towel", "sheet", "pillow", "blanket", "curtain", "rug",
                             "container", "storage", "organizer", "shelf"],
            "tools_home_improvement": ["tool", "drill", "saw", "hammer", "screwdriver",
                                        "wrench", "paint", "lumber", "hardware", "LED",
                                        "light", "fixture", "outlet", "switch"],
            "sports_outdoors": ["exercise", "workout", "fitness", "yoga", "camping",
                                "hiking", "fishing", "sport", "ball", "glove", "tent",
                                "backpack", "water bottle", "bicycle"],
            "electronics": ["charger", "cable", "phone case", "headphone", "speaker",
                            "camera", "battery", "power bank", "adapter", "USB"],
            "office_products": ["pen", "pencil", "paper", "notebook", "stapler", "tape",
                                "folder", "binder", "desk", "chair", "office"],
            "automotive": ["car", "vehicle", "tire", "oil", "wiper", "floor mat",
                           "car charger", "dash cam", "sunshade", "car cover"],
            "clothing": ["shirt", "pants", "dress", "jacket", "sock", "underwear",
                         "hat", "glove", "scarf", "belt"],
        }

        # Check title and category for matches
        for cat_id, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in title or keyword in category:
                    return cat_id

        # Default to home_kitchen if can't determine
        return "home_kitchen"

    @staticmethod
    async def filter_approved_products(products: list, db: AsyncSession) -> tuple[list, list]:
        """
        Filter products into approved and restricted lists.
        Returns (approved, restricted) tuple.
        """
        approved_cats = await EligibilityService.get_approved_categories(db)

        approved = []
        restricted = []

        for product in products:
            cat_id = EligibilityService.categorize_product(product)
            cat_info = AMAZON_CATEGORIES.get(cat_id, {})

            product["_category_id"] = cat_id
            product["_category_name"] = cat_info.get("name", "Unknown")

            if cat_id in approved_cats:
                product["_eligibility"] = "approved"
                approved.append(product)
            else:
                product["_eligibility"] = "restricted"
                product["_approval_difficulty"] = cat_info.get("approval_difficulty", "unknown")
                restricted.append(product)

        return approved, restricted

    @staticmethod
    def get_all_categories() -> dict:
        """Get all categories with their info."""
        return AMAZON_CATEGORIES


eligibility_service = EligibilityService()
