from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json
import unittest
from urllib.error import HTTPError

from fitness_agent import routines
from fitness_agent.hevy import HevyClient, HevyError, NotFound
from test_hevy import FakeOpener


NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def hevy_routine(**changes):
    result = {
        "id": "r1", "title": "D", "folder_id": None, "updated_at": "2026-11-13T19:29:45.285Z",
        "exercises": [
            {"index": 0, "title": "Rear Delt", "exercise_template_id": "D8281C62", "superset_id": 0,
             "rest_seconds": 90, "notes": None, "sets": [
                 {"index": 0, "type": "normal", "weight_kg": 19.958088015168148, "reps": None,
                  "distance_meters": 0, "duration_seconds": 0, "custom_metric": 0, "rep_range": {"start": 12, "end": 15}},
             ]},
            {"index": 1, "title": "Iso-Lateral", "exercise_template_id": "91FAFBA3", "superset_id": None,
             "rest_seconds": 90, "notes": "OMITIR", "sets": [
                 {"index": 0, "type": "normal", "weight_kg": 40, "reps": 8,
                  "distance_meters": None, "duration_seconds": None, "custom_metric": None, "rep_range": None},
             ]},
        ],
    }
    result.update(changes)
    return result


class FakeClient:
    def __init__(self, current, after=None, templates=("D8281C62", "91FAFBA3", "NEW")):
        self.current, self.after, self.templates = current, after, templates
        self.calls = []

    def routine(self, routine_id):
        self.calls.append(("GET", routine_id))
        return deepcopy(self.after if self.after and ("PUT", routine_id) in [c[:2] for c in self.calls] else self.current)

    def update_routine(self, routine_id, body):
        self.calls.append(("PUT", routine_id, body))
        return {}

    def exercise(self, template_id):
        self.calls.append(("TEMPLATE", template_id))
        if template_id not in self.templates:
            raise NotFound("no")
        return {"id": template_id}


def edited():
    proposal = json.loads(json.dumps(routines.export(hevy_routine(), NOW)))
    proposal["routine"]["exercises"][0]["sets"][0]["rep_range"] = {"start": 8, "end": 12}
    return proposal


def applied_routine(proposal):
    """Lo que Hevy devolvería después de aplicar la propuesta, con su forma de lectura."""
    result = hevy_routine(updated_at="2026-11-17T12:00:00Z")
    for ex, wanted in zip(result["exercises"], proposal["routine"]["exercises"]):
        for s, w in zip(ex["sets"], wanted["sets"]):
            s.update(w)
    return result


