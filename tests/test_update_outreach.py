"""Unit tests for scripts/update_outreach.py (Phase 6 tracking refactor).

Scope is strictly the thin CLI wrapper around tracking.py. Tracking internals
are covered by a sibling test file.
"""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date as real_date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

import tracking  # noqa: E402
import update_outreach  # noqa: E402

try:
    from fixtures import FixedClock  # noqa: F401
except ImportError:
    # Fallback shim in case the sibling agent's tests/fixtures.py isn't in place
    # yet. The real class lives at tests/fixtures.py — delete this once sibling
    # agent lands.
    class FixedClock:  # type: ignore
        def __init__(self, iso_date="2026-04-11"):
            self._today = real_date.fromisoformat(iso_date)

        def today(self):
            return self._today

        def today_str(self):
            return self._today.isoformat()


class _FrozenDate(real_date):
    """A date subclass whose .today() returns a fixed value. Used to patch
    tracking.date so tracking._today_str() is deterministic inside
    update_outreach.log_outreach (which doesn't forward a `today` kwarg)."""

    _frozen_iso = "2026-04-11"

    @classmethod
    def today(cls):
        return real_date.fromisoformat(cls._frozen_iso)


def _stub_classify(company: str) -> str:
    return "startup" if (company or "").lower() == "acme" else "unknown"


