import os
import sys
import json
import copy
import datetime
import unittest
from pathlib import Path
from unittest.mock import patch

# Configure stdout and stderr for UTF-8 encoding on Windows to handle emojis correctly
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Set project root in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent.pipeline import run_compliance_pipeline

class TestVendorGateCompliance(unittest.TestCase):
    # Track failures to exit with code 1 without tracebacks
    failures = []

    @classmethod
    def setUpClass(cls):
        cls.failures = []
        # Load mock data from JSON file with exception handling
        json_path = Path(__file__).resolve().parent / "mock_data.json"
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                cls.mock_data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"[Error] Mock data file not found at: {json_path}. "
                "Please make sure tests/mock_data.json exists."
            )
        except json.JSONDecodeError as e:
            raise ValueError(
                f"[Error] Corrupted or invalid JSON in tests/mock_data.json: {e}"
            )

    @classmethod
    def tearDownClass(cls):
        # If there were failures, log a summary and exit with code 1 (no traceback)
        if cls.failures:
            print("\n=======================================================")
            print(f"❌ TEST SUITE FAILED with {len(cls.failures)} failure(s):")
            print("=======================================================")
            for idx, fail_msg in enumerate(cls.failures, 1):
                print(f"{idx}. {fail_msg}")
            print("=======================================================\n")
            # Flush stdout and stderr buffers before exiting
            sys.stdout.flush()
            sys.stderr.flush()
            # Exit process with code 1 without raising exception tracebacks
            os._exit(1)

    def setUp(self):
        # Set dynamic system date based on today's date
        self.today = datetime.date.today()
        os.environ["SYSTEM_DATE"] = self.today.strftime("%Y-%m-%d")
        
        self.dummy_docs = [
            ("W-9 Tax Form", Path("dummy_w9.pdf")),
            ("Certificate of Insurance", Path("dummy_coi.pdf")),
            ("Bank Verification Letter", Path("dummy_bank.pdf")),
            ("Company Registration", Path("dummy_reg.pdf")),
        ]

    def tearDown(self):
        if "SYSTEM_DATE" in os.environ:
            del os.environ["SYSTEM_DATE"]

    @patch("agent.pipeline.run_dynamic_extraction")
    def test_1_approve_scenario(self, mock_run_extraction):
        """
        Scenario 1: A vendor package with all documents present and all 10 compliance rules passing
        should return APPROVE.
        """
        mock_data = copy.deepcopy(self.mock_data["approve"])
        
        # Calculate a future policy expiration date (> 30 days ahead)
        future_date = (self.today + datetime.timedelta(days=90)).strftime("%Y-%m-%d")
        mock_data["documents"]["Certificate of Insurance"]["expiry_date"] = future_date
        
        mock_run_extraction.return_value = mock_data

        # Run pipeline
        report = run_compliance_pipeline("USA", self.dummy_docs)

        # Print outputs
        print("\n\n=== [TEST 1: APPROVE SCENARIO PIPELINE OUTPUT SUMMARY] ===")
        print(json.dumps(report["summary"], indent=2, ensure_ascii=False))

        # Assert results with custom error logging (no traceback raised)
        try:
            self.assertEqual(
                report["summary"]["recommendation"], 
                "Approve",
                msg=f"Pipeline recommended '{report['summary']['recommendation']}' instead of 'Approve'. Reason: {report['summary']['recommendation_reason']}"
            )
            self.assertEqual(report["summary"]["failed_cross_checks"], 0)
            self.assertEqual(report["summary"]["total_docs_missing"], 0)
            self.assertIn("Clean compliance", report["summary"]["recommendation_reason"])
        except AssertionError as e:
            fail_msg = f"test_1_approve_scenario failed: {e}"
            print(f"\n❌ [TEST FAILURE] {fail_msg}")
            self.failures.append(fail_msg)

    @patch("agent.pipeline.run_dynamic_extraction")
    def test_2_request_info_scenario(self, mock_run_extraction):
        """
        Scenario 2: A vendor package with two rule failures (e.g. COI expired, name mismatch W-9/COI)
        should return REQUEST INFO.
        """
        mock_data = copy.deepcopy(self.mock_data["request_info"])
        
        # Calculate an expired policy date (in the past)
        past_date = (self.today - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
        mock_data["documents"]["Certificate of Insurance"]["expiry_date"] = past_date
        
        mock_run_extraction.return_value = mock_data

        # Run pipeline
        report = run_compliance_pipeline("USA", self.dummy_docs)

        # Print outputs
        print("\n\n=== [TEST 2: REQUEST INFO SCENARIO PIPELINE OUTPUT SUMMARY] ===")
        print(json.dumps(report["summary"], indent=2, ensure_ascii=False))

        # Assert results with custom error logging (no traceback raised)
        try:
            self.assertEqual(
                report["summary"]["recommendation"], 
                "Request Info",
                msg=f"Pipeline recommended '{report['summary']['recommendation']}' instead of 'Request Info'. Reason: {report['summary']['recommendation_reason']}"
            )
            # Rule 1 and Rule 3 should be failed rules
            failed_rule_ids = [r["rule_id"] for r in report["compliance_rules"] if r["status"] == "Failed"]
            self.assertIn("Rule 1", failed_rule_ids)
            self.assertIn("Rule 3", failed_rule_ids)
            self.assertEqual(len(failed_rule_ids), 2)
        except AssertionError as e:
            fail_msg = f"test_2_request_info_scenario failed: {e}"
            print(f"\n❌ [TEST FAILURE] {fail_msg}")
            self.failures.append(fail_msg)

    @patch("agent.pipeline.run_dynamic_extraction")
    def test_3_escalate_scenario(self, mock_run_extraction):
        """
        Scenario 3: A vendor package missing required documents with a completeness score below 40%
        should return ESCALATE.
        """
        mock_run_extraction.return_value = self.mock_data["escalate"]

        # Only W-9 uploaded
        uploaded_docs = [("W-9 Tax Form", Path("dummy_w9.pdf"))]

        # Run pipeline
        report = run_compliance_pipeline("USA", uploaded_docs)

        # Print outputs
        print("\n\n=== [TEST 3: ESCALATE SCENARIO PIPELINE OUTPUT SUMMARY] ===")
        print(json.dumps(report["summary"], indent=2, ensure_ascii=False))

        # Assert results with custom error logging (no traceback raised)
        try:
            self.assertEqual(
                report["summary"]["recommendation"], 
                "Escalate",
                msg=f"Pipeline recommended '{report['summary']['recommendation']}' instead of 'Escalate'. Reason: {report['summary']['recommendation_reason']}"
            )
            self.assertTrue(len(report["missing_required_docs"]) > 0)
            self.assertLess(report["summary"]["overall_completeness_pct"], 40.0)
        except AssertionError as e:
            fail_msg = f"test_3_escalate_scenario failed: {e}"
            print(f"\n❌ [TEST FAILURE] {fail_msg}")
            self.failures.append(fail_msg)

if __name__ == "__main__":
    unittest.main()
