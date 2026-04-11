"""Unit tests for scripts/tracking.py (Phase 6 tracking refactor).

Every test is filesystem-isolated via tempfile.TemporaryDirectory and
injects a FixedClock for deterministic timestamps. No test touches the
real data/tracking.json or dashboard/data.js.

Run with:
    python -m unittest discover tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

import tracking  # noqa: E402
from fixtures import FixedClock  # noqa: E402


# ---------------------------------------------------------------------------
# TestEmptyTracking / _normalize_schema
# ---------------------------------------------------------------------------

class TestEmptyTracking(unittest.TestCase):
    def test_empty_tracking_has_all_top_level_keys(self):
        data = tracking._empty_tracking()
        for key in ("metadata", "applications", "unlinked_outreach",
                    "legacy_applications", "stats"):
            self.assertIn(key, data)
        self.assertEqual(data["metadata"]["version"], "3.0")
        self.assertEqual(data["metadata"]["created"], "")
        self.assertEqual(data["metadata"]["last_updated"], "")
        self.assertEqual(data["applications"], [])
        self.assertEqual(data["unlinked_outreach"], [])
        self.assertEqual(data["legacy_applications"], [])
        self.assertEqual(data["stats"], {})

    def test_normalize_schema_fills_missing_keys(self):
        data = {}
        result = tracking._normalize_schema(data)
        self.assertIs(result, data)  # mutates in place
        for key in ("metadata", "applications", "unlinked_outreach",
                    "legacy_applications", "stats"):
            self.assertIn(key, data)
        self.assertEqual(data["metadata"]["version"], "3.0")

    def test_normalize_schema_preserves_existing_values(self):
        data = {"metadata": {"version": "3.0", "created": "2026-01-01",
                             "last_updated": "2026-04-11"},
                "applications": [{"id": "x"}]}
        tracking._normalize_schema(data)
        self.assertEqual(data["metadata"]["created"], "2026-01-01")
        self.assertEqual(len(data["applications"]), 1)
        self.assertIn("unlinked_outreach", data)

    def test_normalize_schema_does_not_raise_on_empty_dict(self):
        try:
            tracking._normalize_schema({})
        except Exception as e:  # pragma: no cover
            self.fail(f"_normalize_schema({{}}) raised {e!r}")


# ---------------------------------------------------------------------------
# TestRecomputeStats
# ---------------------------------------------------------------------------

class TestRecomputeStats(unittest.TestCase):
    def test_empty_stats_all_zero(self):
        data = tracking._empty_tracking()
        tracking.recompute_stats(data)
        self.assertEqual(data["stats"]["total_applications"], 0)
        self.assertEqual(data["stats"]["total_outreach_sent"], 0)
        self.assertEqual(data["stats"]["positive_outcomes"], 0)
        self.assertEqual(data["stats"]["interviews_scheduled"], 0)

    def test_one_app_two_outreach_one_accepted_one_pending(self):
        data = tracking._empty_tracking()
        data["applications"].append({
            "id": "a1", "company": "Acme", "role": "PM",
            "outreach": [
                {"id": "o1", "name": "Alice", "outcome": "accepted"},
                {"id": "o2", "name": "Bob", "outcome": "pending"},
            ],
        })
        tracking.recompute_stats(data)
        self.assertEqual(data["stats"]["total_applications"], 1)
        self.assertEqual(data["stats"]["total_outreach_sent"], 2)
        self.assertEqual(data["stats"]["positive_outcomes"], 1)
        self.assertEqual(data["stats"]["interviews_scheduled"], 0)

    def test_mixed_apps_and_unlinked_outcomes(self):
        data = tracking._empty_tracking()
        data["applications"] = [
            {"id": "a1", "company": "Acme", "role": "PM",
             "outreach": [{"id": "o1", "outcome": "accepted"}]},
            {"id": "a2", "company": "Beta", "role": "SWE",
             "outreach": [
                 {"id": "o2", "outcome": "replied"},
                 {"id": "o3", "outcome": "interview"},
             ]},
        ]
        data["unlinked_outreach"] = [{"id": "o4", "outcome": "pending"}]
        tracking.recompute_stats(data)
        self.assertEqual(data["stats"]["total_applications"], 2)
        self.assertEqual(data["stats"]["total_outreach_sent"], 4)
        self.assertEqual(data["stats"]["positive_outcomes"], 3)
        self.assertEqual(data["stats"]["interviews_scheduled"], 1)

    def test_recompute_stats_is_idempotent(self):
        data = tracking._empty_tracking()
        data["applications"].append({
            "id": "a1", "company": "Acme", "role": "PM",
            "outreach": [{"id": "o1", "outcome": "interview"}],
        })
        tracking.recompute_stats(data)
        snapshot = dict(data["stats"])
        tracking.recompute_stats(data)
        self.assertEqual(data["stats"], snapshot)


# ---------------------------------------------------------------------------
# TestFindOrCreateApplication
# ---------------------------------------------------------------------------

class TestFindOrCreateApplication(unittest.TestCase):
    def setUp(self):
        self.clock = FixedClock("2026-04-11")
        self.data = tracking._empty_tracking()

    def test_creates_new_application_in_saved_state(self):
        app = tracking.find_or_create_application(
            self.data, company="Acme", role="PM",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        self.assertEqual(app["status"], "saved")
        self.assertEqual(app["company"], "Acme")
        self.assertEqual(app["role"], "PM")
        self.assertEqual(len(self.data["applications"]), 1)
        self.assertIs(self.data["applications"][0], app)

    def test_duplicate_lookup_returns_same_dict(self):
        app1 = tracking.find_or_create_application(
            self.data, company="Acme", role="PM",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        app2 = tracking.find_or_create_application(
            self.data, company="Acme", role="PM",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        self.assertIs(app1, app2)
        self.assertEqual(len(self.data["applications"]), 1)

    def test_case_insensitive_match(self):
        app1 = tracking.find_or_create_application(
            self.data, company="Acme", role="PM",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        app2 = tracking.find_or_create_application(
            self.data, company="acme", role="pm",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        self.assertIs(app1, app2)
        self.assertEqual(len(self.data["applications"]), 1)

    def test_new_app_id_and_saved_date_from_clock(self):
        app = tracking.find_or_create_application(
            self.data, company="Acme", role="PM",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        self.assertEqual(app["id"], "2026-04-11-acme-pm")
        self.assertEqual(app["dates"]["saved"], "2026-04-11")
        self.assertIsNone(app["dates"]["applied"])

    def test_does_not_match_if_only_company_matches(self):
        tracking.find_or_create_application(
            self.data, company="Acme", role="PM",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        app2 = tracking.find_or_create_application(
            self.data, company="Acme", role="Designer",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        self.assertEqual(len(self.data["applications"]), 2)
        self.assertEqual(app2["role"], "Designer")


# ---------------------------------------------------------------------------
# TestBuildOutreachEntry
# ---------------------------------------------------------------------------

class TestBuildOutreachEntry(unittest.TestCase):
    def test_id_and_sent_date_use_clock(self):
        clock = FixedClock("2026-04-11")
        entry = tracking.build_outreach_entry(
            name="Alice Example", recipient_role="Recruiter",
            msg_type="connection-request", message="Hi Alice",
            today=clock.today_str(),
        )
        self.assertEqual(entry["id"], "outreach-2026-04-11-alice-example")
        self.assertEqual(entry["dates"]["sent"], "2026-04-11")

    def test_message_length_matches_message(self):
        msg = "Hello there, this is a test message."
        entry = tracking.build_outreach_entry(
            name="Alice", recipient_role="PM", msg_type="inmail",
            message=msg, today="2026-04-11",
        )
        self.assertEqual(entry["message_length"], len(msg))
        self.assertEqual(entry["message"], msg)

    def test_optional_fields_default_none(self):
        entry = tracking.build_outreach_entry(
            name="Alice", recipient_role="PM", msg_type="inmail",
            message="m", today="2026-04-11",
        )
        self.assertIsNone(entry["linkedin_url"])
        self.assertIsNone(entry["variant"])
        self.assertEqual(entry["outcome"], "pending")
        self.assertIsNone(entry["response_time_days"])
        self.assertEqual(entry["follow_ups"], [])
        self.assertNotIn("company", entry)

    def test_optional_fields_set_when_provided(self):
        entry = tracking.build_outreach_entry(
            name="Alice", recipient_role="PM", msg_type="inmail",
            message="m", today="2026-04-11",
            linkedin_url="https://linkedin.com/in/alice",
            variant="variant-A",
        )
        self.assertEqual(entry["linkedin_url"], "https://linkedin.com/in/alice")
        self.assertEqual(entry["variant"], "variant-A")

    def test_company_kwarg_is_set_on_entry(self):
        entry = tracking.build_outreach_entry(
            name="Alice", recipient_role="PM", msg_type="inmail",
            message="m", today="2026-04-11", company="Acme",
        )
        self.assertEqual(entry["company"], "Acme")


# ---------------------------------------------------------------------------
# TestLogOutreach
# ---------------------------------------------------------------------------

class TestLogOutreach(unittest.TestCase):
    def setUp(self):
        self.clock = FixedClock("2026-04-11")
        self.data = tracking._empty_tracking()

    def test_unlinked_when_no_matching_app(self):
        entry, parent = tracking.log_outreach(
            self.data, name="Alice", company="Acme",
            recipient_role="PM", msg_type="inmail", message="Hi",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        self.assertIsNone(parent)
        self.assertEqual(len(self.data["unlinked_outreach"]), 1)
        self.assertIs(self.data["unlinked_outreach"][0], entry)
        self.assertEqual(entry["company"], "Acme")

    def test_nests_under_app_by_role_for_application(self):
        tracking.find_or_create_application(
            self.data, company="Acme", role="PM",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        entry, parent = tracking.log_outreach(
            self.data, name="Alice", company="Acme",
            recipient_role="Recruiter", msg_type="inmail", message="Hi",
            today=self.clock.today_str(), now=self.clock.now(),
            role_for_application="PM",
        )
        self.assertIsNotNone(parent)
        self.assertEqual(parent["company"], "Acme")
        self.assertEqual(parent["role"], "PM")
        self.assertEqual(len(parent["outreach"]), 1)
        self.assertIs(parent["outreach"][0], entry)
        # entry.company should NOT be set when nested
        self.assertNotIn("company", entry)
        self.assertEqual(self.data["unlinked_outreach"], [])

    def test_nests_under_app_by_job_id(self):
        app = tracking.find_or_create_application(
            self.data, company="Acme", role="PM",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        entry, parent = tracking.log_outreach(
            self.data, name="Alice", company="Acme",
            recipient_role="Recruiter", msg_type="inmail", message="Hi",
            today=self.clock.today_str(), now=self.clock.now(),
            job_id=app["id"],
        )
        self.assertIs(parent, app)
        self.assertEqual(len(app["outreach"]), 1)
        self.assertIs(app["outreach"][0], entry)

    def test_entry_id_uses_fixed_clock(self):
        entry, _ = tracking.log_outreach(
            self.data, name="Alice Example", company="Acme",
            recipient_role="PM", msg_type="inmail", message="Hi",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        self.assertEqual(entry["id"], "outreach-2026-04-11-alice-example")
        self.assertEqual(entry["dates"]["sent"], "2026-04-11")

    def test_job_id_takes_precedence_over_role_for_application(self):
        # Two apps at same company; job_id should pick the right one
        app1 = tracking.find_or_create_application(
            self.data, company="Acme", role="PM",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        app2 = tracking.find_or_create_application(
            self.data, company="Acme", role="Designer",
            today=self.clock.today_str(), now=self.clock.now(),
        )
        _, parent = tracking.log_outreach(
            self.data, name="Alice", company="Acme",
            recipient_role="PM", msg_type="inmail", message="Hi",
            today=self.clock.today_str(), now=self.clock.now(),
            job_id=app2["id"], role_for_application="PM",
        )
        self.assertIs(parent, app2)
        self.assertEqual(len(app1.get("outreach", [])), 0)


# ---------------------------------------------------------------------------
# TestUpdateOutcome
# ---------------------------------------------------------------------------

class TestUpdateOutcome(unittest.TestCase):
    def setUp(self):
        self.data = tracking._empty_tracking()
        tracking.log_outreach(
            self.data, name="Alice", company="Acme",
            recipient_role="PM", msg_type="inmail", message="Hi",
            today="2026-04-11",
        )

    def test_accepted_sets_response_time_days(self):
        ok = tracking.update_outcome(
            self.data, name="Alice", company="Acme",
            status="accepted", today="2026-04-14",
        )
        self.assertTrue(ok)
        entry = self.data["unlinked_outreach"][0]
        self.assertEqual(entry["outcome"], "accepted")
        self.assertEqual(entry["dates"]["accepted"], "2026-04-14")
        self.assertEqual(entry["response_time_days"], 3)

    def test_non_existent_entry_returns_false(self):
        ok = tracking.update_outcome(
            self.data, name="Ghost", company="Nobody", status="accepted",
        )
        self.assertFalse(ok)

    def test_replied_status(self):
        ok = tracking.update_outcome(
            self.data, name="Alice", company="Acme",
            status="replied", today="2026-04-13",
        )
        self.assertTrue(ok)
        entry = self.data["unlinked_outreach"][0]
        self.assertEqual(entry["outcome"], "replied")
        self.assertEqual(entry["dates"]["replied"], "2026-04-13")
        # replied does not compute response_time_days
        self.assertIsNone(entry["response_time_days"])

    def test_interview_status(self):
        ok = tracking.update_outcome(
            self.data, name="Alice", company="Acme",
            status="interview", today="2026-04-20",
        )
        self.assertTrue(ok)
        entry = self.data["unlinked_outreach"][0]
        self.assertEqual(entry["outcome"], "interview")
        self.assertEqual(entry["dates"]["interview"], "2026-04-20")

    def test_declined_status_does_not_change_dates(self):
        before = dict(self.data["unlinked_outreach"][0]["dates"])
        ok = tracking.update_outcome(
            self.data, name="Alice", company="Acme",
            status="declined", today="2026-04-15",
        )
        self.assertTrue(ok)
        entry = self.data["unlinked_outreach"][0]
        self.assertEqual(entry["outcome"], "declined")
        self.assertEqual(entry["dates"], before)

    def test_no_response_status(self):
        ok = tracking.update_outcome(
            self.data, name="Alice", company="Acme",
            status="no_response", today="2026-04-25",
        )
        self.assertTrue(ok)
        entry = self.data["unlinked_outreach"][0]
        self.assertEqual(entry["outcome"], "no_response")

    def test_invalid_status_returns_false_without_mutating(self):
        entry_before = json.loads(json.dumps(self.data["unlinked_outreach"][0]))
        ok = tracking.update_outcome(
            self.data, name="Alice", company="Acme",
            status="invalid", today="2026-04-15",
        )
        self.assertFalse(ok)
        self.assertEqual(self.data["unlinked_outreach"][0], entry_before)

    def test_sent_status_updates_sent_date(self):
        ok = tracking.update_outcome(
            self.data, name="Alice", company="Acme",
            status="sent", today="2026-04-12",
        )
        self.assertTrue(ok)
        entry = self.data["unlinked_outreach"][0]
        self.assertEqual(entry["dates"]["sent"], "2026-04-12")


# ---------------------------------------------------------------------------
# TestFindOutreach
# ---------------------------------------------------------------------------

class TestFindOutreach(unittest.TestCase):
    def setUp(self):
        self.data = tracking._empty_tracking()
        # nested outreach under an app
        app = tracking.find_or_create_application(
            self.data, company="Acme", role="PM", today="2026-04-11",
        )
        app["outreach"].append(tracking.build_outreach_entry(
            name="Nested Nina", recipient_role="PM", msg_type="inmail",
            message="hi", today="2026-04-11",
        ))
        # unlinked outreach
        self.data["unlinked_outreach"].append(tracking.build_outreach_entry(
            name="Unlinked Ulli", recipient_role="PM", msg_type="inmail",
            message="hi", today="2026-04-11", company="Beta",
        ))

    def test_case_insensitive_nested_lookup(self):
        entry, parent = tracking.find_outreach(
            self.data, name="nested nina", company="ACME",
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["name"], "Nested Nina")
        self.assertIsNotNone(parent)
        self.assertEqual(parent["company"], "Acme")

    def test_case_insensitive_unlinked_lookup(self):
        entry, parent = tracking.find_outreach(
            self.data, name="UNLINKED ULLI", company="beta",
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["name"], "Unlinked Ulli")
        self.assertIsNone(parent)

    def test_not_found_returns_none_none(self):
        entry, parent = tracking.find_outreach(
            self.data, name="Ghost", company="Nowhere",
        )
        self.assertIsNone(entry)
        self.assertIsNone(parent)

    def test_nested_entry_returns_parent(self):
        _entry, parent = tracking.find_outreach(
            self.data, name="Nested Nina", company="Acme",
        )
        self.assertIsNotNone(parent)
        self.assertEqual(parent["role"], "PM")

    def test_unlinked_entry_returns_none_parent(self):
        _entry, parent = tracking.find_outreach(
            self.data, name="Unlinked Ulli", company="Beta",
        )
        self.assertIsNone(parent)


# ---------------------------------------------------------------------------
# TestIterOutreach
# ---------------------------------------------------------------------------

class TestIterOutreach(unittest.TestCase):
    def test_empty_data_yields_nothing(self):
        data = tracking._empty_tracking()
        self.assertEqual(list(tracking.iter_outreach(data)), [])

    def test_mixed_data_yields_everything_with_correct_parent(self):
        data = tracking._empty_tracking()
        app1 = tracking.find_or_create_application(
            data, company="Acme", role="PM", today="2026-04-11",
        )
        app1["outreach"].append(tracking.build_outreach_entry(
            name="A1", recipient_role="PM", msg_type="inmail",
            message="m", today="2026-04-11",
        ))
        app2 = tracking.find_or_create_application(
            data, company="Beta", role="SWE", today="2026-04-11",
        )
        app2["outreach"].append(tracking.build_outreach_entry(
            name="B1", recipient_role="SWE", msg_type="inmail",
            message="m", today="2026-04-11",
        ))
        data["unlinked_outreach"].append(tracking.build_outreach_entry(
            name="U1", recipient_role="PM", msg_type="inmail",
            message="m", today="2026-04-11", company="Gamma",
        ))

        results = list(tracking.iter_outreach(data))
        self.assertEqual(len(results), 3)
        names = [e["name"] for e, _p in results]
        self.assertEqual(names, ["A1", "B1", "U1"])
        # Parents: first two should be apps, third should be None
        self.assertIs(results[0][1], app1)
        self.assertIs(results[1][1], app2)
        self.assertIsNone(results[2][1])

    def test_order_apps_before_unlinked(self):
        data = tracking._empty_tracking()
        # Add unlinked first, then app
        data["unlinked_outreach"].append(tracking.build_outreach_entry(
            name="First Unlinked", recipient_role="PM", msg_type="inmail",
            message="m", today="2026-04-11", company="Beta",
        ))
        app = tracking.find_or_create_application(
            data, company="Acme", role="PM", today="2026-04-11",
        )
        app["outreach"].append(tracking.build_outreach_entry(
            name="Second Nested", recipient_role="PM", msg_type="inmail",
            message="m", today="2026-04-11",
        ))
        results = list(tracking.iter_outreach(data))
        # apps-nested should come first even though unlinked was added first
        self.assertEqual(results[0][0]["name"], "Second Nested")
        self.assertEqual(results[1][0]["name"], "First Unlinked")


# ---------------------------------------------------------------------------
# TestLoadAndSave
# ---------------------------------------------------------------------------

class TestLoadAndSave(unittest.TestCase):
    def test_load_missing_tracking_missing_template_returns_empty_v3(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            data = tracking.load(
                path=tmp / "tracking.json",
                template_path=tmp / "template.json",
                legacy_path=tmp / "legacy.json",
                log=False,
            )
            self.assertEqual(data["metadata"]["version"], "3.0")
            self.assertEqual(data["applications"], [])
            self.assertEqual(data["unlinked_outreach"], [])

    def test_load_missing_tracking_with_template_copies_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            tracking_path = tmp / "tracking.json"
            template_path = tmp / "template.json"
            template_data = {
                "metadata": {"version": "3.0", "created": "2026-01-01",
                             "last_updated": ""},
                "applications": [],
                "unlinked_outreach": [],
                "legacy_applications": [],
                "stats": {},
            }
            template_path.write_text(json.dumps(template_data))

            data = tracking.load(
                path=tracking_path, template_path=template_path,
                legacy_path=tmp / "legacy.json", log=False,
            )
            self.assertEqual(data["metadata"]["version"], "3.0")
            self.assertEqual(data["metadata"]["created"], "2026-01-01")
            # load is read-only: tracking file should NOT be created
            self.assertFalse(tracking_path.exists())

    def test_save_writes_json_with_v3_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            tracking_path = tmp / "tracking.json"
            data = tracking._empty_tracking()
            tracking.save(data, path=tracking_path, today="2026-04-11",
                          regen_js=False)
            self.assertTrue(tracking_path.exists())
            with open(tracking_path) as f:
                loaded = json.load(f)
            for key in ("metadata", "applications", "unlinked_outreach",
                        "legacy_applications", "stats"):
                self.assertIn(key, loaded)
            self.assertEqual(loaded["metadata"]["version"], "3.0")

    def test_save_updates_last_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            data = tracking._empty_tracking()
            tracking.save(data, path=tmp / "tracking.json",
                          today="2026-04-11", regen_js=False)
            self.assertEqual(data["metadata"]["last_updated"], "2026-04-11")

    def test_save_recomputes_stats_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            data = tracking._empty_tracking()
            data["applications"].append({
                "id": "a1", "company": "Acme", "role": "PM",
                "outreach": [{"id": "o1", "outcome": "interview"}],
            })
            # Stats are empty initially
            self.assertEqual(data["stats"], {})
            tracking.save(data, path=tmp / "tracking.json",
                          today="2026-04-11", regen_js=False)
            self.assertEqual(data["stats"]["total_applications"], 1)
            self.assertEqual(data["stats"]["interviews_scheduled"], 1)
            self.assertEqual(data["stats"]["positive_outcomes"], 1)

    def test_save_regen_js_false_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            data = tracking._empty_tracking()
            try:
                tracking.save(data, path=tmp / "tracking.json",
                              today="2026-04-11", regen_js=False)
            except Exception as e:  # pragma: no cover
                self.fail(f"save(regen_js=False) raised {e!r}")

    def test_round_trip_save_then_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            tracking_path = tmp / "tracking.json"
            data1 = tracking._empty_tracking()
            tracking.find_or_create_application(
                data1, company="Acme", role="PM", today="2026-04-11",
            )
            data1["unlinked_outreach"].append(tracking.build_outreach_entry(
                name="Alice", recipient_role="PM", msg_type="inmail",
                message="hi", today="2026-04-11", company="Beta",
            ))
            tracking.save(data1, path=tracking_path, today="2026-04-11",
                          regen_js=False)

            data2 = tracking.load(
                path=tracking_path,
                template_path=tmp / "template.json",
                legacy_path=tmp / "legacy.json",
                log=False,
            )
            self.assertEqual(data2["metadata"]["version"], "3.0")
            self.assertEqual(len(data2["applications"]), 1)
            self.assertEqual(data2["applications"][0]["company"], "Acme")
            self.assertEqual(len(data2["unlinked_outreach"]), 1)
            self.assertEqual(data2["unlinked_outreach"][0]["name"], "Alice")


# ---------------------------------------------------------------------------
# TestLegacyMigration
# ---------------------------------------------------------------------------

class TestLegacyMigration(unittest.TestCase):
    def _write_legacy(self, tmp: Path, payload: dict) -> Path:
        p = tmp / "outreach-history.json"
        p.write_text(json.dumps(payload))
        return p

    def test_migrates_two_connections_into_unlinked_outreach(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            legacy = self._write_legacy(tmp, {
                "connections": [
                    {"name": "Alice", "company": "Acme",
                     "message": "Hello", "outcome": "accepted",
                     "sent_date": "2026-03-01"},
                    {"name": "Bob", "company": "Beta",
                     "message": "Hi", "outcome": "pending",
                     "sent_date": "2026-03-05"},
                ],
            })
            data = tracking._empty_tracking()
            count = tracking._merge_legacy(data, legacy)
            self.assertEqual(count, 2)
            self.assertEqual(len(data["unlinked_outreach"]), 2)

    def test_migrated_ids_have_legacy_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            legacy = self._write_legacy(tmp, {
                "connections": [
                    {"name": "Alice", "company": "Acme", "message": "m"},
                ],
            })
            data = tracking._empty_tracking()
            tracking._merge_legacy(data, legacy)
            self.assertTrue(
                data["unlinked_outreach"][0]["id"].startswith("outreach-legacy-")
            )

    def test_merge_legacy_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            legacy = self._write_legacy(tmp, {
                "connections": [
                    {"name": "Alice", "company": "Acme", "message": "m"},
                    {"name": "Bob", "company": "Beta", "message": "m"},
                ],
            })
            data = tracking._empty_tracking()
            first = tracking._merge_legacy(data, legacy)
            second = tracking._merge_legacy(data, legacy)
            self.assertEqual(first, 2)
            self.assertEqual(second, 0)
            self.assertEqual(len(data["unlinked_outreach"]), 2)

    def test_legacy_applications_go_into_legacy_bucket(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            legacy = self._write_legacy(tmp, {
                "applications": [
                    {"company": "Acme", "title": "PM", "status": "applied"},
                    {"company": "Beta", "title": "SWE", "status": "rejected"},
                ],
            })
            data = tracking._empty_tracking()
            tracking._merge_legacy(data, legacy)
            self.assertEqual(len(data["legacy_applications"]), 2)
            ids = {a["id"] for a in data["legacy_applications"]}
            self.assertIn("legacy-acme-pm", ids)
            self.assertIn("legacy-beta-swe", ids)

    def test_corrupt_legacy_file_returns_zero_and_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            p = tmp / "outreach-history.json"
            p.write_text("{not valid json")
            data = tracking._empty_tracking()
            try:
                count = tracking._merge_legacy(data, p)
            except Exception as e:  # pragma: no cover
                self.fail(f"_merge_legacy on corrupt file raised {e!r}")
            self.assertEqual(count, 0)
            self.assertEqual(data["unlinked_outreach"], [])

    def test_migration_preserves_outcome_message_and_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            legacy = self._write_legacy(tmp, {
                "connections": [
                    {
                        "name": "Alice",
                        "company": "Acme",
                        "message": "Hello Alice",
                        "outcome": "replied",
                        "sent_date": "2026-03-01",
                        "replied_date": "2026-03-05",
                        "accepted_date": "2026-03-03",
                    },
                ],
            })
            data = tracking._empty_tracking()
            tracking._merge_legacy(data, legacy)
            entry = data["unlinked_outreach"][0]
            self.assertEqual(entry["outcome"], "replied")
            self.assertEqual(entry["message"], "Hello Alice")
            self.assertEqual(entry["message_length"], len("Hello Alice"))
            self.assertEqual(entry["dates"]["sent"], "2026-03-01")
            self.assertEqual(entry["dates"]["replied"], "2026-03-05")
            self.assertEqual(entry["dates"]["accepted"], "2026-03-03")

    def test_load_with_auto_migrate_merges_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            legacy = self._write_legacy(tmp, {
                "connections": [
                    {"name": "Alice", "company": "Acme", "message": "m"},
                ],
            })
            data = tracking.load(
                path=tmp / "tracking.json",
                template_path=tmp / "template.json",
                legacy_path=legacy,
                log=False,
            )
            self.assertEqual(len(data["unlinked_outreach"]), 1)
            self.assertEqual(data["unlinked_outreach"][0]["name"], "Alice")

    def test_load_with_auto_migrate_false_skips_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            legacy = self._write_legacy(tmp, {
                "connections": [
                    {"name": "Alice", "company": "Acme", "message": "m"},
                ],
            })
            data = tracking.load(
                path=tmp / "tracking.json",
                template_path=tmp / "template.json",
                legacy_path=legacy,
                auto_migrate=False,
                log=False,
            )
            self.assertEqual(data["unlinked_outreach"], [])


if __name__ == "__main__":
    unittest.main()
