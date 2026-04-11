"""Tests for the legacy outreach-history.json → tracking.json migration path.

Covers:
- scripts/migrate_outreach_to_tracking.py (the standalone one-shot script)
- scripts/tracking.py::_merge_legacy (the auto-migration triggered by load())
"""
from __future__ import annotations

import contextlib
import importlib
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
import migrate_outreach_to_tracking as migrate_script  # noqa: E402

try:
    from fixtures import FixedClock  # noqa: F401
except ImportError:
    from datetime import date

    class FixedClock:  # type: ignore
        def __init__(self, iso_date: str = "2026-04-11"):
            self._today = date.fromisoformat(iso_date)

        def today_str(self) -> str:
            return self._today.isoformat()


def _legacy_with_connections(conns, apps=None):
    return {
        "metadata": {"created": "2025-01-01"},
        "connections": conns,
        "applications": apps or [],
    }


class _TempIsolation(unittest.TestCase):
    """Base class: redirect tracking + migrate-script paths into a temp dir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

        # tracking module state
        self._orig_tracking = tracking.TRACKING_FILE
        self._orig_template = tracking.TRACKING_TEMPLATE
        self._orig_legacy = tracking.LEGACY_FILE
        self._orig_regen = tracking._regen_data_js_silently
        tracking.TRACKING_FILE = self.tmp_path / "tracking.json"
        tracking.TRACKING_TEMPLATE = self.tmp_path / "tracking-template.json"
        tracking.LEGACY_FILE = self.tmp_path / "outreach-history.json"
        tracking._regen_data_js_silently = lambda: None

        # migrate-script state
        self._orig_ms_tracking = migrate_script.TRACKING_FILE
        self._orig_ms_template = migrate_script.TRACKING_TEMPLATE
        self._orig_ms_legacy = migrate_script.LEGACY_FILE
        migrate_script.TRACKING_FILE = self.tmp_path / "tracking.json"
        migrate_script.TRACKING_TEMPLATE = self.tmp_path / "tracking-template.json"
        migrate_script.LEGACY_FILE = self.tmp_path / "outreach-history.json"

    def tearDown(self):
        tracking.TRACKING_FILE = self._orig_tracking
        tracking.TRACKING_TEMPLATE = self._orig_template
        tracking.LEGACY_FILE = self._orig_legacy
        tracking._regen_data_js_silently = self._orig_regen
        migrate_script.TRACKING_FILE = self._orig_ms_tracking
        migrate_script.TRACKING_TEMPLATE = self._orig_ms_template
        migrate_script.LEGACY_FILE = self._orig_ms_legacy
        self.tmp.cleanup()

    def _write_legacy(self, payload):
        (self.tmp_path / "outreach-history.json").write_text(json.dumps(payload))

    def _read_tracking(self):
        path = self.tmp_path / "tracking.json"
        return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Standalone migration script
# ---------------------------------------------------------------------------

class TestStandaloneMigrationScript(_TempIsolation):
    def test_migrates_two_connections(self):
        self._write_legacy(
            _legacy_with_connections(
                [
                    {"name": "Alice", "company": "Acme", "message": "hi1"},
                    {"name": "Bob", "company": "Beta", "message": "hi2"},
                ]
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            migrate_script.main()
        data = self._read_tracking()
        self.assertEqual(len(data["unlinked_outreach"]), 2)
        names = {o["name"] for o in data["unlinked_outreach"]}
        self.assertEqual(names, {"Alice", "Bob"})

    def test_migration_is_idempotent(self):
        self._write_legacy(
            _legacy_with_connections(
                [
                    {"name": "Alice", "company": "Acme", "message": "hi1"},
                    {"name": "Bob", "company": "Beta", "message": "hi2"},
                ]
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            migrate_script.main()
            migrate_script.main()
        data = self._read_tracking()
        self.assertEqual(len(data["unlinked_outreach"]), 2)

    def test_no_legacy_file_exits_cleanly(self):
        # No legacy file written.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            migrate_script.main()
        self.assertIn("Nothing to migrate", buf.getvalue())
        self.assertFalse((self.tmp_path / "tracking.json").exists())


# ---------------------------------------------------------------------------
# Auto-migration on tracking.load()
# ---------------------------------------------------------------------------

class TestAutoMigrationOnLoad(_TempIsolation):
    def test_auto_migrates_when_empty_and_legacy_present(self):
        self._write_legacy(
            _legacy_with_connections(
                [
                    {"name": "A", "company": "X", "message": "m"},
                    {"name": "B", "company": "Y", "message": "m"},
                    {"name": "C", "company": "Z", "message": "m"},
                ]
            )
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            data = tracking.load()
        self.assertEqual(len(data["unlinked_outreach"]), 3)
        self.assertIn("Migrated 3 legacy outreach entries", buf.getvalue())

    def test_does_not_remigrate_when_tracking_has_data(self):
        # Pre-seed tracking with one existing application.
        seeded = tracking._empty_tracking()
        seeded["applications"].append(
            {
                "id": "2026-04-11-acme-pm",
                "company": "Acme",
                "role": "PM",
                "status": "applied",
                "outreach": [],
                "dates": {"applied": "2026-04-11"},
            }
        )
        (self.tmp_path / "tracking.json").write_text(json.dumps(seeded))
        self._write_legacy(
            _legacy_with_connections(
                [{"name": "A", "company": "X", "message": "m"}]
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            data = tracking.load()
        self.assertEqual(data["unlinked_outreach"], [])

    def test_auto_migrate_false_skips_migration(self):
        self._write_legacy(
            _legacy_with_connections(
                [{"name": "A", "company": "X", "message": "m"}]
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            data = tracking.load(auto_migrate=False)
        self.assertEqual(data["unlinked_outreach"], [])

    def test_log_false_suppresses_migration_line(self):
        self._write_legacy(
            _legacy_with_connections(
                [{"name": "A", "company": "X", "message": "m"}]
            )
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            data = tracking.load(log=False)
        self.assertEqual(len(data["unlinked_outreach"]), 1)
        self.assertNotIn("Migrated", buf.getvalue())

    def test_corrupt_legacy_file_returns_empty(self):
        (self.tmp_path / "outreach-history.json").write_text("not valid json {{")
        with contextlib.redirect_stdout(io.StringIO()):
            data = tracking.load()
        self.assertEqual(data["unlinked_outreach"], [])
        self.assertEqual(data["metadata"]["version"], "3.0")

        # _merge_legacy directly should return 0.
        fresh = tracking._empty_tracking()
        self.assertEqual(
            tracking._merge_legacy(fresh, self.tmp_path / "outreach-history.json"),
            0,
        )

    def test_direction_filter_only_migrates_outgoing(self):
        self._write_legacy(
            _legacy_with_connections(
                [
                    {
                        "name": "Alice",
                        "company": "Acme",
                        "message": "outgoing1",
                        "direction": "OUTGOING",
                    },
                    {
                        "name": "Bob",
                        "company": "Beta",
                        "message": "incoming1",
                        "direction": "INCOMING",
                    },
                    {
                        "name": "Carol",
                        "company": "Gamma",
                        "message": "no-direction",
                    },
                ]
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            data = tracking.load()
        names = {o["name"] for o in data["unlinked_outreach"]}
        # Bob (INCOMING) filtered out. Alice explicitly OUTGOING, Carol has no
        # direction key (falsy) so also passes the `conn.get("direction") and ...`
        # guard.
        self.assertIn("Alice", names)
        self.assertIn("Carol", names)
        self.assertNotIn("Bob", names)

    def test_migrated_entries_have_legacy_id_prefix(self):
        self._write_legacy(
            _legacy_with_connections(
                [{"name": "Alice", "company": "Acme", "message": "m"}]
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            data = tracking.load()
        self.assertEqual(len(data["unlinked_outreach"]), 1)
        self.assertTrue(data["unlinked_outreach"][0]["id"].startswith("outreach-legacy-"))

    def test_legacy_applications_captured(self):
        self._write_legacy(
            _legacy_with_connections(
                conns=[],
                apps=[{"company": "Acme", "title": "PM", "status": "applied"}],
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            data = tracking.load()
        self.assertEqual(len(data["legacy_applications"]), 1)
        self.assertEqual(data["legacy_applications"][0]["company"], "Acme")

    def test_auto_migration_is_idempotent(self):
        self._write_legacy(
            _legacy_with_connections(
                [{"name": "Alice", "company": "Acme", "message": "m"}]
            )
        )
        # First run: loads (and migrates) then save.
        with contextlib.redirect_stdout(io.StringIO()):
            data = tracking.load()
            tracking.save(data)
        # Second run: tracking now populated, _is_empty_enough_to_migrate is False.
        with contextlib.redirect_stdout(io.StringIO()):
            data2 = tracking.load()
        self.assertEqual(len(data2["unlinked_outreach"]), 1)
        ids = [o["id"] for o in data2["unlinked_outreach"]]
        self.assertEqual(len(set(ids)), 1)

    def test_merge_legacy_directly_idempotent(self):
        """_merge_legacy should skip ids it has already added."""
        self._write_legacy(
            _legacy_with_connections(
                [{"name": "Alice", "company": "Acme", "message": "m"}]
            )
        )
        data = tracking._empty_tracking()
        n1 = tracking._merge_legacy(data, self.tmp_path / "outreach-history.json")
        n2 = tracking._merge_legacy(data, self.tmp_path / "outreach-history.json")
        self.assertEqual(n1, 1)
        self.assertEqual(n2, 0)
        self.assertEqual(len(data["unlinked_outreach"]), 1)


# ---------------------------------------------------------------------------
# Field preservation (_merge_legacy auto-migration path)
# ---------------------------------------------------------------------------

class TestFieldPreservation(_TempIsolation):
    def test_fields_preserved_through_merge(self):
        self._write_legacy(
            _legacy_with_connections(
                [
                    {
                        "name": "Alice",
                        "company": "Acme",
                        "message": "hello there",
                        "sent_date": "2025-03-01",
                        "accepted_date": "2025-03-03",
                        "replied_date": "2025-03-04",
                        "outcome": "replied",
                        "company_size": "startup",
                        "response_time_days": 2,
                        "recipient_role": "recruiter",
                    }
                ]
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            data = tracking.load()
        self.assertEqual(len(data["unlinked_outreach"]), 1)
        entry = data["unlinked_outreach"][0]
        self.assertEqual(entry["message"], "hello there")
        self.assertEqual(entry["dates"]["sent"], "2025-03-01")
        self.assertEqual(entry["dates"]["accepted"], "2025-03-03")
        self.assertEqual(entry["dates"]["replied"], "2025-03-04")
        self.assertEqual(entry["outcome"], "replied")
        self.assertEqual(entry["company_size"], "startup")
        self.assertEqual(entry["response_time_days"], 2)
        self.assertEqual(entry["recipient_role"], "recruiter")


if __name__ == "__main__":
    unittest.main()
