"""
Download product images from Unsplash Source API based on Product.title.

Usage:
    python -m app.utils.download_product_images
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.parse import quote_plus
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    import requests
    from requests import RequestException
except ImportError:  # pragma: no cover - exercised in non-requests environments
    requests = None

    class RequestException(Exception):
        pass


# Ensure project root is importable when executed as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app  # noqa: E402
from app.models import Product  # noqa: E402


UNSPLASH_SOURCE_TEMPLATE = "https://source.unsplash.com/800x600/?{query}"
FALLBACK_SOURCE_TEMPLATE = "https://loremflickr.com/800/600/{query}"
REQUEST_TIMEOUT = (5, 20)  # (connect timeout, read timeout)
CHUNK_SIZE = 8192
MAX_RETRIES = 2


def _normalized_query(title: str) -> str:
    """Return a URL-safe query for Unsplash Source API."""
    compact = " ".join((title or "").split())
    return quote_plus(compact)


def _normalized_fallback_query(title: str) -> str:
    compact = " ".join((title or "").split())
    # loremflickr supports comma-separated terms
    return ",".join(compact.lower().split())


def _download_image(url: str, destination: Path) -> None:
    """Download an image from URL and write it atomically."""
    temp_path = destination.with_suffix(destination.suffix + ".tmp")

    if requests is not None:
        with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            if content_type and "image" not in content_type.lower():
                raise ValueError(f"Unexpected response content type: {content_type}")

            with temp_path.open("wb") as file_handle:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        file_handle.write(chunk)
        temp_path.replace(destination)
        return

    req = Request(url, headers={"User-Agent": "ChainPort/1.0"})
    with urlopen(req, timeout=REQUEST_TIMEOUT[1]) as response:
        content_type = response.headers.get("Content-Type", "")
        if content_type and "image" not in content_type.lower():
            raise ValueError(f"Unexpected response content type: {content_type}")
        with temp_path.open("wb") as file_handle:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                file_handle.write(chunk)
    temp_path.replace(destination)


def _download_with_retry(urls: list[str], destination: Path) -> None:
    """Try downloading from each URL with bounded retries."""
    last_error = None
    for url in urls:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                _download_image(url, destination)
                return
            except (RequestException, URLError, OSError, ValueError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    time.sleep(1.0)
                continue
    if last_error:
        raise last_error
    raise RuntimeError("Unknown download failure")


def main() -> None:
    app = create_app()

    downloaded = 0
    skipped = 0
    failed = 0

    with app.app_context():
        output_dir = Path(app.static_folder) / "images" / "products"
        output_dir.mkdir(parents=True, exist_ok=True)

        products = Product.query.order_by(Product.id.asc()).all()
        if not products:
            print("No products found in database.")
            return

        for product in products:
            filename = output_dir / f"product_{product.id}.jpg"
            title = (product.title or "").strip()

            if filename.exists():
                print(f"[SKIP] product_{product.id}.jpg already exists")
                skipped += 1
                continue

            if not title:
                print(f"[SKIP] Product {product.id} has empty title")
                skipped += 1
                continue

            query = _normalized_query(title)
            fallback_query = _normalized_fallback_query(title)
            urls = [
                UNSPLASH_SOURCE_TEMPLATE.format(query=query),
                FALLBACK_SOURCE_TEMPLATE.format(query=fallback_query),
            ]

            try:
                _download_with_retry(urls, filename)
                print(f"[OK] Downloaded product_{product.id}.jpg for: {title}")
                downloaded += 1
            except (RequestException, URLError, OSError, ValueError) as exc:
                print(f"[ERROR] Product {product.id} ({title}): {exc}")
                failed += 1

    print(
        f"Done. Downloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}"
    )


if __name__ == "__main__":
    main()
