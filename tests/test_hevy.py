from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from fitness_agent.cli import main, private_write
from fitness_agent.hevy import ACTIVE_ROUTINES, HevyClient, HevyError, NoRedirects, select_routines
from fitness_agent.review import build_snapshot, render_report


NOW = datetime(2026, 11, 13, 18, tzinfo=timezone.utc)


def routines():
    return [
        {"id": str(i), "title": title, "exercises": [{
            "title": "Ejercicio de prueba", "exercise_template_id": "test-exercise",
            "sets": [{"type": "warmup", "reps": 10}, {"type": "normal", "reps": 8}],
            "rest_seconds": None, "superset_id": 0,
        }]}
        for i, title in enumerate(ACTIVE_ROUTINES)
    ]


def workout(**changes):
    result = {
        "id": "workout-1", "title": ACTIVE_ROUTINES[1], "routine_id": "1",
        "start_time": "2026-11-12T12:00:00Z", "end_time": "2026-11-12T13:00:00Z",
        "exercises": deepcopy(routines()[1]["exercises"]),
    }
    result.update(changes)
    return result


class FakeOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, req, timeout):
        self.requests.append(req)
        payload = next(self.responses)
        if isinstance(payload, Exception):
            raise payload
        return BytesIO(json.dumps(payload).encode())


class ClientTests(unittest.TestCase):
    def test_pagination_and_read_only_auth(self):
        fake = FakeOpener([
            {"page": 1, "page_count": 2, "routines": routines()[:2]},
            {"page": 2, "page_count": 2, "routines": routines()[2:]},
        ])
        self.assertEqual(HevyClient("secret", opener=fake).routines(), routines())
        for req in fake.requests:
            self.assertEqual(req.get_method(), "GET")
            self.assertEqual(req.get_header("Api-key"), "secret")
            self.assertNotIn("secret", req.full_url)
        self.assertIn("page=2", fake.requests[1].full_url)

    def test_invalid_auth_does_not_echo_response_or_key(self):
        error = HTTPError("https://api.hevyapp.com/v1/routines", 401, "secret", {}, BytesIO(b"secret"))
        with self.assertRaises(HevyError) as caught:
            HevyClient("secret", opener=FakeOpener([error])).routines()
        self.assertNotIn("secret", str(caught.exception))

    def test_retry_rate_limit(self):
        error = HTTPError("https://api.hevyapp.com/v1/routines", 429, "rate limit", {"Retry-After": "1"}, BytesIO())
        delays = []
        fake = FakeOpener([error, {"page": 1, "page_count": 0, "routines": []}])
        self.assertEqual(HevyClient("secret", opener=fake, sleep=delays.append).routines(), [])
        self.assertEqual(delays, [1])

    def test_duplicate_pages_fail_instead_of_double_counting(self):
        payload = {"page": 1, "page_count": 2, "routines": routines()[:1]}
        second = dict(payload, page=2)
        with self.assertRaises(HevyError):
            HevyClient("secret", opener=FakeOpener([payload, second])).routines()

    def test_missing_page_fails(self):
        fake = FakeOpener([{"page": 1, "page_count": 2, "routines": []}])
        with self.assertRaises(HevyError):
            HevyClient("secret", opener=fake).routines()

    def test_redirect_is_blocked(self):
        with self.assertRaises(HevyError):
            NoRedirects().redirect_request(None, None, 302, "redirect", {}, "https://other.example")

    def test_json_format_error(self):
        with self.assertRaises(HevyError):
            HevyClient("secret", opener=FakeOpener([[]])).routines()


class ReviewTests(unittest.TestCase):
    def test_decorative_emoji_and_ambiguous_names(self):
        selected = routines()
        for routine, title in zip(selected, (
            "B - Lower 🌋", "D - I Am The Shadows 🧬",
            "E - Redemption 💫 (Now or Never)",
        )):
            routine["title"] = title
        self.assertEqual(len(select_routines(selected)), 3)
        with self.assertRaises(HevyError):
            select_routines(selected + routines()[:1])

    def test_exact_active_routines_not_substring(self):
        selected = routines()
        selected[1]["title"] = " D — I Am The Shadows "
        self.assertEqual(len(select_routines(selected)), 3)
        with self.assertRaises(HevyError):
            select_routines(routines()[:2])
        with self.assertRaises(HevyError):
            select_routines(routines() + routines()[:1])

    def test_scope_dates_id_and_title_fallback(self):
        workouts = [
            workout(),
            workout(id="fallback", routine_id=None),
            workout(id="wrong-id", routine_id="inactive"),
            workout(id="old", start_time="2025-01-01T00:00:00Z", end_time="2025-01-01T01:00:00Z"),
            workout(id="unfinished", end_time=None),
        ]
        snapshot = build_snapshot(routines(), workouts, {}, 12, NOW)
        self.assertEqual([s["workout"]["id"] for s in snapshot["sessions"]], ["workout-1", "fallback"])
        self.assertEqual(snapshot["unmatched_workouts_in_window"], 1)
        self.assertEqual(snapshot["sessions"][1]["match"], "title_fallback")

    def test_muscle_counts_exclude_warmups_and_ambiguous_titles(self):
        templates = {"test-exercise": {"primary_muscle_group": "back"}}
        snapshot = build_snapshot(routines(), [workout(), workout(id="fallback", routine_id=None)], templates, 12, NOW)
        report = render_report(snapshot)
        self.assertIn("| back | 1 | 0.08 |", report)
        self.assertIn("| Ejercicio de prueba | 1 | 8 reps | sin registrar | 0 |", report)
        self.assertIn("registrar un descanso", report)

    def test_invalid_date_fails_rather_than_dropping_evidence(self):
        for changes in ({"start_time": "invalid"}, {"start_time": "2026-11-12T12:00:00"}, {"end_time": "2026-11-12T11:00:00Z"}):
            with self.subTest(changes=changes), self.assertRaises(HevyError):
                build_snapshot(routines(), [workout(**changes)], {}, 12, NOW)


class CliTests(unittest.TestCase):
    def test_private_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.json"
            private_write(path, "first")
            private_write(path, "second")
            self.assertEqual(path.read_text(), "second")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_sync_end_to_end_without_network(self):
        client = unittest.mock.Mock()
        client.routines.return_value = routines()
        client.workouts.return_value = [workout()]
        client.exercise.return_value = {"id": "test-exercise", "primary_muscle_group": "back"}
        with tempfile.TemporaryDirectory() as folder, patch("fitness_agent.cli.ROOT", Path(folder)), \
                patch("fitness_agent.cli.load_key", return_value="secret"), \
                patch("fitness_agent.cli.HevyClient", return_value=client), \
                patch("fitness_agent.review.datetime") as clock:
            clock.now.return_value = NOW
            clock.fromisoformat.side_effect = datetime.fromisoformat
            self.assertEqual(main(["sync"]), 0)
            payload = json.loads((Path(folder) / "data/snapshot.json").read_text())
            self.assertEqual(len(payload["routines"]), 3)
            self.assertEqual(len(payload["sessions"]), 1)
            self.assertNotIn("secret", json.dumps(payload))
            self.assertTrue((Path(folder) / "data/review.md").exists())


if __name__ == "__main__":
    unittest.main()