class _TrackingIsolationMixin:
    """Shared setUp/tearDown that redirects tracking state to a temp dir and
    stubs the company classifier so tests are hermetic."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

        self._original_tracking_file = tracking.TRACKING_FILE
        self._original_template = tracking.TRACKING_TEMPLATE
        self._original_legacy = tracking.LEGACY_FILE
        self._original_regen = tracking._regen_data_js_silently
        self._original_date = tracking.date
        self._original_classify = update_outreach.classify

        tracking.TRACKING_FILE = self.tmp_path / "tracking.json"
        tracking.TRACKING_TEMPLATE = self.tmp_path / "template.json"
        tracking.LEGACY_FILE = self.tmp_path / "outreach-history.json"
        tracking._regen_data_js_silently = lambda: None
        tracking.date = _FrozenDate
        update_outreach.classify = _stub_classify

        # Seed the template file so tracking.load() produces a clean v3.0 dict.
        tracking.TRACKING_TEMPLATE.write_text(
            json.dumps(tracking._empty_tracking())
        )

    def tearDown(self):
        tracking.TRACKING_FILE = self._original_tracking_file
        tracking.TRACKING_TEMPLATE = self._original_template
        tracking.LEGACY_FILE = self._original_legacy
        tracking._regen_data_js_silently = self._original_regen
        tracking.date = self._original_date
        update_outreach.classify = self._original_classify
        self.tmp.cleanup()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_tracking(self) -> dict:
        with open(tracking.TRACKING_FILE) as f:
            return json.load(f)

    def _seed_application(self, company, role, app_id=None):
        """Put one minimal v3.0 application into tracking.json."""
        data = tracking.load()
        today = _FrozenDate._frozen_iso
        slug = tracking._slug(f"{company} {role}")
        aid = app_id or f"{today}-{slug}"
        app = {
            "id": aid,
            "company": company,
            "role": role,
            "url": None,
            "source": "linkedin",
            "company_size": "unknown",
            "salary_range": None,
            "location": None,
            "status": "saved",
            "dates": {
                "saved": today,
                "saved_at": f"{today}T12:00:00+00:00",
                "applied": None,
                "applied_at": None,
                "rejected": None,
                "offer": None,
            },
            "cover_letter": None,
            "outreach": [],
            "notes": "",
        }
        data["applications"].append(app)
        tracking.save(data)
        return aid


class TestLogOutreach(_TrackingIsolationMixin, unittest.TestCase):
    """log_outreach writes to tracking.json via the tracking module."""

    def test_unlinked_brand_new_company(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.log_outreach(
                name="Alice Example",
                company="Acme",
                recipient_role="recruiter",
                msg_type="connection-request",
                message="Hi Alice, I admire Acme's work.",
            )

        data = self._read_tracking()
        # Entry lives in unlinked_outreach (no application exists yet).
        self.assertEqual(len(data["unlinked_outreach"]), 1)
        self.assertEqual(len(data["applications"]), 0)

        entry = data["unlinked_outreach"][0]
        self.assertEqual(entry["name"], "Alice Example")
        self.assertEqual(entry["company"], "Acme")
        self.assertEqual(entry["outcome"], "pending")
        self.assertEqual(entry["type"], "connection-request")
        self.assertEqual(entry["recipient_role"], "recruiter")
        self.assertEqual(entry["message"], "Hi Alice, I admire Acme's work.")
        self.assertEqual(
            entry["message_length"],
            len("Hi Alice, I admire Acme's work."),
        )
        self.assertEqual(entry["dates"]["sent"], "2026-04-11")
        self.assertIsNone(entry["dates"]["accepted"])
        self.assertIsNone(entry["dates"]["replied"])
        self.assertIsNone(entry["dates"]["interview"])

        # id starts with 'outreach-', includes today and a slug of the name.
        self.assertTrue(entry["id"].startswith("outreach-"))
        self.assertIn("2026-04-11", entry["id"])
        self.assertIn("alice-example", entry["id"])

    def test_classifier_stub_drives_company_size(self):
        # Acme → startup (per stub); anything else → unknown.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.log_outreach(
                name="Bob",
                company="Acme",
                recipient_role="peer",
                msg_type="inmail",
                message="hello",
            )
            update_outreach.log_outreach(
                name="Carol",
                company="NovaCorp",
                recipient_role="peer",
                msg_type="inmail",
                message="hello",
            )

        out = buf.getvalue()
        self.assertIn("(inmail, startup)", out)
        self.assertIn("(inmail, unknown)", out)

    def test_print_format_with_and_without_job_id(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.log_outreach(
                name="Alice",
                company="Acme",
                recipient_role="recruiter",
                msg_type="connection-request",
                message="hi",
            )
        out = buf.getvalue()
        self.assertIn(
            "Logged outreach to Alice at Acme (connection-request, startup)",
            out,
        )
        # No job_id → no 'Linked to job' line.
        self.assertNotIn("Linked to job", out)

        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            update_outreach.log_outreach(
                name="Dave",
                company="Acme",
                recipient_role="peer",
                msg_type="email",
                message="hi",
                job_id="2026-04-11-acme-pm",
            )
        out2 = buf2.getvalue()
        self.assertIn(
            "Logged outreach to Dave at Acme (email, startup)",
            out2,
        )
        self.assertIn("Linked to job: 2026-04-11-acme-pm", out2)

    def test_linked_path_via_matching_job_id(self):
        """When job_id matches an application's id, the outreach nests under
        that application instead of going to unlinked_outreach."""
        aid = self._seed_application("Acme", "PM")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.log_outreach(
                name="Alice",
                company="Acme",
                recipient_role="recruiter",
                msg_type="connection-request",
                message="hi Alice",
                job_id=aid,
            )

        data = self._read_tracking()
        self.assertEqual(len(data["unlinked_outreach"]), 0)
        self.assertEqual(len(data["applications"]), 1)
        app = data["applications"][0]
        self.assertEqual(len(app["outreach"]), 1)
        nested = app["outreach"][0]
        self.assertEqual(nested["name"], "Alice")
        # Nested entries do not carry a 'company' field (parent owns it).
        self.assertNotIn("company", nested)

    def test_writes_to_tracking_json_not_legacy(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.log_outreach(
                name="Alice",
                company="Acme",
                recipient_role="recruiter",
                msg_type="connection-request",
                message="hi",
            )
        self.assertTrue(tracking.TRACKING_FILE.exists())
        self.assertFalse(
            tracking.LEGACY_FILE.exists(),
            "legacy outreach-history.json should not be touched",
        )

    def test_stats_recomputed_after_log(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.log_outreach(
                name="Alice",
                company="Acme",
                recipient_role="recruiter",
                msg_type="connection-request",
                message="hi",
            )

        data = self._read_tracking()
        self.assertEqual(data["stats"]["total_outreach_sent"], 1)
        self.assertEqual(data["stats"]["total_applications"], 0)
        self.assertEqual(data["stats"]["positive_outcomes"], 0)
        self.assertEqual(data["stats"]["interviews_scheduled"], 0)

    def test_stats_counts_applications_when_seeded(self):
        self._seed_application("Acme", "PM")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.log_outreach(
                name="Alice",
                company="Acme",
                recipient_role="recruiter",
                msg_type="inmail",
                message="hi",
            )
        data = self._read_tracking()
        self.assertEqual(data["stats"]["total_applications"], 1)
        self.assertEqual(data["stats"]["total_outreach_sent"], 1)


class TestUpdateOutcome(_TrackingIsolationMixin, unittest.TestCase):
    """update_outcome mutates an existing entry and persists."""

    def _seed_outreach(self, **overrides):
        """Use tracking.log_outreach directly (not the CLI) to seed an entry."""
        data = tracking.load()
        tracking.log_outreach(
            data,
            name=overrides.get("name", "Alice"),
            company=overrides.get("company", "Acme"),
            recipient_role=overrides.get("recipient_role", "recruiter"),
            msg_type=overrides.get("msg_type", "connection-request"),
            message=overrides.get("message", "hi"),
            company_size=overrides.get("company_size", "startup"),
            today="2026-04-11",
        )
        tracking.save(data)

    def test_found_accepted_sets_response_time(self):
        self._seed_outreach()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.update_outcome(
                "Alice", "Acme", "accepted", update_date="2026-04-14"
            )

        data = self._read_tracking()
        entry = data["unlinked_outreach"][0]
        self.assertEqual(entry["outcome"], "accepted")
        self.assertEqual(entry["dates"]["accepted"], "2026-04-14")
        self.assertEqual(entry["response_time_days"], 3)

        self.assertIn(
            "Updated Alice at Acme: accepted (2026-04-14)",
            buf.getvalue(),
        )

    def test_not_found_raises_system_exit_and_writes_stderr(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                update_outreach.update_outcome(
                    "Ghost", "Nowhere", "accepted", update_date="2026-04-11"
                )
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn(
            "Error: No outreach found for Ghost at Nowhere",
            err.getvalue(),
        )

    def test_status_transition_replied(self):
        self._seed_outreach()
        with contextlib.redirect_stdout(io.StringIO()):
            update_outreach.update_outcome(
                "Alice", "Acme", "replied", update_date="2026-04-12"
            )
        entry = self._read_tracking()["unlinked_outreach"][0]
        self.assertEqual(entry["outcome"], "replied")
        self.assertEqual(entry["dates"]["replied"], "2026-04-12")

    def test_status_transition_interview(self):
        self._seed_outreach()
        with contextlib.redirect_stdout(io.StringIO()):
            update_outreach.update_outcome(
                "Alice", "Acme", "interview", update_date="2026-04-13"
            )
        entry = self._read_tracking()["unlinked_outreach"][0]
        self.assertEqual(entry["outcome"], "interview")
        self.assertEqual(entry["dates"]["interview"], "2026-04-13")

    def test_status_transition_no_response(self):
        self._seed_outreach()
        with contextlib.redirect_stdout(io.StringIO()):
            update_outreach.update_outcome(
                "Alice", "Acme", "no_response", update_date="2026-04-25"
            )
        entry = self._read_tracking()["unlinked_outreach"][0]
        self.assertEqual(entry["outcome"], "no_response")

    def test_status_transition_declined(self):
        self._seed_outreach()
        with contextlib.redirect_stdout(io.StringIO()):
            update_outreach.update_outcome(
                "Alice", "Acme", "declined", update_date="2026-04-20"
            )
        entry = self._read_tracking()["unlinked_outreach"][0]
        self.assertEqual(entry["outcome"], "declined")

    def test_status_transition_sent_sets_date(self):
        self._seed_outreach()
        with contextlib.redirect_stdout(io.StringIO()):
            update_outreach.update_outcome(
                "Alice", "Acme", "sent", update_date="2026-04-15"
            )
        entry = self._read_tracking()["unlinked_outreach"][0]
        self.assertEqual(entry["dates"]["sent"], "2026-04-15")


class TestShowStats(_TrackingIsolationMixin, unittest.TestCase):
    """show_stats prints a breakdown of tracking data."""

    def test_empty_state_suppresses_breakdown(self):
        # Kick off an empty load/save so tracking.json exists.
        data = tracking.load()
        tracking.save(data)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.show_stats()
        out = buf.getvalue()

        self.assertIn("=== Outreach Stats ===", out)
        self.assertIn("Total outreach sent: 0", out)
        self.assertIn("Applications: 0", out)
        # Breakdown blocks are suppressed when there's nothing to show.
        self.assertNotIn("Outcomes:", out)
        self.assertNotIn("By Message Type", out)
        self.assertNotIn("By Company Size", out)
        self.assertNotIn("By Recipient Role", out)
        self.assertNotIn("Avg response time:", out)

    def test_single_accepted_entry_produces_full_breakdown(self):
        data = tracking.load()
        tracking.log_outreach(
            data,
            name="Alice",
            company="Acme",
            recipient_role="recruiter",
            msg_type="connection-request",
            message="hi",
            company_size="startup",
            today="2026-04-11",
        )
        tracking.update_outcome(
            data, "Alice", "Acme", "accepted", today="2026-04-14"
        )
        tracking.save(data)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.show_stats()
        out = buf.getvalue()

        self.assertIn("Total outreach sent: 1", out)
        self.assertIn("Applications: 0", out)
        self.assertIn("Outcomes:", out)
        self.assertIn("accepted", out)
        self.assertIn("(100%)", out)

        self.assertIn("By Message Type:", out)
        self.assertIn("connection-request", out)

        self.assertIn("By Company Size:", out)
        # NOTE: tracking.build_outreach_entry does NOT persist company_size
        # on the outreach dict (the arg to tracking.log_outreach is consumed
        # only when creating a parent application). So show_stats falls back
        # to "unknown" for a freshly-logged unlinked entry. If the tracking
        # module is later changed to persist company_size on entries, this
        # assertion should flip to "startup".
        self.assertIn("unknown", out)

        self.assertIn("By Recipient Role:", out)
        self.assertIn("recruiter", out)

        # Response time is 3 days (2026-04-11 → 2026-04-14).
        self.assertIn("Avg response time:", out)
        self.assertIn("3.0 days", out)

    def test_avg_response_time_hidden_when_only_pending(self):
        data = tracking.load()
        tracking.log_outreach(
            data,
            name="Alice",
            company="Acme",
            recipient_role="recruiter",
            msg_type="connection-request",
            message="hi",
            company_size="startup",
            today="2026-04-11",
        )
        tracking.save(data)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update_outreach.show_stats()
        out = buf.getvalue()
        self.assertIn("Total outreach sent: 1", out)
        self.assertNotIn("Avg response time:", out)


class TestCliSurface(unittest.TestCase):
    """Regression guardrail against accidental argparse surface changes."""

    def test_help_lists_three_subcommands(self):
        proc = subprocess.run(
            [sys.executable, "update_outreach.py", "--help"],
            cwd=str(PROJECT_ROOT / "scripts"),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        self.assertIn("log", out)
        self.assertIn("update", out)
        self.assertIn("stats", out)


if __name__ == "__main__":
    unittest.main()
