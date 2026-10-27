# -*- coding: utf-8 -*-
import os
import sys
import unittest
import re
from unittest.mock import MagicMock

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "utils"))


class TestIssue4PerformanceDoS(unittest.TestCase):
    """
    Test suite for Issue 4: Cyclical Pre-Disbursement Server Freeze (Denial of Service).
    Guarantees:
    1. Compound database indexes are declared in schema.sql for critical query pathways.
    2. Required database indexes exist on the 'applications' table in the PostgreSQL database.
    3. Artificial CPU-burner loop (4,000 line draws) is eliminated from PDF generation.
    4. Gunicorn in Dockerfile is configured with multi-threaded concurrency (--threads)
       to prevent worker starvation during disbursement traffic spikes.
    """

    def test_schema_declares_performance_indexes(self):
        """
        app/schema.sql must define indexes for mobile, (status, submitted_at), and (status, block).
        Without these indexes, queries across 100,000+ records perform full sequential scans.
        """
        schema_path = os.path.join(BASE_DIR, "schema.sql")
        self.assertTrue(os.path.exists(schema_path), f"schema.sql not found at {schema_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_content = f.read()

        self.assertIn(
            "idx_applications_mobile",
            schema_content,
            "schema.sql missing idx_applications_mobile index definition"
        )
        self.assertIn(
            "idx_applications_status_submitted",
            schema_content,
            "schema.sql missing idx_applications_status_submitted compound index definition"
        )
        self.assertIn(
            "idx_applications_status_block",
            schema_content,
            "schema.sql missing idx_applications_status_block compound index definition"
        )

    def test_database_indexes_exist_in_postgres(self):
        """
        PostgreSQL database must have the indexes active on the applications table.
        """
        from app import get_db

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'applications'"
        )
        indexes = {row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()

        required_indexes = {
            "idx_applications_mobile",
            "idx_applications_status_submitted",
            "idx_applications_status_block",
        }
        missing = required_indexes - indexes
        self.assertEqual(
            len(missing),
            0,
            f"Missing required performance indexes in database: {missing}. Existing indexes: {indexes}"
        )

    def test_pdf_generator_eliminates_artificial_cpu_burner_loop(self):
        """
        app/utils/pdf_generator.py must NOT contain the artificial 2000-iteration loop
        that burned CPU by drawing 4,000 individual vector line segments per PDF.
        """
        pdf_gen_path = os.path.join(BASE_DIR, "utils", "pdf_generator.py")
        self.assertTrue(os.path.exists(pdf_gen_path), f"pdf_generator.py not found at {pdf_gen_path}")
        with open(pdf_gen_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertNotIn(
            "range(0, 2000)",
            code,
            "Artificial CPU burner loop 'range(0, 2000)' still present in pdf_generator.py!"
        )
        self.assertNotIn(
            "range(2000)",
            code,
            "Artificial CPU burner loop 'range(2000)' still present in pdf_generator.py!"
        )

        # Generate a test PDF and verify line command count is low (< 50, instead of > 4000)
        from utils.pdf_generator import generate_acknowledgment_pdf

        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (
            "SSP99999",
            "Pramod Sharma",
            "9861908220",
            "1950-01-01",
            "Sonapur",
            "Sonari",
            "1234567890",
            "SBIN0001234",
            "2026-03-01 10:00:00",
            "APPROVED"
        )
        pdf_bytes = generate_acknowledgment_pdf(mock_cur, 1)
        self.assertTrue(len(pdf_bytes) > 0, "PDF generation failed to produce output")

        # In fpdf, vector line draws produce 'l' (line) / 'm' (moveto) operators
        line_draw_count = len(re.findall(rb"[\d.]+ [\d.]+ l\b", pdf_bytes))
        self.assertLess(
            line_draw_count,
            100,
            f"PDF stream contains {line_draw_count} vector line commands; CPU burner loop not eliminated!"
        )

    def test_dockerfile_configures_gunicorn_thread_concurrency(self):
        """
        app/Dockerfile must configure Gunicorn with multi-threaded concurrency (--threads)
        to prevent complete worker lockup during pre-disbursement traffic spikes.
        """
        dockerfile_path = os.path.join(BASE_DIR, "Dockerfile")
        self.assertTrue(os.path.exists(dockerfile_path), f"Dockerfile not found at {dockerfile_path}")
        with open(dockerfile_path, "r", encoding="utf-8") as f:
            dockerfile_content = f.read()

        self.assertIn(
            "--threads",
            dockerfile_content,
            "Dockerfile CMD must include '--threads' to enable multi-threaded Gunicorn concurrency"
        )


if __name__ == "__main__":
    unittest.main()
