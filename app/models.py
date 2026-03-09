from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from collections import defaultdict
from functools import lru_cache
import os
import re
from app.extensions import db
from flask_login import UserMixin


INDUSTRY_IMAGE_MAP = {
    "agriculture": "agriculture.jpg",
    "textile": "textiles.jpg",
    "polymer_chemical": "epoxy.jpg",
    "construction_material": "cement.jpg",
    "mining_metal": "copper_cathode.jpg",
    "petrochemical": "refinery.jpg",
    "industrial_chemical": "solvent.jpg",
    "packaging": "packaging.jpg",
}

PRODUCT_IMAGE_MAP = {
    "premium basmati rice": "basmati_rice.jpg",
    "aramid fabric": "aramid_fabric.jpg",
    "kevlar fabric": "aramid_fabric.jpg",
    "nomex fabric": "aramid_fabric.jpg",
    "copper cathode": "copper_cathode.jpg",
    "coal": "copper_cathode.jpg",
    "spices": "spices.jpg",
    "pigments": "solvent.jpg",
    "concrete blocks": "cement.jpg",
    "concrete slabs": "cement.jpg",
}


def _normalize_text(value):
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _normalize_match_text(value):
    value = re.sub(r"[^a-z0-9\s]+", " ", (value or "").lower())
    return re.sub(r"\s+", " ", value).strip()


def classify_product_industry(title, category):
    """Classify a product into one of ChainPort's industry groups."""
    title_text = _normalize_text(title)
    category_text = _normalize_text(category)
    combined = f"{title_text} {category_text}".strip()
    scores = defaultdict(int)

    # High-confidence phrase matches from full title/category context.
    phrase_rules = {
        "textile": [
            "aramid fabric",
            "kevlar fiber",
            "nomex fireproof fabric",
            "fireproof fabric",
            "cotton yarn",
            "woven fabric",
            "industrial textile",
        ],
        "mining_metal": [
            "copper cathode",
            "copper cathodes",
            "thermal coal",
            "metallurgical coal",
            "iron ore",
            "bauxite ore",
        ],
        "construction_material": [
            "portland cement",
            "white portland cement",
            "concrete block",
            "concrete blocks",
            "building material",
            "construction grade",
        ],
        "polymer_chemical": [
            "epoxy resin",
            "polyurethane resin",
            "polymer resin",
            "engineering polymer",
        ],
        "industrial_chemical": [
            "industrial solvent",
            "solvent blend",
            "pigment paste",
            "inorganic pigments",
            "organic pigments",
        ],
        "petrochemical": [
            "petrochemical feedstock",
            "refinery naphtha",
            "base oil",
            "bitumen",
            "fuel oil",
        ],
        "agriculture": [
            "basmati rice",
            "raw rice",
            "agricultural commodity",
            "grain export",
            "pulse crop",
        ],
        "packaging": [
            "corrugated box",
            "kraft paper",
            "packaging film",
            "shrink wrap",
            "ldpe bags",
        ],
    }

    for industry, phrases in phrase_rules.items():
        for phrase in phrases:
            if phrase in combined:
                scores[industry] += 8

    # Token-level scoring to handle title variants.
    token_rules = {
        "agriculture": {"rice", "grain", "wheat", "maize", "corn", "soy", "pulse", "lentil", "cashew", "spice", "cottonseed"},
        "textile": {"aramid", "kevlar", "nomex", "fabric", "fiber", "fibre", "yarn", "textile", "woven", "nonwoven"},
        "polymer_chemical": {"epoxy", "polymer", "resin", "polyurethane", "polyamide", "polyester", "composite"},
        "construction_material": {"cement", "concrete", "block", "brick", "mortar", "gypsum", "clinker", "rebar", "aggregate"},
        "mining_metal": {"coal", "copper", "cathode", "ore", "aluminum", "aluminium", "zinc", "nickel", "iron", "steel"},
        "petrochemical": {"petrochemical", "refinery", "naphtha", "bitumen", "diesel", "fuel", "lpg", "benzene", "toluene"},
        "industrial_chemical": {"solvent", "pigment", "chemical", "thinner", "additive", "acid", "caustic", "surfactant"},
        "packaging": {"packaging", "pack", "box", "carton", "pallet", "wrap", "film", "container", "kraft"},
    }

    tokens = set(re.findall(r"[a-z0-9%]+", combined))
    for industry, industry_tokens in token_rules.items():
        overlap = tokens.intersection(industry_tokens)
        if overlap:
            scores[industry] += len(overlap) * 2

    # Category-based boosts.
    category_boosts = {
        "agri": "agriculture",
        "agriculture": "agriculture",
        "textile": "textile",
        "fabric": "textile",
        "construction": "construction_material",
        "building": "construction_material",
        "mining": "mining_metal",
        "metal": "mining_metal",
        "polymer": "polymer_chemical",
        "petro": "petrochemical",
        "refinery": "petrochemical",
        "chemical": "industrial_chemical",
        "packaging": "packaging",
    }

    for key, industry in category_boosts.items():
        if key in category_text:
            scores[industry] += 4

    if not scores:
        return "industrial_chemical"

    # Deterministic tie-breaker by priority.
    priority = [
        "textile",
        "mining_metal",
        "construction_material",
        "polymer_chemical",
        "petrochemical",
        "industrial_chemical",
        "agriculture",
        "packaging",
    ]
    best_score = max(scores.values())
    candidates = [industry for industry, score in scores.items() if score == best_score]
    for industry in priority:
        if industry in candidates:
            return industry
    return candidates[0]


