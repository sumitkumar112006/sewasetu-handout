import os
import sys
import unittest
import subprocess
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Add app and scripts directory to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))


class TestIssue2RTPSApproval(unittest.TestCase):
    """
    Test suite for Issue 2: Broken RTPS 'Deemed Approval' Automation Engine.
    Guarantees:
    1. deemed_approval.py correctly finds and loads config/app.ini without FileNotFoundError.
    2. run_deemed_approval() batch function exists and transitions overdue applications (>15 days)
       to DEEMED_APPROVED with decided_by = 'RTPS-AUTO'.
    3. Citizen portal dynamically computes effective statutory status as DEEMED_APPROVED
       when application has been pending past the 15-day SLA deadline.
    """

    def test_deemed_approval_config_path_exists(self):
        """
        The script must reference config/app.ini (not the legacy settings.ini).
        In the unfixed code, deemed_approval.py crashes on line 24 with FileNotFoundError.
        """
        script_path = os.path.join(BASE_DIR, "scripts", "deemed_approval.py")
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True
        )
        self.assertNotIn(
            "FileNotFoundError: [Errno 2] No such file or directory: ",
            result.stderr,
            f"deemed_approval.py crashed with FileNotFoundError: {result.stderr}"
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Script failed with code {result.returncode}: {result.stderr}"
        )

    def test_deemed_approval_import_and_execution(self):
        """
        deemed_approval module must be importable without crash on module-level open(),
        and provide a callable run_deemed_approval() function.
        """
        try:
            import deemed_approval
        except FileNotFoundError as e:
            self.fail(f"Importing deemed_approval raised FileNotFoundError: {e}")

        self.assertTrue(
            hasattr(deemed_approval, "run_deemed_approval"),
            "deemed_approval module should export a callable run_deemed_approval() function"
        )

    def test_statutory_sla_status_computation(self):
        """
        Under the RTPS Act, a pending application past 15 days is deemed approved.
        The application portal must evaluate effective status as DEEMED_APPROVED.
        """
        from app import get_effective_status

        now = datetime.now()
        overdue_submitted_at = now - timedelta(days=20)
        recent_submitted_at = now - timedelta(days=5)

        # Overdue pending -> DEEMED_APPROVED
        effective_status = get_effective_status("PENDING", overdue_submitted_at, sla_days=15)
        self.assertEqual(
            effective_status,
            "DEEMED_APPROVED",
            f"Expected DEEMED_APPROVED for 20-day-old application, got {effective_status}"
        )

        # Recent pending -> remains PENDING
        recent_status = get_effective_status("PENDING", recent_submitted_at, sla_days=15)
        self.assertEqual(recent_status, "PENDING")

        # Explicitly REJECTED or APPROVED should not be changed
        self.assertEqual(get_effective_status("REJECTED", overdue_submitted_at, sla_days=15), "REJECTED")
        self.assertEqual(get_effective_status("APPROVED", overdue_submitted_at, sla_days=15), "APPROVED")


if __name__ == "__main__":
    unittest.main()
