from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asin = Column(String(20), unique=True, index=True)
    title = Column(String(500))
    brand = Column(String(200))
    category = Column(String(100))
    image_url = Column(Text, default="")
    amazon_price = Column(Float, default=0)
    bsr = Column(Integer, default=0)
    bsr_category = Column(String(100), default="")
    fba_seller_count = Column(Integer, default=0)
    fbm_seller_count = Column(Integer, default=0)
    is_amazon_seller = Column(Boolean, default=False)
    monthly_sales_est = Column(Integer, default=0)
    review_count = Column(Integer, default=0)
    rating = Column(Float, default=0)
    weight_lbs = Column(Float, default=0)
    dimensions = Column(String(100), default="")
    upc = Column(String(20), default="")
    ean = Column(String(20), default="")
    referral_fee_pct = Column(Float, default=15)
    fba_fee = Column(Float, default=0)
    storage_fee_monthly = Column(Float, default=0)
    keepa_data = Column(JSON, default=dict)
    status = Column(String(20), default="active")  # active, paused, archived
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    supplier_products = relationship("SupplierProduct", back_populates="product", cascade="all, delete-orphan")
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
    inventory_items = relationship("InventoryItem", back_populates="product", cascade="all, delete-orphan")

    @property
    def roi(self):
        best = self.best_supplier_price
        if best and best > 0 and self.amazon_price > 0:
            total_cost = best + (self.fba_fee or 0) + (self.storage_fee_monthly or 0) + 0.40
            referral = self.amazon_price * (self.referral_fee_pct or 15) / 100
            profit = self.amazon_price - referral - total_cost
            return round((profit / best) * 100, 1) if best > 0 else 0
        return 0

    @property
    def net_profit(self):
        best = self.best_supplier_price
        if best and best > 0 and self.amazon_price > 0:
            total_cost = best + (self.fba_fee or 0) + (self.storage_fee_monthly or 0) + 0.40
            referral = self.amazon_price * (self.referral_fee_pct or 15) / 100
            return round(self.amazon_price - referral - total_cost, 2)
        return 0

    @property
    def best_supplier_price(self):
        if self.supplier_products:
            return min(sp.cost for sp in self.supplier_products if sp.cost > 0)
        return None

    @property
    def is_profitable(self):
        return self.roi >= 20 and self.net_profit >= 3


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    contact_name = Column(String(200), default="")
    email = Column(String(200), default="")
    phone = Column(String(50), default="")
    website = Column(String(300), default="")
    address = Column(Text, default="")
    supplier_type = Column(String(50), default="distributor")  # distributor, brand_direct, retailer
    payment_terms = Column(String(100), default="")
    min_order = Column(Float, default=0)
    notes = Column(Text, default="")
    resale_cert_registered = Column(Boolean, default=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    supplier_products = relationship("SupplierProduct", back_populates="supplier", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier", cascade="all, delete-orphan")


class SupplierProduct(Base):
    __tablename__ = "supplier_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    supplier_sku = Column(String(100), default="")
    cost = Column(Float, nullable=False)
    moq = Column(Integer, default=1)  # Minimum Order Quantity
    lead_time_days = Column(Integer, default=7)
    in_stock = Column(Boolean, default=True)
    last_price_update = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, default="")

    # Relationships
    supplier = relationship("Supplier", back_populates="supplier_products")
    product = relationship("Product", back_populates="supplier_products")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    amazon_price = Column(Float)
    bsr = Column(Integer)
    fba_seller_count = Column(Integer)
    fbm_seller_count = Column(Integer)
    buy_box_price = Column(Float)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="price_history")


class InventoryItem(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity_fba = Column(Integer, default=0)
    quantity_inbound = Column(Integer, default=0)  # Enviado a Amazon, no recibido aun
    quantity_local = Column(Integer, default=0)     # En tu almacen/local
    reorder_point = Column(Integer, default=10)
    reorder_quantity = Column(Integer, default=50)
    avg_cost = Column(Float, default=0)             # Costo promedio por unidad
    total_invested = Column(Float, default=0)
    last_restock_date = Column(DateTime, default=None)
    days_of_stock = Column(Integer, default=0)
    status = Column(String(20), default="in_stock")  # in_stock, low_stock, out_of_stock, overstock
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="inventory_items")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_number = Column(String(50), unique=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    status = Column(String(30), default="draft")  # draft, submitted, received, cancelled
    total_amount = Column(Float, default=0)
    items_count = Column(Integer, default=0)
    order_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expected_date = Column(DateTime, default=None)
    received_date = Column(DateTime, default=None)
    tracking_number = Column(String(100), default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    supplier = relationship("Supplier", back_populates="purchase_orders")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    received_quantity = Column(Integer, default=0)

    purchase_order = relationship("PurchaseOrder", back_populates="items")
    product = relationship("Product")


class ScanResult(Base):
    __tablename__ = "scan_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_name = Column(String(200), default="")
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    total_products_scanned = Column(Integer, default=0)
    profitable_found = Column(Integer, default=0)
    marginal_found = Column(Integer, default=0)
    not_profitable = Column(Integer, default=0)
    avg_roi = Column(Float, default=0)
    scan_data = Column(JSON, default=list)  # Full results
    status = Column(String(20), default="completed")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    alert_type = Column(String(50), nullable=False)  # price_drop, price_increase, low_stock, out_of_stock, new_competitor, buy_box_lost
    severity = Column(String(20), default="info")  # info, warning, critical
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product")


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class BrandApproval(Base):
    __tablename__ = "brand_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_name = Column(String(200), nullable=False)
    category = Column(String(100), default="")
    status = Column(String(30), default="pending")  # pending, submitted, approved, rejected
    amazon_request_url = Column(Text, default="")
    requirements = Column(Text, default="")  # What Amazon requires
    invoice_sent = Column(Boolean, default=False)
    invoice_date = Column(DateTime, default=None)
    invoice_supplier = Column(String(200), default="")
    invoice_units = Column(Integer, default=0)
    contact_email = Column(String(200), default="")
    contact_phone = Column(String(50), default="")
    submitted_at = Column(DateTime, default=None)
    resolved_at = Column(DateTime, default=None)
    notes = Column(Text, default="")
    priority = Column(String(20), default="medium")  # low, medium, high
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
