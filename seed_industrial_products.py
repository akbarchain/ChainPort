import io
from pathlib import Path
from urllib.parse import quote_plus

import requests
from PIL import Image

from app import create_app
from app.extensions import db
from app.models import Product, User


SELLER_EMAIL = "seller@chainport.com"
SELLER_PASSWORD = "123456"

DEMO_TITLES = {
    "premium basmati rice",
}

INDUSTRIAL_PRODUCTS = [
    {"title": "Carbon Fiber Tow", "category": "textile", "unit": "kg", "price_per_unit": 1800, "min_order_quantity": 50},
    {"title": "Kevlar Fiber", "category": "textile", "unit": "kg", "price_per_unit": 2200, "min_order_quantity": 25},
    {"title": "Nomex Fire Resistant Fabric", "category": "textile", "unit": "meter", "price_per_unit": 950, "min_order_quantity": 100},
    {"title": "Fiberglass Reinforced Pipes", "category": "construction", "unit": "meter", "price_per_unit": 1500, "min_order_quantity": 30},
    {"title": "Epoxy Resin Industrial Grade", "category": "polymer", "unit": "kg", "price_per_unit": 350, "min_order_quantity": 200},
    {"title": "Copper Cathode 99.99%", "category": "metal", "unit": "ton", "price_per_unit": 820000, "min_order_quantity": 1},
    {"title": "Portland Cement OPC 53", "category": "construction", "unit": "bag", "price_per_unit": 420, "min_order_quantity": 500},
    {"title": "Industrial Pigment Powder", "category": "chemical", "unit": "kg", "price_per_unit": 280, "min_order_quantity": 100},
    {"title": "Thermal Coal", "category": "mining", "unit": "ton", "price_per_unit": 9800, "min_order_quantity": 50},
    {"title": "Performance Chemical Surfactant", "category": "chemical", "unit": "kg", "price_per_unit": 410, "min_order_quantity": 120},
]

TITLE_TO_CATEGORY = {item["title"]: item["category"] for item in INDUSTRIAL_PRODUCTS}
CATEGORY_FALLBACK_IMAGE = {
    "textile": "textiles.jpg",
    "construction": "cement.jpg",
    "polymer": "epoxy.jpg",
    "metal": "copper_cathode.jpg",
    "mining": "copper_cathode.jpg",
    "chemical": "solvent.jpg",
}


def ensure_seller():
    seller = User.query.filter_by(email=SELLER_EMAIL).first()
    if seller:
        return seller

    seller = User(
        email=SELLER_EMAIL,
        first_name="Industrial",
        last_name="Seller",
        company_name="ChainPort Industrial Exports",
        phone="+91-9000000000",
        is_verified=True,
        is_active=True,
    )
    seller.set_password(SELLER_PASSWORD)
    db.session.add(seller)
    db.session.commit()
    return seller


def remove_demo_products():
    removed = 0
    for product in Product.query.all():
        title = (product.title or "").strip().lower()
        category = (product.category or "").strip().lower()
        if title in DEMO_TITLES or category in {"agri", "agriculture"}:
            db.session.delete(product)
            removed += 1

    if removed:
        db.session.commit()
    return removed


def download_image(product_name, product_id):
    uploads_dir = Path("app/static/uploads/products")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    output_path = uploads_dir / f"{product_id}.jpg"

    if output_path.exists():
        print(f"[skip] image exists for #{product_id}: {output_path.name}")
        return

    query = quote_plus(f"{product_name},industrial")
    unsplash_url = f"https://source.unsplash.com/800x600/?{query}"

    image_bytes = None
    try:
        response = requests.get(unsplash_url, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
    except requests.RequestException as exc:
        print(f"[warn] Unsplash Source failed for #{product_id} {product_name}: {exc}")
        picsum_url = f"https://picsum.photos/seed/{query}/800/600"
        try:
            response = requests.get(picsum_url, timeout=30)
            response.raise_for_status()
            image_bytes = response.content
            print(f"[ok] Picsum fallback download for #{product_id}")
        except requests.RequestException as picsum_exc:
            print(f"[error] fallback download failed for #{product_id} {product_name}: {picsum_exc}")
            _save_local_fallback_image(product_name, output_path)
            return

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        resampling = getattr(Image, "Resampling", Image)
        image.thumbnail((800, 800), resampling.LANCZOS)
        image.save(output_path, format="JPEG", quality=90, optimize=True)
        print(f"[ok] image downloaded for #{product_id}: {output_path.name}")
    except Exception as exc:
        print(f"[error] image processing failed for #{product_id} {product_name}: {exc}")
        _save_local_fallback_image(product_name, output_path)


def _save_local_fallback_image(product_name, output_path):
    category = TITLE_TO_CATEGORY.get(product_name, "chemical")
    fallback_name = CATEGORY_FALLBACK_IMAGE.get(category, "solvent.jpg")
    fallback_path = Path("app/static/images/products") / fallback_name
    if not fallback_path.exists():
        return

    try:
        image = Image.open(fallback_path).convert("RGB")
        resampling = getattr(Image, "Resampling", Image)
        image.thumbnail((800, 800), resampling.LANCZOS)
        image.save(output_path, format="JPEG", quality=90, optimize=True)
        print(f"[ok] fallback image used for {product_name}: {fallback_name}")
    except Exception as exc:
        print(f"[error] fallback image failed for {product_name}: {exc}")


def upsert_products(seller):
    for item in INDUSTRIAL_PRODUCTS:
        product = Product.query.filter(
            db.func.lower(Product.title) == item["title"].lower()
        ).first()

        if not product:
            product = Product(
                seller_id=seller.id,
                title=item["title"],
                is_active=True,
            )
            db.session.add(product)

        product.seller_id = seller.id
        product.title = item["title"]
        product.category = item["category"]
        product.price_per_unit = item["price_per_unit"]
        product.unit = item["unit"]
        product.min_order_quantity = item["min_order_quantity"]
        product.country_of_origin = "India"
        product.payment_terms = "LC / TT"
        product.delivery_terms = "FOB"
        product.description = f"{item['title']} supplied for industrial B2B trade."
        product.currency = "INR"
        product.is_active = True

        db.session.commit()
        print(f"[ok] product upserted #{product.id}: {product.title}")
        download_image(product.title, product.id)


def main():
    app = create_app()
    with app.app_context():
        db.create_all()

        removed = remove_demo_products()
        if removed:
            print(f"[ok] removed demo/agriculture products: {removed}")
        else:
            print("[ok] no demo/agriculture products found")

        seller = ensure_seller()
        print(f"[ok] seller ready: {seller.email}")

        upsert_products(seller)

    print("\nRun command:")
    print("python seed_industrial_products.py")


if __name__ == "__main__":
    main()
