from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-this-to-a-random-secret-key"
    database_url: str = "sqlite+aiosqlite:///./fba_system.db"

    # Amazon SP-API
    amazon_marketplace_id: str = "ATVPDKIKX0DER"
    amazon_seller_id: str = ""
    amazon_sp_api_refresh_token: str = ""
    amazon_sp_api_client_id: str = ""
    amazon_sp_api_client_secret: str = ""
    amazon_sp_api_access_key: str = ""
    amazon_sp_api_secret_key: str = ""
    amazon_sp_api_role_arn: str = ""

    # Keepa
    keepa_api_key: str = ""

    # MiMo AI API
    mimo_api_key: str = ""
    mimo_api_base: str = "https://api.xiaomimimo.com/v1"
    mimo_model: str = "mimo-v2.5"

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    report_email: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Amazon FBA Fee structure (2025-2026)
FBA_FEES = {
    "small_standard": {"max_weight_oz": 6, "fee": 3.06},
    "large_standard_4oz": {"max_weight_oz": 4, "fee": 3.68},
    "large_standard_8oz": {"max_weight_oz": 8, "fee": 4.25},
    "large_standard_12oz": {"max_weight_oz": 12, "fee": 4.95},
    "large_standard_16oz": {"max_weight_oz": 16, "fee": 5.40},
    "large_standard_1_5lb": {"max_weight_oz": 24, "fee": 5.64},
    "large_standard_2lb": {"max_weight_oz": 32, "fee": 5.77},
    "large_standard_3lb": {"max_weight_oz": 48, "fee": 6.14},
    "large_standard_20lb": {"max_weight_oz": 320, "fee": 7.14 + 0.16 * 4},  # simplified
    "small_oversize": {"fee": 9.73},
    "medium_oversize": {"fee": 12.07},
    "large_oversize": {"fee": 14.95},
}

# Referral fee percentages by category
REFERRAL_FEES = {
    "automotive": 12,
    "baby": 15,
    "beauty": 15,
    "clothing": 17,
    "computers": 8,
    "electronics": 8,
    "furniture": 15,
    "grocery": 15,
    "health": 15,
    "home": 15,
    "industrial": 12,
    "jewelry": 20,
    "kitchen": 15,
    "lawn_garden": 15,
    "office": 15,
    "outdoors": 15,
    "pet": 15,
    "shoes": 15,
    "sports": 15,
    "tools": 15,
    "toys": 15,
    "video_games": 15,
    "other": 15,
}

# Storage fees per cubic foot
STORAGE_FEE_STANDARD = 0.87  # Jan-Sep
STORAGE_FEE_Q4 = 2.40        # Oct-Dec
STORAGE_FEE_OVERSIZE_STANDARD = 0.56
STORAGE_FEE_OVERSIZE_Q4 = 1.40
