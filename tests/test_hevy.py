from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from fitness_agent import cloud
from fitness_agent.cli import main, private_write
from fitness_agent.hevy import ACTIVE_ROUTINES, HevyClient, HevyError, NoRedirects, select_routines
from fitness_agent.review import build_snapshot, load_preferences, render_report


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

    def test_exercise_catalog_uses_large_pages(self):
        templates = [{"id": "T1", "title": "Leg Press (Machine)", "equipment": "machine"}]
        fake = FakeOpener([{"page": 1, "page_count": 1, "exercise_templates": templates}])
        self.assertEqual(HevyClient("secret", opener=fake).exercise_templates(), templates)
        self.assertIn("exercise_templates?page=1&pageSize=100", fake.requests[0].full_url)

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
        self.assertIn("| Ejercicio de prueba | a realizar | 1 | 8 reps | sin registrar | 0 |", report)
        self.assertIn("Sin data/preferences.json", report)
        self.assertIn("registrar un descanso", report)

    def test_invalid_date_fails_rather_than_dropping_evidence(self):
        for changes in ({"start_time": "invalid"}, {"start_time": "2026-11-12T12:00:00"}, {"end_time": "2026-11-12T11:00:00Z"}):
            with self.subTest(changes=changes), self.assertRaises(HevyError):
                build_snapshot(routines(), [workout(**changes)], {}, 12, NOW)


def routines_with_reference():
    selected = routines()
    selected[1]["exercises"].append({
        "title": "Iso-Lateral Low Row", "exercise_template_id": "omitted",
        "sets": [{"type": "normal", "reps": 10}, {"type": "normal", "reps": 10}],
        "rest_seconds": 90, "superset_id": None,
    })
    selected[1]["exercises"][0]["rest_seconds"] = 60
    return selected


PREFERENCES = {
    "rest_seconds": 90,
    "D_exercise_order": ["test-exercise", "omitted"],
    "temporarily_omitted_exercises_by_routine": {"1": ["omitted"]},
}


