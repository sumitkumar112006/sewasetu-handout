import os
import sys
import unittest
import zlib
import re
from datetime import datetime
from unittest.mock import MagicMock

# Add app directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from app import sanitize, generate_acknowledgment


class TestIssue1Encoding(unittest.TestCase):
    """
    Test suite for Issue 1: UTF-8 & Indic Script Encoding Failure.
    Guarantees:
    1. sanitize() does not slice multibyte Indic strings at byte boundaries or truncate to 20 bytes.
    2. generate_acknowledgment() renders Indic characters (Assamese, Bengali, Devanagari)
       faithfully without falling back to '?' question marks due to Latin-1 font limitations.
    """

    def test_sanitize_assamese_name_preservation(self):
        """Assamese name (11 chars, 32 bytes) must not be truncated to 20 bytes or sliced mid-byte."""
        name = "প্ৰমোদ শৰ্মা"
        sanitized = sanitize(name)
        self.assertEqual(sanitized, name, f"Expected full name '{name}', got '{sanitized}'")

    def test_sanitize_devanagari_name_preservation(self):
        """Devanagari name (17 chars, 49 bytes) must not be truncated to 20 bytes."""
        name = "राजेश कुमार शर्मा"
        sanitized = sanitize(name)
        self.assertEqual(sanitized, name, f"Expected full name '{name}', got '{sanitized}'")

    def test_sanitize_preserves_allowed_length(self):
        """Names up to 100 characters (matching DB VARCHAR(100)) must be fully preserved."""
        long_indic_name = "প্ৰমোদ " * 10  # 70 characters
        sanitized = sanitize(long_indic_name)
        self.assertEqual(sanitized, long_indic_name.strip())

    def test_pdf_indic_characters_not_replaced_with_question_marks(self):
        """
        Acknowledgment PDF must support Indic Unicode characters.
        Legacy Helvetica font threw FPDFUnicodeEncodingException and replaced names with '?'.
        """
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (
            "SSP26123456",
            "প্ৰমোদ শৰ্মা",       # Assamese Name
            "9876543210",
            "1955-01-01",
            "সোণাপুৰ",           # Assamese Village
            "Sonari",
            "1234567890",
            "SBIN0001234",
            datetime(2026, 3, 15, 10, 30),
            "PENDING"
        )

        pdf_bytes = generate_acknowledgment(mock_cur, 1)
        self.assertIsInstance(pdf_bytes, (bytes, bytearray))
        self.assertGreater(len(pdf_bytes), 1000)

        # Decompress PDF streams to verify no cells fell back to '(?) Tj'
        streams = re.findall(rb"stream[\r\n]+(.*?)[\r\n]+endstream", pdf_bytes, re.DOTALL)
        question_mark_cells_found = 0
        for s in streams:
            try:
                decompressed = zlib.decompress(s)
                if b"(?) Tj" in decompressed:
                    question_mark_cells_found += 1
            except Exception:
                pass

        self.assertEqual(
            question_mark_cells_found,
            0,
            f"PDF contains {question_mark_cells_found} cell(s) with '(?) Tj' fallback due to font encoding exception!"
        )


if __name__ == "__main__":
    unittest.main()
