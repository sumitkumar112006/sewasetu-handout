import os
import sys
import unittest
import io
from datetime import datetime, date
from unittest.mock import patch
import werkzeug

# Ensure werkzeug compatibility with Flask 2.2.5 test client
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "utils"))

from app import app, get_db


class TestIssue5CancellationAndUX(unittest.TestCase):
    """
    Test suite for Issue 5: Self-Serve Cancellation, Duplicate Re-application, and Form UX Fixes.
    Guarantees:
    1. Citizens can self-cancel a PENDING application from the status portal.
    2. Cancelled/rejected applications do NOT block citizens from re-applying (duplicate check).
    3. Indian date format (DD/MM/YYYY) is prioritized over US format (MM/DD/YYYY).
    4. Widowed applicants are not blocked by requiring a deceased husband's employer.
    5. Document uploads accept JPG and PDF up to 5 MB with user-friendly errors.
    """

    def setUp(self):
        self.client = app.test_client()
        app.config["TESTING"] = True
        app.secret_key = "test-secret-key"

    def test_self_serve_cancellation_of_pending_application(self):
        """
        An authenticated citizen can cancel their own PENDING application.
        The application status updates to 'CANCELLED' with decided_by='APPLICANT'.
        """
        # Insert a test pending application
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO applications
               (application_no, applicant_name, mobile, dob, village, block, bank_account, ifsc, status, submitted_at)
               VALUES ('TEST-CANC-01', 'Biren Das', '9899001122', '1952-04-10', 'Sonapur', 'Sonari', '11223344', 'SBIN0001', 'PENDING', %s)
               RETURNING id""",
            (datetime.now(),)
        )
        test_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        try:
            # Login as the citizen
            with self.client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["portal_mobile"] = "9899001122"

            # POST to cancel endpoint
            resp = self.client.post(f"/application/{test_id}/cancel", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)

            # Verify database record updated
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT status, decided_by FROM applications WHERE id = %s", (test_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()

            self.assertEqual(row[0], "CANCELLED", f"Expected status 'CANCELLED', got '{row[0]}'")
            self.assertEqual(row[1], "APPLICANT", f"Expected decided_by 'APPLICANT', got '{row[1]}'")
        finally:
            # Cleanup
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM applications WHERE application_no = 'TEST-CANC-01'")
            conn.commit()
            cur.close()
            conn.close()

    def test_duplicate_check_allows_reapplication_after_cancellation(self):
        """
        If a citizen's prior application was CANCELLED or REJECTED, they must be allowed
        to submit a new application with the same mobile number.
        """
        conn = get_db()
        cur = conn.cursor()
        # Seed an existing cancelled application
        cur.execute(
            """INSERT INTO applications
               (application_no, applicant_name, mobile, dob, village, block, bank_account, ifsc, status, submitted_at)
               VALUES ('TEST-CANC-02', 'Biren Das', '9899003344', '1952-04-10', 'Sonapur', 'Sonari', '11223344', 'SBIN0001', 'CANCELLED', %s)
               RETURNING id""",
            (datetime.now(),)
        )
        conn.commit()
        cur.close()
        conn.close()

        try:
            with self.client.session_transaction() as sess:
                sess["verified_mobile"] = "9899003344"
                sess["form_data"] = {
                    "applicant_name": "Biren Das",
                    "village": "Sonapur",
                    "block": "Sonari",
                    "gender": "Male",
                    "marital_status": "Married",
                    "bank_account": "1122334455",
                    "ifsc": "SBIN0001234",
                    "dob": "10/04/1952",
                }
                sess["doc_path"] = "/tmp/dummy.pdf"

            with patch("app.send_sms"), patch("app.generate_acknowledgment", return_value=b"%PDF-test"):
                resp = self.client.post("/declaration", follow_redirects=True)
                self.assertEqual(resp.status_code, 200)
                # Should not be redirected to index with "Duplicate applications are not permitted"
                self.assertNotIn(b"Duplicate applications are not permitted", resp.data)
                self.assertIn(b"Application Submitted", resp.data)
        finally:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM applications WHERE mobile = '9899003344'")
            cur.execute("DELETE FROM portal_users WHERE mobile = '9899003344'")
            conn.commit()
            cur.close()
            conn.close()

    def test_indian_date_format_prioritized_over_us_format(self):
        """
        Entering '05/06/1950' must parse as June 5, 1950 (DD/MM/YYYY), NOT May 6, 1950.
        Portal login password must be '05061950'.
        """
        with self.client.session_transaction() as sess:
            sess["verified_mobile"] = "9899005566"
            sess["form_data"] = {
                "applicant_name": "Ramen Baruah",
                "village": "Sonapur",
                "block": "Sonari",
                "gender": "Male",
                "marital_status": "Married",
                "bank_account": "9988776655",
                "ifsc": "SBIN0001234",
                "dob": "05/06/1950",  # 5th June 1950
            }
            sess["doc_path"] = "/tmp/dummy.pdf"

        try:
            with patch("app.send_sms"), patch("app.generate_acknowledgment", return_value=b"%PDF-test"):
                resp = self.client.post("/declaration", follow_redirects=True)
                self.assertEqual(resp.status_code, 200)

            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT dob FROM applications WHERE mobile = '9899005566'")
            row = cur.fetchone()
            cur.close()
            conn.close()

            self.assertIsNotNone(row, "Application was not inserted")
            # Must be June 5, 1950 (1950-06-05)
            self.assertEqual(
                str(row[0]),
                "1950-06-05",
                f"Date was parsed as US format {row[0]} instead of Indian format 1950-06-05!"
            )
        finally:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM applications WHERE mobile = '9899005566'")
            cur.execute("DELETE FROM portal_users WHERE mobile = '9899005566'")
            conn.commit()
            cur.close()
            conn.close()

    def test_widow_not_blocked_by_husband_employer_requirement(self):
        """
        A widowed applicant providing husband_name but leaving husband_employer blank
        must NOT be rejected.
        """
        with self.client.session_transaction() as sess:
            sess["verified_mobile"] = "9899007788"
            sess["form_data"] = {
                "applicant_name": "Amina Begum",
                "village": "Sonapur",
                "block": "Sonari",
                "gender": "Female",
                "marital_status": "Widowed",
                "husband_name": "Late Ali Ahmed",
                "husband_employer": "",  # Empty because husband is deceased
                "bank_account": "4455667788",
                "ifsc": "SBIN0001234",
                "dob": "12/08/1951",
            }
            sess["doc_path"] = "/tmp/dummy.pdf"

        try:
            with patch("app.send_sms"), patch("app.generate_acknowledgment", return_value=b"%PDF-test"):
                resp = self.client.post("/declaration", follow_redirects=True)
                self.assertEqual(resp.status_code, 200)
                self.assertNotIn(b"Something went wrong", resp.data)
                self.assertIn(b"Application Submitted", resp.data)
        finally:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM applications WHERE mobile = '9899007788'")
            cur.execute("DELETE FROM portal_users WHERE mobile = '9899007788'")
            conn.commit()
            cur.close()
            conn.close()

    def test_upload_accepts_jpg_and_informative_error_messages(self):
        """
        Upload must accept .jpg documents and provide user-friendly error messages
        instead of cryptic 'ERR_VAL_47'.
        """
        with self.client.session_transaction() as sess:
            sess["verified_mobile"] = "9899009900"

        # 1. Test JPG upload succeeds
        jpg_data = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 500)
        resp = self.client.post(
            "/upload",
            data={"document": (jpg_data, "voter_id.jpg")},
            follow_redirects=True,
            content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b"ERR_VAL_47", resp.data)
        self.assertIn(b"Declaration", resp.data)

        # 2. Test invalid extension has user-friendly message, not ERR_VAL_47
        with self.client.session_transaction() as sess:
            sess["verified_mobile"] = "9899009900"

        txt_data = io.BytesIO(b"random text")
        resp_invalid = self.client.post(
            "/upload",
            data={"document": (txt_data, "document.txt")},
            follow_redirects=True,
            content_type="multipart/form-data"
        )
        self.assertNotIn(b"ERR_VAL_47", resp_invalid.data)
        self.assertTrue(
            b"PDF" in resp_invalid.data or b"JPG" in resp_invalid.data,
            "Expected helpful error message specifying PDF or JPG format"
        )


if __name__ == "__main__":
    unittest.main()
