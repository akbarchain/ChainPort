from app import create_app
from app.models import db, User, Product

app = create_app()

sample_products = [
    {
        "title": "Aramid Fabric (Kevlar Equivalent)",
        "category": "textile",
        "description": "High strength aramid fabric for protective garments.",
        "price_per_unit": 850.0,
        "unit": "meter",
        "country_of_origin": "India",
        "min_order_quantity": 50,
    },
    {
        "title": "Premium Basmati Rice",
        "category": "agri",
        "description": "Aged premium basmati rice, long grain.",
        "price_per_unit": 120.0,
        "unit": "kg",
        "country_of_origin": "India",
        "min_order_quantity": 500,
    },
    {
        "title": "Industrial Plywood Sheets",
        "category": "plywood",
        "description": "Commercial grade plywood for construction.",
        "price_per_unit": 2500.0,
        "unit": "sheet",
        "country_of_origin": "Malaysia",
        "min_order_quantity": 20,
    },
]

with app.app_context():
    seller = User.query.filter_by(email="seller@chainport.com").first()
    if not seller:
        seller = User(email="seller@chainport.com", company_name="Global Industrial Traders", is_verified=True)
        seller.set_password("123456")
        db.session.add(seller)
        db.session.commit()

    for data in sample_products:
        exists = Product.query.filter_by(title=data["title"]).first()
        if not exists:
            p = Product(
                seller_id=seller.id,
                title=data["title"],
                description=data.get("description"),
                category=data.get("category"),
                price_per_unit=data.get("price_per_unit"),
                unit=data.get("unit"),
                country_of_origin=data.get("country_of_origin"),
                min_order_quantity=data.get("min_order_quantity"),
                is_active=True,
            )
            db.session.add(p)
    db.session.commit()
    print("Seeded sample products and seller (if missing).")
