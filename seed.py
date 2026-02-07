from app import create_app
from app.extensions import db
from app.models import User, Trade, Product, Message

app = create_app()

with app.app_context():
    # Create sample users
    if not User.query.filter_by(email="demo@chainport.com").first():
        demo_user = User(
            email="demo@chainport.com",
            first_name="Demo",
            last_name="User",
            company_name="Demo Trading Co",
            phone="+1234567890",
            is_verified=True,
        )
        demo_user.set_password("demo123")
        db.session.add(demo_user)

    if not User.query.filter_by(email="buyer@example.com").first():
        buyer = User(
            email="buyer@example.com",
            first_name="John",
            last_name="Buyer",
            company_name="Global Imports Ltd",
            phone="+1987654321",
            is_verified=True,
        )
        buyer.set_password("buyer123")
        db.session.add(buyer)

    if not User.query.filter_by(email="seller@example.com").first():
        seller = User(
            email="seller@example.com",
            first_name="Jane",
            last_name="Seller",
            company_name="Export Masters Inc",
            phone="+1123456789",
            is_verified=True,
        )
        seller.set_password("seller123")
        db.session.add(seller)

    db.session.commit()

    # Create sample products
    seller = User.query.filter_by(email="seller@example.com").first()
    if seller and not Product.query.first():
        products = [
            Product(
                seller_id=seller.id,
                title="Premium Basmati Rice",
                description="High-quality basmati rice from Punjab region. Long grain, aromatic, perfect for export.",
                category="Agriculture",
                hs_code="100630",
                quantity=1000.0,
                unit="tons",
                price_per_unit=1200.00,
                currency="INR",
                country_of_origin="India",
                min_order_quantity=10.0,
                payment_terms="LC at sight",
                delivery_terms="FOB Mumbai Port",
                is_active=True,
            ),
            Product(
                seller_id=seller.id,
                title="Organic Cotton Yarn",
                description="100% organic cotton yarn, carded and combed. Available in various counts.",
                category="Textiles",
                hs_code="520511",
                quantity=5000.0,
                unit="kg",
                price_per_unit=8.50,
                currency="INR",
                country_of_origin="India",
                min_order_quantity=100.0,
                payment_terms="30% advance, 70% against documents",
                delivery_terms="CIF",
                is_active=True,
            ),
            Product(
                seller_id=seller.id,
                title="Handwoven Silk Scarves",
                description="Beautiful handwoven silk scarves with traditional patterns. Perfect for fashion retailers.",
                category="Textiles",
                hs_code="621410",
                quantity=2000.0,
                unit="pieces",
                price_per_unit=25.00,
                currency="INR",
                country_of_origin="India",
                min_order_quantity=50.0,
                payment_terms="50% advance, 50% before shipment",
                delivery_terms="DDP",
                is_active=True,
            ),
            Product(
                seller_id=seller.id,
                title="Spice Blend Mix",
                description="Authentic Indian spice blend with turmeric, coriander, cumin, and other premium spices.",
                category="Agriculture",
                hs_code="091091",
                quantity=3000.0,
                unit="kg",
                price_per_unit=15.00,
                currency="INR",
                country_of_origin="India",
                min_order_quantity=25.0,
                payment_terms="TT 100%",
                delivery_terms="FOB Chennai Port",
                is_active=True,
            ),
            Product(
                seller_id=seller.id,
                title="Cashew Nuts Premium",
                description="Premium quality cashew nuts, carefully selected and processed. Available in different grades.",
                category="Agriculture",
                hs_code="080132",
                quantity=800.0,
                unit="kg",
                price_per_unit=18.00,
                currency="INR",
                country_of_origin="India",
                min_order_quantity=50.0,
                payment_terms="LC at sight",
                delivery_terms="CIF",
                is_active=True,
            ),
        ]

        for product in products:
            db.session.add(product)

    # Create sample trades
    buyer = User.query.filter_by(email="buyer@example.com").first()
    seller = User.query.filter_by(email="seller@example.com").first()

    if buyer and seller and not Trade.query.first():
        # Get the first product for the trade
        product = Product.query.first()

        trade1 = Trade(
            buyer_id=buyer.id,
            seller_id=seller.id,
            product_id=product.id if product else None,
            quantity=25.0,
            unit="tons",
            price_per_unit=1200.00,
            total_amount=30000.00,
            currency="INR",
            status="pending",
            payment_terms="LC at sight",
            delivery_terms="FOB Mumbai Port",
            notes="Looking forward to a successful partnership.",
        )
        trade2 = Trade(
            buyer_id=buyer.id,
            seller_id=seller.id,
            product_id=product.id if product else None,
            quantity=15.0,
            unit="tons",
            price_per_unit=1200.00,
            total_amount=18000.00,
            currency="INR",
            status="completed",
            payment_terms="LC at sight",
            delivery_terms="FOB Mumbai Port",
            notes="Great quality, will order more.",
        )
        db.session.add(trade1)
        db.session.add(trade2)

    db.session.commit()

    print("Sample data added successfully!")
