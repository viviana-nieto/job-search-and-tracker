"""Unit tests for scripts/score_messages.py (Phase 6 tracking refactor)."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

import tracking  # noqa: E402
import score_messages  # noqa: E402

try:
    from fixtures import FixedClock  # noqa: E402
except ImportError:
    from datetime import date

    class FixedClock:  # type: ignore[no-redef]
        def __init__(self, iso_date="2026-04-11"):
            self._today = date.fromisoformat(iso_date)

        def today_str(self):
            return self._today.isoformat()


TODAY = "2026-04-11"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_unlinked(data, name, company, msg_type, role, outcome, msg,
                  company_size="unknown"):
    """Append an unlinked outreach entry to data['unlinked_outreach']."""
    entry = tracking.build_outreach_entry(
        name=name,
        recipient_role=role,
        msg_type=msg_type,
        message=msg,
        today=TODAY,
        company=company,
    )
    entry["outcome"] = outcome
    entry["company_size"] = company_size
    data["unlinked_outreach"].append(entry)
    return entry


def _add_nested(data, name, company, role_for_app, msg_type, role, outcome,
                msg, company_size="unknown"):
    """Create-or-find an application and append a nested outreach entry."""
    app = tracking.find_or_create_application(
        data,
        company=company,
        role=role_for_app,
        today=TODAY,
        company_size=company_size,
    )
    entry = tracking.build_outreach_entry(
        name=name,
        recipient_role=role,
        msg_type=msg_type,
        message=msg,
        today=TODAY,
    )
    entry["outcome"] = outcome
    entry["company_size"] = company_size
    app.setdefault("outreach", []).append(entry)
    return entry, app


# ---------------------------------------------------------------------------
# Base test case — handles isolation via tempdir + monkeypatching
# ---------------------------------------------------------------------------

class _ScoreMessagesTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp_path = Path(self._tmp.name)

        # Redirect all tracking file paths into the tempdir.
        self._orig_tracking_file = tracking.TRACKING_FILE
        self._orig_template_file = tracking.TRACKING_TEMPLATE
        self._orig_legacy_file = tracking.LEGACY_FILE
        self._orig_regen = tracking._regen_data_js_silently

        tracking.TRACKING_FILE = tmp_path / "tracking.json"
        tracking.TRACKING_TEMPLATE = tmp_path / "tracking-template.json"
        tracking.LEGACY_FILE = tmp_path / "outreach-history.json"
        tracking._regen_data_js_silently = lambda: None

        self.addCleanup(self._restore_tracking_globals)

        # Seed with an empty v3.0 template so load() hits a real file.
        self.data = {
            "metadata": {
                "version": "3.0",
                "created": TODAY,
                "last_updated": TODAY,
            },
            "applications": [],
            "unlinked_outreach": [],
            "legacy_applications": [],
            "stats": {},
        }
        self._write_current_data()

    def _restore_tracking_globals(self):
        tracking.TRACKING_FILE = self._orig_tracking_file
        tracking.TRACKING_TEMPLATE = self._orig_template_file
        tracking.LEGACY_FILE = self._orig_legacy_file
        tracking._regen_data_js_silently = self._orig_regen

    def _write_current_data(self):
        """Persist self.data directly (bypasses tracking.save side effects)."""
        with open(tracking.TRACKING_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def _run_score(self):
        """Call score_messages.score_messages() with stdout captured."""
        self._write_current_data()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            score_messages.score_messages()
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

class TestEmptyState(_ScoreMessagesTestBase):
    def test_no_outreach_prints_empty_message_and_returns_early(self):
        out = self._run_score()
        self.assertIn("No outreach data to analyze.", out)
        self.assertNotIn("MESSAGE PERFORMANCE REPORT", out)
        self.assertNotIn("Total outreach:", out)


# ---------------------------------------------------------------------------
# Single entry variations
# ---------------------------------------------------------------------------

class TestSingleEntry(_ScoreMessagesTestBase):
    def test_single_pending_entry(self):
        _add_unlinked(
            self.data,
            name="Alice Example",
            company="AcmeCo",
            msg_type="connection-request",
            role="recruiter",
            outcome="pending",
            msg="Hi Alice, would love to connect.",
        )
        out = self._run_score()
        self.assertIn("MESSAGE PERFORMANCE REPORT", out)
        self.assertIn("Total outreach: 1", out)
        self.assertIn("Positive outcomes: 0", out)
        self.assertIn("Pending: 1", out)
        self.assertIn("--- Message Type ---", out)

    def test_single_accepted_entry_reports_100_percent(self):
        _add_unlinked(
            self.data,
            name="Bob Example",
            company="GlobalCo",
            msg_type="inmail",
            role="hiring-manager",
            outcome="accepted",
            msg="Hi Bob, I'm keen on your team.",
        )
        out = self._run_score()
        self.assertIn("Total outreach: 1", out)
        self.assertIn("Positive outcomes: 1", out)
        self.assertIn("(100%)", out)


# ---------------------------------------------------------------------------
# Multiple mixed entries — dimension tables
# ---------------------------------------------------------------------------

class TestMultipleEntries(_ScoreMessagesTestBase):
    def test_five_mixed_entries(self):
        specs = [
            ("Alice", "AcmeCo",   "connection-request", "startup", "recruiter",
             "accepted"),
            ("Betty", "AcmeCo",   "connection-request", "startup", "recruiter",
             "replied"),
            ("Carl",  "BigCorp",  "inmail",             "large",   "hiring-manager",
             "pending"),
            ("Dana",  "SmallInc", "email",              "startup", "peer",
             "no_response"),
            ("Eve",   "BigCorp",  "connection-request", "large",   "recruiter",
             "interview"),
        ]
        for name, company, mtype, size, role, outcome in specs:
            _add_unlinked(
                self.data,
                name=name,
                company=company,
                msg_type=mtype,
                role=role,
                outcome=outcome,
                msg=f"Hello {name}, here is my pitch.",
                company_size=size,
            )

        out = self._run_score()

        self.assertIn("Total outreach: 5", out)
        # accepted + replied + interview = 3 positives
        self.assertIn("Positive outcomes: 3", out)

        # Each dimension table appears
        self.assertIn("--- Message Type ---", out)
        self.assertIn("--- Company Size ---", out)
        self.assertIn("--- Recipient Role ---", out)

        # Message Type table: connection-request appears with 3 entries
        self.assertIn("connection-request", out)
        # Company size values visible
        self.assertIn("startup", out)
        self.assertIn("large", out)
        # Recipient role values visible
        self.assertIn("recruiter", out)

        # Structural check: confirm connection-request row shows 3 sent.
        mt_idx = out.index("--- Message Type ---")
        cs_idx = out.index("--- Company Size ---")
        mt_section = out[mt_idx:cs_idx]
        # Within the message-type section, the connection-request row should
        # include the count 3.
        conn_line = next(
            (line for line in mt_section.splitlines() if "connection-request" in line),
            "",
        )
        self.assertIn("3", conn_line,
                      f"expected connection-request row to include 3: {conn_line!r}")

        # And recruiter row should show 3 in recipient-role section.
        rr_idx = out.index("--- Recipient Role ---")
        # Recipient Role section goes until the next "---" header.
        rr_section = out[rr_idx:]
        for delim in ("--- Message Length ---", "--- Top Performing Messages ---",
                      "--- Recommendations ---"):
            if delim in rr_section:
                rr_section = rr_section[:rr_section.index(delim)]
                break
        recruiter_line = next(
            (line for line in rr_section.splitlines() if line.strip().startswith("recruiter")),
            "",
        )
        self.assertIn("3", recruiter_line,
                      f"expected recruiter row to include 3: {recruiter_line!r}")


# ---------------------------------------------------------------------------
# Message length bucketing
# ---------------------------------------------------------------------------

class TestMessageLength(_ScoreMessagesTestBase):
    def test_short_and_long_buckets(self):
        short_msg = "s" * 100
        long_msg = "L" * 400

        _add_unlinked(
            self.data,
            name="Shorty",
            company="ShortCo",
            msg_type="connection-request",
            role="recruiter",
            outcome="accepted",
            msg=short_msg,
        )
        _add_unlinked(
            self.data,
            name="Longy",
            company="LongCo",
            msg_type="inmail",
            role="hiring-manager",
            outcome="replied",
            msg=long_msg,
        )

        out = self._run_score()
        self.assertIn("--- Message Length ---", out)

        ml_idx = out.index("--- Message Length ---")
        ml_section = out[ml_idx:]
        # Truncate to message length section only (stops at next "---").
        next_sep = ml_section.find("---", len("--- Message Length ---"))
        if next_sep != -1:
            ml_section = ml_section[:next_sep]

        self.assertIn("Short (<=300)", ml_section)
        self.assertIn("Long (>300)", ml_section)

        short_line = next(
            (l for l in ml_section.splitlines() if "Short (<=300)" in l),
            "",
        )
        long_line = next(
            (l for l in ml_section.splitlines() if "Long (>300)" in l),
            "",
        )
        # Format: "  {label:<25} {len:>5} {pos:>10} {rate:>7.0f}%"
        # So each line should contain two "1"s and "100%".
        self.assertIn("1", short_line)
        self.assertIn("100%", short_line)
        self.assertIn("1", long_line)
        self.assertIn("100%", long_line)


# ---------------------------------------------------------------------------
# Top performing messages section
# ---------------------------------------------------------------------------

class TestTopPerforming(_ScoreMessagesTestBase):
    def test_top_performing_lists_positive_names_and_outcomes(self):
        _add_unlinked(
            self.data, name="Alice", company="AcmeCo",
            msg_type="connection-request", role="recruiter",
            outcome="accepted", msg="Hi Alice",
        )
        _add_unlinked(
            self.data, name="Bob", company="BetaCo",
            msg_type="inmail", role="hiring-manager",
            outcome="replied", msg="Hi Bob",
        )
        _add_unlinked(
            self.data, name="Carol", company="GammaCo",
            msg_type="email", role="peer",
            outcome="interview", msg="Hi Carol",
        )

        out = self._run_score()
        self.assertIn("--- Top Performing Messages ---", out)

        self.assertIn("Alice @ AcmeCo", out)
        self.assertIn("Bob @ BetaCo", out)
        self.assertIn("Carol @ GammaCo", out)

        self.assertIn("[accepted]", out)
        self.assertIn("[replied]", out)
        self.assertIn("[interview]", out)


# ---------------------------------------------------------------------------
# Recommendations — threshold and winning-dimension detection
# ---------------------------------------------------------------------------

class TestRecommendationsThreshold(_ScoreMessagesTestBase):
    def test_below_threshold_shows_need_more_data(self):
        for i in range(5):
            _add_unlinked(
                self.data,
                name=f"Person{i}",
                company=f"Co{i}",
                msg_type="connection-request",
                role="recruiter",
                outcome="pending",
                msg=f"msg {i}",
            )
        out = self._run_score()
        self.assertIn("--- Recommendations ---", out)
        self.assertIn("Need more data", out)
        # Message phrases the count as "You have 5 outreach entries".
        self.assertIn("5", out)
        self.assertIn("outreach entries", out)

    def test_above_threshold_reports_best_dimension(self):
        # 12 email entries, 8 positive — email should clearly win Message Type.
        for i in range(8):
            _add_unlinked(
                self.data,
                name=f"Pos{i}",
                company=f"EmailCo{i}",
                msg_type="email",
                role="recruiter",
                outcome="accepted",
                msg=f"positive msg {i}",
            )
        for i in range(4):
            _add_unlinked(
                self.data,
                name=f"Neg{i}",
                company=f"EmailCo{i + 100}",
                msg_type="email",
                role="recruiter",
                outcome="no_response",
                msg=f"negative msg {i}",
            )

        out = self._run_score()
        self.assertIn("--- Recommendations ---", out)
        self.assertNotIn("Need more data", out)
        # score_messages prints "Best Message Type: email (...)"
        self.assertIn("Best Message Type:", out)
        self.assertIn("email", out)


# ---------------------------------------------------------------------------
# Linked (nested under app) vs unlinked traversal
# ---------------------------------------------------------------------------

class TestLinkedVsUnlinked(_ScoreMessagesTestBase):
    def test_both_sources_are_counted(self):
        _add_nested(
            self.data,
            name="Nina",
            company="NestedCo",
            role_for_app="Senior Engineer",
            msg_type="inmail",
            role="hiring-manager",
            outcome="accepted",
            msg="Hi Nina",
        )
        _add_unlinked(
            self.data,
            name="Ulric",
            company="UnlinkedCo",
            msg_type="connection-request",
            role="recruiter",
            outcome="replied",
            msg="Hi Ulric",
        )
        out = self._run_score()
        self.assertIn("Total outreach: 2", out)
        self.assertIn("Positive outcomes: 2", out)


# ---------------------------------------------------------------------------
# Company resolution — nested takes company from parent, unlinked from self
# ---------------------------------------------------------------------------

class TestCompanyResolution(_ScoreMessagesTestBase):
    def test_nested_and_unlinked_companies_resolve_in_top_performing(self):
        _add_nested(
            self.data,
            name="Nina",
            company="NestedCo",
            role_for_app="Engineer",
            msg_type="inmail",
            role="hiring-manager",
            outcome="accepted",
            msg="Hi Nina, nested positive",
        )
        _add_unlinked(
            self.data,
            name="Ulric",
            company="UnlinkedCo",
            msg_type="connection-request",
            role="recruiter",
            outcome="replied",
            msg="Hi Ulric, unlinked positive",
        )
        out = self._run_score()

        self.assertIn("Total outreach: 2", out)
        # Both companies appear in Top Performing Messages section.
        self.assertIn("--- Top Performing Messages ---", out)
        top_idx = out.index("--- Top Performing Messages ---")
        top_section = out[top_idx:]
        if "--- Recommendations ---" in top_section:
            top_section = top_section[:top_section.index("--- Recommendations ---")]

        self.assertIn("Nina @ NestedCo", top_section)
        self.assertIn("Ulric @ UnlinkedCo", top_section)


# ---------------------------------------------------------------------------
# CLI surface — call main() directly
# ---------------------------------------------------------------------------

class TestCliSurface(_ScoreMessagesTestBase):
    def test_main_on_empty_tracking_matches_score_messages(self):
        # Subprocess invocation is fiddly (won't inherit the monkeypatched
        # module globals). Call main() directly instead to exercise the CLI
        # entry point without touching real files.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            score_messages.main()
        out = buf.getvalue()
        self.assertIn("No outreach data to analyze.", out)


if __name__ == "__main__":
    unittest.main()
