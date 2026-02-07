from app import create_app
from app.extensions import db
from app.models import User, Trade, Product, Message

app = create_app()

with app.app_context():
    # Create 10 diverse users (merchants, buyers, sellers)
    users_data = [
        {
            "email": "akbar.plywood@industrial.com",
            "first_name": "Akbar",
            "last_name": "Khan",
            "company_name": "Akbar Plywood Industries",
            "phone": "+91-9876543210",
            "role": "seller"
        },
        {
            "email": "rajesh.adhesives@chemical.com",
            "first_name": "Rajesh",
            "last_name": "Sharma",
            "company_name": "Rajesh Industrial Adhesives Ltd",
            "phone": "+91-9876543211",
            "role": "seller"
        },
        {
            "email": "priya.fabrics@textiles.com",
            "first_name": "Priya",
            "last_name": "Desai",
            "company_name": "Priya Fire Retardant Fabrics",
            "phone": "+91-9876543212",
            "role": "seller"
        },
        {
            "email": "vikram.fiberglass@composite.com",
            "first_name": "Vikram",
            "last_name": "Singh",
            "company_name": "Vikram Fiber Glass Manufacturing",
            "phone": "+91-9876543213",
            "role": "seller"
        },
        {
            "email": "neha.chemicals@industrial.com",
            "first_name": "Neha",
            "last_name": "Verma",
            "company_name": "Neha Industrial Chemicals Pvt Ltd",
            "phone": "+91-9876543214",
            "role": "seller"
        },
        {
            "email": "amit.paints@coatings.com",
            "first_name": "Amit",
            "last_name": "Patel",
            "company_name": "Amit Premium Paints Corporation",
            "phone": "+91-9876543215",
            "role": "seller"
        },
        {
            "email": "suresh.buyer@construction.com",
            "first_name": "Suresh",
            "last_name": "Kumar",
            "company_name": "Suresh Construction & Building Materials",
            "phone": "+91-9876543216",
            "role": "buyer"
        },
        {
            "email": "meera.merchant@wholesale.com",
            "first_name": "Meera",
            "last_name": "Gupta",
            "company_name": "Meera Wholesale Trading Enterprise",
            "phone": "+91-9876543217",
            "role": "merchant"
        },
        {
            "email": "karthik.importer@trade.com",
            "first_name": "Karthik",
            "last_name": "Reddy",
            "company_name": "Karthik Global Imports & Exports",
            "phone": "+91-9876543218",
            "role": "buyer"
        },
        {
            "email": "divya.distributor@industrial.com",
            "first_name": "Divya",
            "last_name": "Iyer",
            "company_name": "Divya Industrial Distribution Co",
            "phone": "+91-9876543219",
            "role": "merchant"
        }
    ]

    # Create users if they don't exist
    created_users = {}
    for user_data in users_data:
        if not User.query.filter_by(email=user_data["email"]).first():
            user = User(
                email=user_data["email"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                company_name=user_data["company_name"],
                phone=user_data["phone"],
                is_verified=True,
                kyc_status="verified"
            )
            user.set_password("password123")
            db.session.add(user)
            created_users[user_data["email"]] = user
        else:
            created_users[user_data["email"]] = User.query.filter_by(email=user_data["email"]).first()

    db.session.commit()
    
    # Get all users for product creation
    all_users = User.query.all()

    # Create 10 different industrial products (all in INR)
    products_data = [
        {
            "seller_email": "akbar.plywood@industrial.com",
            "title": "Premium Grade Plywood Sheets",
            "description": "High-quality plywood sheets, 12mm thickness, birch veneer. Perfect for furniture manufacturing and construction.",
            "category": "Construction Materials",
            "hs_code": "441209",
            "quantity": 5000.0,
            "unit": "sheets",
            "price_per_unit": 850.00,
            "min_order_quantity": 100.0,
            "payment_terms": "30% advance, 70% against documents",
            "delivery_terms": "FOB - Bengaluru Port"
        },
        {
            "seller_email": "rajesh.adhesives@chemical.com",
            "title": "Industrial Grade Adhesives - Multi Purpose",
            "description": "High-strength industrial adhesives suitable for wood, metal, and plastic bonding. Temperature resistant up to 120°C.",
            "category": "Chemical Products",
            "hs_code": "350910",
            "quantity": 10000.0,
            "unit": "liters",
            "price_per_unit": 250.00,
            "min_order_quantity": 50.0,
            "payment_terms": "LC at sight",
            "delivery_terms": "CIF - Chennai Port"
        },
        {
            "seller_email": "priya.fabrics@textiles.com",
            "title": "Fire Retardant Fabrics - Class A",
            "description": "Premium fire-retardant fabrics meeting international safety standards. Available in multiple colors and patterns.",
            "category": "Textiles",
            "hs_code": "590190",
            "quantity": 2000.0,
            "unit": "meters",
            "price_per_unit": 1200.00,
            "min_order_quantity": 100.0,
            "payment_terms": "50% advance, 50% before shipment",
            "delivery_terms": "FOB - Mumbai Port"
        },
        {
            "seller_email": "vikram.fiberglass@composite.com",
            "title": "Fiber Glass Reinforced Sheets",
            "description": "High-quality fiberglass sheets for industrial applications. 4mm thickness, excellent insulation properties.",
            "category": "Composite Materials",
            "hs_code": "700991",
            "quantity": 3500.0,
            "unit": "sheets",
            "price_per_unit": 650.00,
            "min_order_quantity": 50.0,
            "payment_terms": "45 days payment terms",
            "delivery_terms": "CIF - Kolkata Port"
        },
        {
            "seller_email": "neha.chemicals@industrial.com",
            "title": "Industrial Epoxy Resin - Grade A",
            "description": "Premium grade epoxy resin for coating and composite manufacturing. High purity, excellent shelf life.",
            "category": "Chemical Products",
            "hs_code": "390730",
            "quantity": 5000.0,
            "unit": "kg",
            "price_per_unit": 450.00,
            "min_order_quantity": 100.0,
            "payment_terms": "TT 100%",
            "delivery_terms": "FOB - Kandla Port"
        },
        {
            "seller_email": "neha.chemicals@industrial.com",
            "title": "Industrial Polyurethane Foam",
            "description": "Rigid polyurethane foam blocks for insulation and cushioning. Meets fire safety standards.",
            "category": "Chemical Products",
            "hs_code": "391030",
            "quantity": 8000.0,
            "unit": "kg",
            "price_per_unit": 280.00,
            "min_order_quantity": 200.0,
            "payment_terms": "30 days payment terms",
            "delivery_terms": "CIF - Cochin Port"
        },
        {
            "seller_email": "amit.paints@coatings.com",
            "title": "Premium Acrylic Industrial Paint",
            "description": "Weather-resistant acrylic paint for industrial buildings and structures. UV protected, long-lasting finish.",
            "category": "Coatings & Paints",
            "hs_code": "320900",
            "quantity": 12000.0,
            "unit": "liters",
            "price_per_unit": 420.00,
            "min_order_quantity": 100.0,
            "payment_terms": "LC at sight",
            "delivery_terms": "FOB - Mumbai Port"
        },
        {
            "seller_email": "amit.paints@coatings.com",
            "title": "Epoxy Floor Coating Paint",
            "description": "Two-component epoxy paint for factory floors and warehouses. Anti-slip, chemical resistant.",
            "category": "Coatings & Paints",
            "hs_code": "320890",
            "quantity": 6000.0,
            "unit": "liters",
            "price_per_unit": 580.00,
            "min_order_quantity": 50.0,
            "payment_terms": "45 days net",
            "delivery_terms": "CIF - Pune"
        },
        {
            "seller_email": "rajesh.adhesives@chemical.com",
            "title": "Industrial Solvents Mix",
            "description": "High-purity industrial solvents for cleaning and degreasing. Safe, effective, environmentally conscious.",
            "category": "Chemical Products",
            "hs_code": "290300",
            "quantity": 4000.0,
            "unit": "liters",
            "price_per_unit": 180.00,
            "min_order_quantity": 25.0,
            "payment_terms": "Advance 30%, 70% against documents",
            "delivery_terms": "CIF - Hazira Port"
        },
        {
            "seller_email": "vikram.fiberglass@composite.com",
            "title": "Glass Fiber Reinforced Pipes",
            "description": "GRFP pipes for industrial fluid handling. Corrosion-resistant, lightweight, durable construction.",
            "category": "Composite Materials",
            "hs_code": "700192",
            "quantity": 2500.0,
            "unit": "meters",
            "price_per_unit": 1450.00,
            "min_order_quantity": 100.0,
            "payment_terms": "LC at sight",
            "delivery_terms": "FOB - Paradip Port"
        }
    ]

    # Create products if they don't exist
    for product_data in products_data:
        seller = User.query.filter_by(email=product_data["seller_email"]).first()
        if seller and not Product.query.filter_by(title=product_data["title"]).first():
            product = Product(
                seller_id=seller.id,
                title=product_data["title"],
                description=product_data["description"],
                category=product_data["category"],
                hs_code=product_data["hs_code"],
                quantity=product_data["quantity"],
                unit=product_data["unit"],
                price_per_unit=product_data["price_per_unit"],
                currency="INR",
                country_of_origin="India",
                min_order_quantity=product_data["min_order_quantity"],
                payment_terms=product_data["payment_terms"],
                delivery_terms=product_data["delivery_terms"],
                is_active=True
            )
            db.session.add(product)

    db.session.commit()

    # Create sample trades between buyers and sellers
    buyer = User.query.filter_by(email="suresh.buyer@construction.com").first()
    seller1 = User.query.filter_by(email="akbar.plywood@industrial.com").first()
    seller2 = User.query.filter_by(email="amit.paints@coatings.com").first()

    if buyer and seller1 and not Trade.query.filter_by(buyer_id=buyer.id).first():
        # Get products for trades
        plywood_product = Product.query.filter_by(title="Premium Grade Plywood Sheets").first()
        paint_product = Product.query.filter_by(title="Premium Acrylic Industrial Paint").first()

        if plywood_product:
            trade1 = Trade(
                buyer_id=buyer.id,
                seller_id=seller1.id,
                product_id=plywood_product.id,
                quantity=200.0,
                unit="sheets",
                price_per_unit=850.00,
                total_amount=170000.00,
                currency="INR",
                status="pending",
                payment_terms="30% advance, 70% against documents",
                delivery_terms="FOB - Bengaluru Port",
                notes="Bulk order for construction project. Looking for timely delivery."
            )
            db.session.add(trade1)

        if paint_product:
            trade2 = Trade(
                buyer_id=buyer.id,
                seller_id=seller2.id,
                product_id=paint_product.id,
                quantity=500.0,
                unit="liters",
                price_per_unit=420.00,
                total_amount=210000.00,
                currency="INR",
                status="completed",
                payment_terms="LC at sight",
                delivery_terms="FOB - Mumbai Port",
                notes="Great quality paint, reliable seller. Will place repeat orders."
            )
            db.session.add(trade2)

        # Another buyer making trades
        karthik_buyer = User.query.filter_by(email="karthik.importer@trade.com").first()
        if karthik_buyer:
            adhesives_product = Product.query.filter_by(title="Industrial Grade Adhesives - Multi Purpose").first()
            if adhesives_product:
                trade3 = Trade(
                    buyer_id=karthik_buyer.id,
                    seller_id=seller2.id,
                    product_id=adhesives_product.id,
                    quantity=200.0,
                    unit="liters",
                    price_per_unit=250.00,
                    total_amount=50000.00,
                    currency="INR",
                    status="in_progress",
                    payment_terms="LC at sight",
                    delivery_terms="CIF - Chennai Port",
                    notes="Industrial project requirement. Need quality assurance certification."
                )
                db.session.add(trade3)

    db.session.commit()

    print("✅ Database seeding completed successfully!")
    print("\n📊 Created Users:")
    for user in User.query.all():
        print(f"  - {user.email} ({user.company_name})")
    
    print("\n📦 Created Products:")
    for product in Product.query.all():
        print(f"  - {product.title} (₹{product.price_per_unit}/unit) by {product.seller.company_name}")
    
    print("\n💼 Created Trades:")
    for trade in Trade.query.all():
        print(f"  - {trade.buyer.company_name} → {trade.seller.company_name}: ₹{trade.total_amount}")
