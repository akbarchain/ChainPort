import io
import os
import re
import tempfile
import unittest

from app import create_app
from app.extensions import db
from app.models import User, Product, Trade, KYCDocument


class SecurityAndEscrowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        db_path = os.path.join(cls.tempdir.name, "test.db")
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["SECRET_KEY"] = "test-secret"

        cls.app = create_app()
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)

        cls.upload_dir = os.path.join(cls.tempdir.name, "uploads")
        os.makedirs(cls.upload_dir, exist_ok=True)
        cls.app.config["UPLOAD_FOLDER"] = cls.upload_dir

        with cls.app.app_context():
            db.drop_all()
            db.create_all()

            buyer = User(email="buyer@example.com", first_name="Buyer", escrow_balance=1000)
            buyer.set_password("password123")
            seller = User(email="seller@example.com", first_name="Seller", escrow_balance=0)
            seller.set_password("password123")
            db.session.add_all([buyer, seller])
            db.session.commit()

            product = Product(
                seller_id=seller.id,
                title="Test Product",
                price_per_unit=10,
                quantity=100,
                unit="kg",
            )
            db.session.add(product)
            db.session.commit()

            trade = Trade(
                buyer_id=buyer.id,
                seller_id=seller.id,
                product_id=product.id,
                quantity=5,
                unit="kg",
                price_per_unit=10,
                total_amount=50,
            )
            db.session.add(trade)
            db.session.commit()

        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        cls.tempdir.cleanup()

    def setUp(self):
        with self.app.app_context():
            trade = Trade.query.first()
            if trade:
                trade.status = "pending"
                trade.escrow_amount = 0
            buyer = User.query.filter_by(email="buyer@example.com").first()
            if buyer:
                buyer.escrow_balance = 1000
            db.session.commit()

    def _extract_csrf(self, html_text):
        meta = re.search(r'name="csrf-token" content="([^"]+)"', html_text)
        if meta:
            return meta.group(1)
        hidden = re.search(r'name="csrf_token".*?value="([^"]+)"', html_text)
        if hidden:
            return hidden.group(1)
        return None

    def login(self, email="buyer@example.com", password="password123"):
        r_get = self.client.get("/login")
        token = self._extract_csrf(r_get.get_data(as_text=True))
        data = {"email": email, "password": password, "csrf_token": token}
        return self.client.post("/login", data=data, follow_redirects=True)

    def test_csrf_required_for_trade_status(self):
        self.login()
        with self.app.app_context():
            trade = Trade.query.first()
            trade_id = trade.id

        # Missing CSRF should be rejected
        r = self.client.post(f"/api/trade/{trade_id}/status", json={"status": "cancelled"})
        self.assertEqual(r.status_code, 400)

        # With CSRF should succeed
        page = self.client.get(f"/trade/{trade_id}")
        token = self._extract_csrf(page.get_data(as_text=True))
        r = self.client.post(
            f"/api/trade/{trade_id}/status",
            json={"status": "cancelled"},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(r.status_code, 200)
        with self.app.app_context():
            trade = db.session.get(Trade, trade_id)
            self.assertEqual(trade.status, "cancelled")

    def test_escrow_release_requires_seller(self):
        self.login(email="buyer@example.com", password="password123")
        with self.app.app_context():
            trade = Trade.query.first()
            trade_id = trade.id

        page = self.client.get(f"/trade/{trade_id}")
        token = self._extract_csrf(page.get_data(as_text=True))

        r = self.client.post(
            f"/api/trade/{trade_id}/escrow",
            json={"action": "release"},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(r.status_code, 403)
        self.assertIn("Only seller", r.get_data(as_text=True))

    def test_escrow_deposit_cannot_exceed_trade_total(self):
        self.login(email="buyer@example.com", password="password123")
        with self.app.app_context():
            trade = Trade.query.first()
            trade_id = trade.id

        page = self.client.get(f"/trade/{trade_id}")
        token = self._extract_csrf(page.get_data(as_text=True))

        r = self.client.post(
            f"/api/trade/{trade_id}/escrow",
            json={"action": "deposit", "amount": 999},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("exceeds trade total", r.get_data(as_text=True))

    def test_kyc_uploads_are_unique_and_private(self):
        self.login(email="buyer@example.com", password="password123")

        kyc_page = self.client.get("/kyc")
        token = self._extract_csrf(kyc_page.get_data(as_text=True))

        data = {
            "csrf_token": token,
            "document_type": "passport",
            "documents": [
                (io.BytesIO(b"file1"), "id.pdf"),
                (io.BytesIO(b"file2"), "id.pdf"),
            ],
        }

        r = self.client.post("/kyc", data=data, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)

        with self.app.app_context():
            docs = KYCDocument.query.filter_by(document_type="passport").all()
            self.assertEqual(len(docs), 2)
            for doc in docs:
                self.assertNotEqual(doc.filename, doc.original_filename)
                self.assertTrue(doc.file_path.startswith(self.upload_dir))
                self.assertTrue(os.path.exists(doc.file_path))


if __name__ == "__main__":
    unittest.main()
