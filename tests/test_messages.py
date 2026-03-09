import os
import re
import tempfile
import unittest

from app import create_app
from app.extensions import db
from app.models import Message, Trade, User


class MessageFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        db_path = os.path.join(cls.tempdir.name, "messages-test.db")
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["SECRET_KEY"] = "messages-test-secret"

        cls.app = create_app()
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            db.drop_all()
            db.create_all()
            u1 = User(email="sender@example.com", first_name="Sender")
            u1.set_password("password123")
            u2 = User(email="receiver@example.com", first_name="Receiver")
            u2.set_password("password123")
            db.session.add_all([u1, u2])
            db.session.commit()

            trade = Trade(
                buyer_id=u1.id,
                seller_id=u2.id,
                product_id=None,
                quantity=1,
                unit="pcs",
                price_per_unit=10,
                total_amount=10,
            )
            db.session.add(trade)
            db.session.commit()

            cls.sender_id = u1.id
            cls.receiver_id = u2.id
            cls.trade_id = trade.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        cls.tempdir.cleanup()

    def _extract_csrf(self, html_text):
        meta = re.search(r'name="csrf-token" content="([^"]+)"', html_text)
        if meta:
            return meta.group(1)
        hidden = re.search(r'name="csrf_token".*?value="([^"]+)"', html_text)
        if hidden:
            return hidden.group(1)
        return None

    def login(self):
        page = self.client.get("/login")
        token = self._extract_csrf(page.get_data(as_text=True))
        return self.client.post(
            "/login",
            data={"email": "sender@example.com", "password": "password123", "csrf_token": token},
            follow_redirects=False,
        )

    def test_start_message_by_user_id_redirects_to_thread(self):
        self.login()
        page = self.client.get("/messages")
        token = self._extract_csrf(page.get_data(as_text=True))
        resp = self.client.post(
            "/messages/start",
            data={"csrf_token": token, "user_id": str(self.receiver_id)},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(f"/messages?user_id={self.receiver_id}", resp.location)

    def test_send_message_invalid_receiver_is_handled(self):
        self.login()
        page = self.client.get("/messages")
        token = self._extract_csrf(page.get_data(as_text=True))
        with self.app.app_context():
            before = Message.query.count()
        resp = self.client.post(
            "/send-message",
            data={"csrf_token": token, "receiver_id": "abc", "content": "hello"},
            follow_redirects=False,
        )
        with self.app.app_context():
            after = Message.query.count()
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/messages", resp.location)
        self.assertEqual(before, after)

    def test_send_message_redirects_back_to_selected_thread(self):
        self.login()
        page = self.client.get(f"/messages?user_id={self.receiver_id}")
        token = self._extract_csrf(page.get_data(as_text=True))
        resp = self.client.post(
            "/send-message",
            data={
                "csrf_token": token,
                "receiver_id": str(self.receiver_id),
                "trade_id": str(self.trade_id),
                "subject": "Test",
                "content": "Message body",
            },
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(f"/messages?user_id={self.receiver_id}", resp.location)
        with self.app.app_context():
            latest = Message.query.order_by(Message.id.desc()).first()
            self.assertIsNotNone(latest)
            self.assertEqual(latest.sender_id, self.sender_id)
            self.assertEqual(latest.receiver_id, self.receiver_id)


if __name__ == "__main__":
    unittest.main()