class RoutineTests(unittest.TestCase):
    def backups(self):
        written = []

        def write(routine_id, now, content):
            written.append(json.loads(content))
            return f"backup-{routine_id}.json"
        return written, write

    def test_unchanged_export_does_not_write(self):
        client = FakeClient(hevy_routine())
        written, write = self.backups()
        result = routines.apply(client, routines.export(hevy_routine(), NOW), write, confirm=True, now=NOW)
        self.assertEqual(result["status"], "sin_cambios")
        self.assertFalse(written)
        self.assertNotIn("PUT", [c[0] for c in client.calls])

    def test_dry_run_lists_changes_without_writing(self):
        client = FakeClient(hevy_routine())
        written, write = self.backups()
        result = routines.apply(client, edited(), write, now=NOW)
        self.assertEqual(result["status"], "simulacion")
        self.assertIn("Rear Delt: series [normal 19.96 kg 12–15 reps] → [normal 19.96 kg 8–12 reps]", result["changes"])
        self.assertFalse(written)
        self.assertNotIn("PUT", [c[0] for c in client.calls])

    def test_version_check_blocks_stale_proposal(self):
        client = FakeClient(hevy_routine(updated_at="2026-11-20T00:00:00Z"))
        written, write = self.backups()
        with self.assertRaises(HevyError) as caught:
            routines.apply(client, edited(), write, confirm=True, now=NOW)
        self.assertIn("Exportala de nuevo", str(caught.exception))
        self.assertFalse(written)
        self.assertNotIn("PUT", [c[0] for c in client.calls])

    def test_confirm_backs_up_writes_and_verifies(self):
        proposal = edited()
        client = FakeClient(hevy_routine(), applied_routine(proposal))
        written, write = self.backups()
        result = routines.apply(client, proposal, write, confirm=True, now=NOW)
        self.assertEqual(result["status"], "aplicado")
        self.assertEqual(written[0]["routine_before"]["updated_at"], "2026-11-13T19:29:45.285Z")
        put = next(c for c in client.calls if c[0] == "PUT")
        self.assertEqual([c[0] for c in client.calls], ["GET", "PUT", "GET"])
        self.assertNotIn("exercise_title", json.dumps(put[2]))
        self.assertEqual(put[2]["routine"]["exercises"][0]["sets"][0]["rep_range"], {"start": 8, "end": 12})
        self.assertEqual(result["updated_at"], "2026-11-17T12:00:00Z")

    def test_failed_verification_points_to_backup(self):
        client = FakeClient(hevy_routine(), hevy_routine(updated_at="2026-11-17T12:00:00Z"))
        written, write = self.backups()
        with self.assertRaises(HevyError) as caught:
            routines.apply(client, edited(), write, confirm=True, now=NOW)
        self.assertIn("backup-r1.json", str(caught.exception))

    def test_reorder_and_unknown_exercise(self):
        proposal = edited()
        proposal["routine"]["exercises"].reverse()
        result = routines.apply(FakeClient(hevy_routine()), proposal, self.backups()[1], now=NOW)
        self.assertTrue(any(line.startswith("Ejercicios: Rear Delt → Iso-Lateral") for line in result["changes"]))
        proposal["routine"]["exercises"].append(dict(proposal["routine"]["exercises"][0], exercise_template_id="MISSING"))
        client = FakeClient(hevy_routine())
        with self.assertRaises(HevyError):
            routines.apply(client, proposal, self.backups()[1], confirm=True, now=NOW)
        self.assertNotIn("PUT", [c[0] for c in client.calls])

    def test_validation_rejects_invalid_files(self):
        def broken(change):
            proposal = edited()
            change(proposal)
            return proposal
        cases = [
            lambda p: p.update(format=2),
            lambda p: p["routine"]["exercises"][0]["sets"].clear(),
            lambda p: p["routine"]["exercises"][0]["sets"][0].update(type="heavy"),
            lambda p: p["routine"]["exercises"][0]["sets"][0].update(rep_range={"start": 12, "end": 8}),
            lambda p: p["routine"]["exercises"][0]["sets"][0].update(reps=8.5),
            lambda p: p["routine"]["exercises"][0].update(extra=True),
            lambda p: p["routine"]["exercises"][0].update(rest_seconds=-1),
            lambda p: p["routine"].update(title=" "),
        ]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(HevyError):
                routines.validate(broken(change))

    def test_find_routine_by_id_or_full_title(self):
        items = [hevy_routine(), hevy_routine(id="r2", title="E - Redemption 💫 (Now or Never)")]
        self.assertEqual(routines.find_routine(items, "r2")["id"], "r2")
        self.assertEqual(routines.find_routine(items, "E - Redemption (Now or Never)")["id"], "r2")
        with self.assertRaises(HevyError):
            routines.find_routine(items, "E")


class ClientWriteTests(unittest.TestCase):
    def test_put_sends_json_body(self):
        fake = FakeOpener([{"routine": {"id": "r1"}}])
        HevyClient("secret", opener=fake).update_routine("r1", {"routine": {"title": "D"}})
        req = fake.requests[0]
        self.assertEqual(req.get_method(), "PUT")
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertEqual(json.loads(req.data), {"routine": {"title": "D"}})

    def test_bad_request_shows_hevy_message_and_404_is_typed(self):
        error = HTTPError("https://api.hevyapp.com/v1/routines/r1", 400, "bad", {},
                          BytesIO(b'{"error": "invalid rep_range"}'))
        with self.assertRaises(HevyError) as caught:
            HevyClient("secret", opener=FakeOpener([error])).update_routine("r1", {})
        self.assertIn("invalid rep_range", str(caught.exception))
        missing = HTTPError("https://api.hevyapp.com/v1/routines/x", 404, "no", {}, BytesIO(b"{}"))
        with self.assertRaises(NotFound):
            HevyClient("secret", opener=FakeOpener([missing])).routine("x")

    def test_routine_id_mismatch_fails(self):
        with self.assertRaises(HevyError):
            HevyClient("secret", opener=FakeOpener([{"routine": {"id": "other"}}])).routine("r1")


if __name__ == "__main__":
    unittest.main()