class PreferenceTests(unittest.TestCase):
    def report(self, preferences, sessions=()):
        snapshot = build_snapshot(routines_with_reference(), list(sessions), {}, 12, NOW, preferences)
        return render_report(snapshot)

    def test_omitted_sets_are_reference_not_planned(self):
        report = self.report(PREFERENCES, [workout()])
        self.assertIn("Series de trabajo previstas: 1. Guardadas solo como referencia (omitidas por preferencia): 2.", report)
        self.assertIn("| Iso-Lateral Low Row | omitido, referencia | 2 |", report)
        self.assertIn("1 de 1 previstas.", report)
        # Sin preferencias, las mismas series cuentan como previstas.
        self.assertIn("Series de trabajo previstas: 3.", self.report(None))

    def test_chest_fly_sets_follow_preferences(self):
        selected = routines_with_reference()
        selected[1]["exercises"][0]["title"] = "Chest Fly (Machine)"
        report = render_report(build_snapshot(selected, [], {}, 12, NOW, dict(PREFERENCES, chest_fly_sets_per_session=2)))
        self.assertIn("Chest Fly (Machine): 1 series; la preferencia es 2.", report)

    def test_rest_and_order_follow_preferences(self):
        report = self.report(PREFERENCES)
        self.assertIn("Ejercicio de prueba: descanso de 60 s; la preferencia es 90 s.", report)
        self.assertNotIn("Iso-Lateral Low Row: descanso", report)
        self.assertNotIn("orden de D difiere", report)
        reordered = dict(PREFERENCES, D_exercise_order=["omitted", "test-exercise"])
        self.assertIn("El orden de D difiere del acordado desde la posición 1", self.report(reordered))

    def test_logged_omitted_exercise_and_stale_preference_are_flagged(self):
        session = workout(exercises=routines_with_reference()[1]["exercises"])
        self.assertIn("Se registró Iso-Lateral Low Row, marcado como omitido", self.report(PREFERENCES, [session]))
        stale = dict(PREFERENCES, temporarily_omitted_exercises_by_routine={"1": ["omitted", "gone"]})
        self.assertIn("La preferencia omite `gone`, que ya no está en la rutina", self.report(stale))

    def test_last_two_d_sessions_are_compared_by_template(self):
        selected = routines_with_reference()
        selected[1]["exercises"][0]["sets"][1]["rep_range"] = {"start": 8, "end": 12}
        first = workout(id="first", start_time="2026-11-01T12:00:00Z", end_time="2026-11-01T13:00:00Z")
        first["exercises"][0]["sets"][1].update(weight_kg=20, reps=9)
        second = workout(id="second", start_time="2026-11-08T12:00:00Z", end_time="2026-11-08T12:40:00Z")
        second["exercises"][0]["sets"][1].update(weight_kg=20, reps=7)
        second["exercises"][0]["superset_id"] = None
        report = render_report(build_snapshot(selected, [second, first], {}, 12, NOW, PREFERENCES))
        self.assertIn("## D: últimas dos sesiones por ejercicio", report)
        self.assertIn("| Ejercicio de prueba | 20 kg (44.1 lb) × 9 | 20 kg (44.1 lb) × 7 | -2 | 7 < 8 | cambió la superserie |",
                      report)
        self.assertNotIn("| Iso-Lateral Low Row | —", report)
        self.assertIn("Duración registrada: 60 min → 40 min.", report)

    def test_load_preferences_validates_before_sync(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preferences.json"
            self.assertIsNone(load_preferences(path))
            for content in ("{", "[]", '{"rest_seconds": "90"}',
                            '{"temporarily_omitted_exercises_by_routine": {"1": "omitted"}}'):
                path.write_text(content)
                with self.subTest(content=content), self.assertRaises(HevyError):
                    load_preferences(path)
            path.write_text(json.dumps(PREFERENCES))
            self.assertEqual(load_preferences(path), PREFERENCES)


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
            self.assertIsNone(payload["preferences"])

    def test_gym_graph_writes_analysis_from_snapshot(self):
        snapshot = {"routines": [{"id": "r", "title": "Libre", "exercises": [
            {"title": "A", "exercise_template_id": "a"}, {"title": "B", "exercise_template_id": "b"}]}]}
        inventory = {"format": 1, "gyms": [{"id": "g", "name": "G", "zones": [], "nearby": [], "stations": [
            {"id": "s1", "name": "Uno", "exercise_template_ids": ["a"], "position": [0, 0, 0]},
            {"id": "s2", "name": "Dos", "exercise_template_ids": ["b"], "position": [3, 0, 4]}]}]}
        with tempfile.TemporaryDirectory() as folder, patch("fitness_agent.cli.ROOT", Path(folder)), \
                patch("sys.stdout") as out:
            data = Path(folder) / "data"
            data.mkdir()
            (data / "snapshot.json").write_text(json.dumps(snapshot))
            self.assertEqual(main(["gym", "graph"]), 1)  # Sin inventario todavía.
            (data / "gyms.json").write_text(json.dumps(inventory))
            self.assertEqual(main(["gym", "graph"]), 0)
            analysis = json.loads((data / "gym-graph.json").read_text())
        self.assertEqual(analysis["gyms"][0]["graph"]["edges"], [{"a": "s1", "b": "s2", "meters": 5.0}])
        self.assertEqual(analysis["gyms"][0]["routines"][0]["current"]["walk_m"], 5.0)
        printed = "".join(call.args[0] for call in out.write.call_args_list)
        self.assertIn("Libre: 5,0 m.", printed)

    def test_invalid_preferences_stop_sync_before_calling_hevy(self):
        with tempfile.TemporaryDirectory() as folder, patch("fitness_agent.cli.ROOT", Path(folder)), \
                patch("fitness_agent.cli.HevyClient") as client:
            private_write(Path(folder) / "data/preferences.json", "{")
            self.assertEqual(main(["sync"]), 1)
            client.assert_not_called()
            self.assertFalse((Path(folder) / "data/snapshot.json").exists())


AUTH = "Bearer " + "x" * 40


def cloud_page(workouts, cursor, has_more=False):
    return {"workouts": workouts, "cursor": cursor, "has_more": has_more}


class CloudTests(unittest.TestCase):
    def run_pull(self, folder, responses, write=private_write):
        fake = FakeOpener(responses)
        client = cloud.CloudClient(AUTH, opener=fake)
        result = cloud.pull(client, Path(folder) / "store.json", Path(folder) / "cursor.json", write)
        return result, fake

    def test_pages_until_done_and_resumes_from_saved_cursor(self):
        with tempfile.TemporaryDirectory() as folder:
            result, fake = self.run_pull(folder, [
                cloud_page([{"id": "A", "title": "x"}], "1", True),
                cloud_page([{"id": "b", "title": "y"}], "2"),
            ])
            self.assertEqual(result, {"added": 2, "updated": 0, "total": 2, "cursor": "2"})
            self.assertIn("cursor=0", fake.requests[0].full_url)
            self.assertIn("cursor=1", fake.requests[1].full_url)
            self.assertEqual(fake.requests[0].get_header("Authorization"), AUTH)
            self.assertEqual(fake.requests[0].get_header("User-agent"), "fitness-agent-cli/1")
            self.assertNotIn("x" * 40, fake.requests[0].full_url)
            result, fake = self.run_pull(folder, [cloud_page([{"id": "a", "title": "editado"}], "2")])
            self.assertIn("cursor=2", fake.requests[0].full_url)
            self.assertEqual(result, {"added": 0, "updated": 1, "total": 2, "cursor": "2"})
            self.assertEqual((Path(folder) / "store.json").stat().st_mode & 0o777, 0o600)

    def test_cursor_is_saved_only_after_workouts(self):
        written = []

        def failing_write(path, content):
            written.append(path.name)
            if path.name == "cursor.json":
                raise OSError("disk full")
            private_write(path, content)

        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OSError):
                self.run_pull(folder, [cloud_page([{"id": "a", "title": "x"}], "1")], failing_write)
            self.assertEqual(written, ["store.json", "cursor.json"])
            self.assertFalse((Path(folder) / "cursor.json").exists())
            # La página se repite sin duplicar el entrenamiento ya guardado.
            result, fake = self.run_pull(folder, [cloud_page([{"id": "a", "title": "x"}], "1")])
            self.assertIn("cursor=0", fake.requests[0].full_url)
            self.assertEqual(result["total"], 1)

    def test_invalid_pages_and_auth_fail_without_leaking_secret(self):
        for payload in ([], cloud_page("x", "1"), cloud_page([], "abc"), cloud_page([{"title": "x"}], "1"),
                        cloud_page([], "0", True)):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as folder, self.assertRaises(HevyError):
                self.run_pull(folder, [payload])
        error = HTTPError("https://example/api", 401, "no", {}, BytesIO(AUTH.encode()))
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(HevyError) as caught:
            self.run_pull(folder, [error])
        self.assertNotIn("x" * 40, str(caught.exception))
        for auth, url in (("token", cloud.DEFAULT_URL), (AUTH, "http://insecure.example")):
            with self.subTest(auth=auth, url=url), self.assertRaises(HevyError):
                cloud.CloudClient(auth, url)

    def test_corrupt_local_store_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "store.json").write_text("{")
            with self.assertRaises(HevyError):
                self.run_pull(folder, [cloud_page([{"id": "a", "title": "x"}], "1")])
            self.assertEqual((Path(folder) / "store.json").read_text(), "{")


if __name__ == "__main__":
    unittest.main()
