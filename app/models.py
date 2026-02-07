from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app.extensions import db
from flask_login import UserMixin


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
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
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    hs_code = db.Column(db.String(20))  # Harmonized System code
    quantity = db.Column(db.Float)
    unit = db.Column(db.String(20))  # kg, tons, pieces, etc.
    price_per_unit = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="INR")
    country_of_origin = db.Column(db.String(50))
    min_order_quantity = db.Column(db.Float)
    payment_terms = db.Column(db.String(100))
    delivery_terms = db.Column(db.String(100))  # FOB, CIF, etc.
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20))
    price_per_unit = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="INR")
    status = db.Column(
        db.String(20), default="pending"
    )  # pending, escrow_deposited, in_progress, completed, cancelled, disputed
    escrow_amount = db.Column(db.Float, default=0.0)
    payment_terms = db.Column(db.String(100))
    delivery_terms = db.Column(db.String(100))
    delivery_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
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
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    trade_id = db.Column(db.Integer, db.ForeignKey("trade.id"), nullable=True)
    subject = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    sender = db.relationship(
        "User", foreign_keys=[sender_id], overlaps="sender_user,sent_messages"
    )
    receiver = db.relationship(
        "User", foreign_keys=[receiver_id], overlaps="receiver_user,received_messages"
    )
    trade = db.relationship("Trade", back_populates="messages")


class EscrowTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    trade_id = db.Column(db.Integer, db.ForeignKey("trade.id"), nullable=True)
    transaction_type = db.Column(
        db.String(20), nullable=False
    )  # deposit, withdrawal, escrow_hold, escrow_release, escrow_refund
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="INR")
    status = db.Column(db.String(20), default="completed")  # pending, completed, failed
    reference_id = db.Column(db.String(100))  # external payment reference
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewer_notes = db.Column(db.Text)
