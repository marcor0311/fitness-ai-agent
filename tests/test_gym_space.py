from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from fitness_agent import gym_space


NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
ROUTINES = [{"id": "r", "title": "Libre", "exercises": [
    {"title": "A", "exercise_template_id": "a", "superset_id": None},
    {"title": "B", "exercise_template_id": "b", "superset_id": None},
]}]


def inventory(**station):
    base = {"id": "s1", "name": "Polea", "exercise_template_ids": ["a", "b"], "position": [1, 0, 2],
            "model": "cable_station", "rotation_deg": 90}
    base.update(station)
    return {"format": 1, "gyms": [{"id": "g", "name": "G", "zones": [], "nearby": [], "stations": [base]}]}


class SpaceServerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "gyms.json"
        self.backups = []

        def write(path, content):
            path.write_text(content, encoding="utf-8")

        catalog = gym_space.catalog_entries(
            {"a": {"id": "a", "title": "Triceps Pushdown", "equipment": "machine"},
             "b": {"id": "b", "title": "Chest Fly (Machine)", "equipment": "machine"}},
            {"templates": [{"id": "z", "title": "Leg Press (Machine)", "equipment": "machine"},
                           {"id": "n", "title": "Push Up", "equipment": "none"}]})
        self.editor = gym_space.Editor(self.path, ROUTINES, catalog, write,
                                        lambda content, now: self.backups.append(content), now=lambda: NOW)
        self.server, self.url = gym_space.serve(self.editor, 0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.folder.cleanup()

    def request(self, method, route, body=None, token=True, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        if token:
            headers["X-Editor-Token"] = self.editor.token
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        connection.request(method, route, body=data, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response.status, payload

    def test_page_is_public_but_data_needs_token_and_local_host(self):
        self.assertIn(f"/#token={self.editor.token}", self.url)
        status, page = self.request("GET", "/", token=False)
        self.assertEqual(status, 200)
        self.assertIn(b"three@0.160.0", page)
        self.assertIn(b"./machine_models.js", page)
        status, models = self.request("GET", "/machine_models.js", token=False)
        self.assertEqual(status, 200)
        self.assertIn(b"export function buildModel", models)
        self.assertEqual(self.request("GET", "/api/state", token=False)[0], 403)
        self.assertEqual(self.request("GET", "/api/state", host="evil.example")[0], 403)
        self.assertEqual(self.request("GET", "/", token=False, host="evil.example:80")[0], 403)
        self.assertEqual(self.request("POST", "/api/save", {"inventory": inventory()}, token=False)[0], 403)
        self.assertFalse(self.path.exists())

    def test_state_has_every_model_and_infers_models_for_old_stations(self):
        status, payload = self.request("GET", "/api/state")
        state = json.loads(payload)
        self.assertEqual(status, 200)
        self.assertEqual(state["source"], "nuevo")
        stations = state["inventory"]["gyms"][0]["stations"]
        self.assertEqual([(s["exercise_template_ids"], s["model"]) for s in stations],
                         [(["a"], "cable_station"), (["b"], "pec_deck")])
        # Solo ejercicios con máquina, barra o mancuernas; cada uno con su modelo.
        self.assertEqual([(t["id"], t["model"]) for t in state["catalog"]],
                         [("b", "pec_deck"), ("z", "leg_press"), ("a", "cable_station")])
        self.assertIn("generic", [m["id"] for m in state["models"]])
        self.assertEqual(state["routines"][0]["exercise_template_ids"], ["a", "b"])
        self.assertEqual(self.request("POST", "/api/graph", {"inventory": inventory()})[0], 404)

    def test_save_validates_and_keeps_a_single_backup(self):
        status, payload = self.request("POST", "/api/save", {"inventory": inventory(model="nave espacial")})
        self.assertEqual(status, 400)
        self.assertIn("model", json.loads(payload)["error"])
        self.assertFalse(self.path.exists())

        self.path.write_text(json.dumps(inventory(name="Antes")), encoding="utf-8")
        self.request("GET", "/api/state")  # La página recarga y toma el archivo como base.
        status, payload = self.request("POST", "/api/save", {"inventory": inventory(name="Después")})
        self.assertEqual(status, 200, payload)
        self.assertEqual(json.loads(payload), {"saved_at": NOW.isoformat()})
        saved = json.loads(self.path.read_text())["gyms"][0]["stations"][0]
        self.assertEqual((saved["name"], saved["model"], saved["rotation_deg"]), ("Después", "cable_station", 90))
        self.request("POST", "/api/save", {"inventory": inventory(name="Otra vez")})
        self.assertEqual(len(self.backups), 1)
        self.assertIn("Antes", self.backups[0])

    def test_save_refuses_when_file_changed_outside_editor(self):
        self.request("GET", "/api/state")
        self.path.write_text(json.dumps(inventory(name="Manual")), encoding="utf-8")
        status, payload = self.request("POST", "/api/save", {"inventory": inventory(name="Editor")})
        self.assertEqual(status, 409)
        self.assertIn("cambió fuera del editor", json.loads(payload)["error"])
        self.assertIn("Manual", self.path.read_text())

    def test_rejects_bad_requests(self):
        self.assertEqual(self.request("GET", "/otra")[0], 404)
        self.assertEqual(self.request("POST", "/api/save", None)[0], 415)
        status, payload = self.request("POST", "/api/save", {"otra": 1})
        self.assertEqual(status, 400)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
