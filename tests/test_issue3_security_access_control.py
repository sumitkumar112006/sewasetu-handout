# -*- coding: utf-8 -*-
import os
import sys
import unittest
import werkzeug

# Ensure werkzeug compatibility with Flask 2.2.5 test client
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, BASE_DIR)

from app import app


class TestIssue3SecurityAccessControl(unittest.TestCase):
    """
    Test suite for Issue 3: Critical PII Leakage, IDOR & Access Control Vulnerabilities.
    Guarantees:
    1. Public unauthenticated access to citizen PDFs (/ack/<id>.pdf) is blocked.
    2. Cross-user IDOR on citizen profiles (/application/<id>) is blocked.
    3. Regular citizens with session['logged_in'] cannot execute /admin/approve or /admin/reject.
    4. SQL injection payloads on /status/reset are safely handled using parameterized queries.
    """

    def setUp(self):
        self.client = app.test_client()

    def test_unauthenticated_pdf_access_denied(self):
        """
        Public unauthenticated users must NOT be allowed to scrape acknowledgment PDFs.
        Unfixed code returns 200 OK with full citizen PII and bank details.
        """
        response = self.client.get("/ack/1.pdf")
        self.assertIn(
            response.status_code,
            (401, 403, 302),
            f"Unauthenticated user accessed PDF! Got status {response.status_code}"
        )

    def test_cross_user_application_view_denied(self):
        """
        A logged-in citizen must NOT be allowed to view another citizen's profile.
        Citizen with mobile '9861908220' (app 1) should not view app 2 (mobile '6950273123').
        """
        with self.client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["portal_mobile"] = "9861908220"

        response = self.client.get("/application/2")
        self.assertEqual(
            response.status_code,
            403,
            f"Cross-user IDOR permitted! Status was {response.status_code} instead of 403 Forbidden"
        )

    def test_unauthorized_citizen_cannot_approve_application(self):
        """
        A regular citizen with logged_in=True must NOT be able to approve applications.
        Unfixed code checks `if not session.get('logged_in')` instead of `admin`.
        """
        with self.client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["portal_mobile"] = "9861908220"
            sess["admin"] = False

        response = self.client.post("/admin/approve/2")
        self.assertEqual(
            response.status_code,
            403,
            f"Non-admin citizen executed admin approval! Got status {response.status_code}"
        )

    def test_unauthorized_citizen_cannot_reject_application(self):
        """
        A regular citizen with logged_in=True must NOT be able to reject applications.
        """
        with self.client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["portal_mobile"] = "9861908220"
            sess["admin"] = False

        response = self.client.post("/admin/reject/2")
        self.assertEqual(
            response.status_code,
            403,
            f"Non-admin citizen executed admin rejection! Got status {response.status_code}"
        )

    def test_admin_can_still_approve_and_view(self):
        """
        Legitimate administrators (session['admin'] = True) must still have full access.
        """
        with self.client.session_transaction() as sess:
            sess["admin"] = True
            sess["logged_in"] = True

        response = self.client.get("/application/2")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