@lru_cache(maxsize=512)
def classify_product_image(title, category):
    """Return a Flask static URL for the product image based on title/category."""
    from flask import url_for

    normalized = _normalize_match_text(f"{title or ''} {category or ''}")
    for product_key in sorted(PRODUCT_IMAGE_MAP.keys(), key=len, reverse=True):
        if _normalize_match_text(product_key) in normalized:
            filename = PRODUCT_IMAGE_MAP[product_key]
            return url_for("static", filename=f"images/products/{filename}")

    industry = classify_product_industry(title, category)
    filename = INDUSTRY_IMAGE_MAP.get(industry) or "solvent.jpg"
    return url_for("static", filename=f"images/products/{filename}")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    company_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    kyc_status = db.Column(
        db.String(20), default="pending"
    )  # pending, submitted, verified, rejected
    escrow_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    products = db.relationship("Product", backref="seller", lazy=True)
    sent_messages = db.relationship(
        "Message", foreign_keys="Message.sender_id", backref="sender_user", lazy=True
    )
    received_messages = db.relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        backref="receiver_user",
        lazy=True,
    )
    buyer_trades = db.relationship(
        "Trade", foreign_keys="Trade.buyer_id", backref="buyer_user", lazy=True
    )
    seller_trades = db.relationship(
        "Trade", foreign_keys="Trade.seller_id", backref="seller_user", lazy=True
    )
    escrow_transactions = db.relationship(
        "EscrowTransaction", backref="user", lazy=True
    )
    kyc_documents = db.relationship("KYCDocument", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), index=True)
    hs_code = db.Column(db.String(20))  # Harmonized System code
    quantity = db.Column(db.Float)
    unit = db.Column(db.String(20))  # kg, tons, pieces, etc.
    price_per_unit = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="INR")
    country_of_origin = db.Column(db.String(50), index=True)
    min_order_quantity = db.Column(db.Float)
    payment_terms = db.Column(db.String(100))
    delivery_terms = db.Column(db.String(100))  # FOB, CIF, etc.
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def image_url(self):
        """Return industry-based image URL for marketplace rendering."""
        try:
            # Prefer product-id named uploads if present
            from flask import current_app, url_for

            uploads_dir = os.path.join(current_app.static_folder, "uploads", "products")
            for ext in ("jpg", "jpeg", "png", "webp"):
                fname = f"{self.id}.{ext}"
                p = os.path.join(uploads_dir, fname)
                if os.path.exists(p):
                    return url_for("static", filename=f"uploads/products/{fname}")

            return classify_product_image(self.title, self.category)
        except Exception:
            # Safe fallback outside app context
            return "/static/images/products/solvent.jpg"


class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20))
    price_per_unit = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="INR")
    status = db.Column(
        db.String(20), default="pending", index=True
    )  # pending, escrow_deposited, in_progress, completed, cancelled, disputed
    escrow_amount = db.Column(db.Float, default=0.0)
    payment_terms = db.Column(db.String(100))
    delivery_terms = db.Column(db.String(100))
    delivery_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    buyer = db.relationship(
        "User", foreign_keys=[buyer_id], overlaps="buyer_trades,buyer_user"
    )
    seller = db.relationship(
        "User", foreign_keys=[seller_id], overlaps="seller_trades,seller_user"
    )
    product = db.relationship("Product", backref="trades")
    messages = db.relationship("Message", back_populates="trade", lazy=True)
    escrow_transactions = db.relationship(
        "EscrowTransaction", backref="trade", lazy=True
    )


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    trade_id = db.Column(db.Integer, db.ForeignKey("trade.id"), nullable=True, index=True)
    subject = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    sender = db.relationship(
        "User", foreign_keys=[sender_id], overlaps="sender_user,sent_messages"
    )
    receiver = db.relationship(
        "User", foreign_keys=[receiver_id], overlaps="receiver_user,received_messages"
    )
    trade = db.relationship("Trade", back_populates="messages")
    attachments = db.relationship("MessageAttachment", backref="message", lazy=True)


class MessageAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("message.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(100))
    file_size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class EscrowTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    trade_id = db.Column(db.Integer, db.ForeignKey("trade.id"), nullable=True, index=True)
    transaction_type = db.Column(
        db.String(20), nullable=False
    )  # deposit, withdrawal, escrow_hold, escrow_release, escrow_refund
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="INR")
    status = db.Column(db.String(20), default="completed")  # pending, completed, failed
    reference_id = db.Column(db.String(100))  # external payment reference
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class KYCDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    document_type = db.Column(
        db.String(50), nullable=False
    )  # business_license, tax_id, passport, etc.
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending, approved, rejected
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = db.Column(db.DateTime)
    reviewer_notes = db.Column(db.Text)
