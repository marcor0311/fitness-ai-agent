import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from fitness_agent import gym_path


ROUTINES = [{"id": "r", "title": "B - Lower", "exercises": [
    {"title": "Leg Press", "exercise_template_id": "a", "superset_id": None},
    {"title": "Leg Curl", "exercise_template_id": "b", "superset_id": None},
    {"title": "Leg Press otra vez", "exercise_template_id": "c", "superset_id": None},
]}]
TEMPLATES = {"b": {"id": "b", "title": "Lying Leg Curl (Machine)", "equipment": "machine"}}


def inventory(layout=None):
    gym = {"id": "g", "name": "G", "zones": [], "nearby": [], "stations": [
        {"id": "prensa", "name": "Prensa", "exercise_template_ids": ["a", "c"], "position": [2, 0, 2],
         "model": "leg_press", "busy": 2},
        # Sin modelo: se infiere del catálogo por su ejercicio.
        {"id": "curl", "name": "Curl", "exercise_template_ids": ["b"], "position": [8, 0, 2]},
        {"id": "suelta", "name": "Sin ubicar", "exercise_template_ids": ["z"]},
    ]}
    if layout:
        gym["layout"] = layout
    return {"format": 1, "gyms": [gym]}


# Pared en x = 5 desde el borde hasta z = 8: para ir de una máquina a la otra hay que rodearla.
WALLED = {"outline": [[0, 0], [10, 0], [10, 10], [0, 10]], "walls": [{"id": "w", "from": [5, 0], "to": [5, 8], "doors": []}]}


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "gyms.json"
        self.viewer = gym_path.Viewer(self.path, ROUTINES, TEMPLATES, lambda: {})

    def tearDown(self):
        self.folder.cleanup()

    def write(self, content):
        self.path.write_text(json.dumps(content), encoding="utf-8")

    def test_missing_or_invalid_file_explains_what_to_do(self):
        with self.assertRaisesRegex(Exception, "gym space"):
            self.viewer.state()
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(Exception, "JSON"):
            self.viewer.state()

    def test_state_has_models_graph_and_legs(self):
        self.write(inventory())
        state = self.viewer.state()
        gym = state["gyms"][0]
        stations = {s["id"]: s for s in gym["stations"]}
        self.assertEqual(stations["prensa"]["model"], "leg_press")
        self.assertEqual(stations["curl"]["model"], "lying_leg_curl")
        self.assertEqual(stations["suelta"]["position"], None)
        self.assertEqual(len(stations["curl"]["size"]), 3)
        self.assertEqual(gym["floor"], [30, 20])
        self.assertEqual(gym["graph"]["unplaced"], ["suelta"])
        self.assertIsNone(gym["outline"])
        self.assertEqual(gym["walls"], [])
        current = gym["routines"][0]["current"]
        self.assertEqual([s["station_id"] for s in current["steps"]], ["prensa", "curl", "prensa"])
        self.assertEqual([s["leg_m"] for s in current["steps"]], [0.0, 6.0, 6.0])
        self.assertAlmostEqual(sum(s["leg_m"] for s in current["steps"]), current["walk_m"])
        self.assertTrue(all("path" not in s for s in current["steps"]))
        self.assertEqual(state["busy_labels"][2], "suele estar ocupada")

    def test_walls_give_walking_paths_around_them(self):
        self.write(inventory(WALLED))
        gym = self.viewer.state()["gyms"][0]
        self.assertEqual(gym["outline"], WALLED["outline"])
        self.assertEqual(gym["walls"][0]["pieces"], [([5, 0], [5, 8])])
        steps = gym["routines"][0]["current"]["steps"]
        path = steps[1]["path"]
        self.assertEqual((path[0], path[-1]), ([2, 2], [8, 2]))
        self.assertTrue(all(z > 8 for _, z in path[1:-1]), path)
        walked = sum(((bx - ax) ** 2 + (bz - az) ** 2) ** 0.5 for (ax, az), (bx, bz) in zip(path, path[1:]))
        self.assertAlmostEqual(walked, steps[1]["leg_m"], places=1)
        # A 6 m en línea recta (el límite de cercanía) pero a más de 6 caminando: no es unión, se marca como separada.
        self.assertEqual(gym["graph"]["edges"], [])
        self.assertEqual(len(gym["separated"]), 1)
        pair = gym["separated"][0]
        self.assertEqual((pair["a"], pair["b"], pair["straight_m"]), ("prensa", "curl", 6.0))
        self.assertAlmostEqual(pair["walking_m"], steps[1]["leg_m"], places=1)

    def test_edges_around_walls_follow_the_walking_path_and_closed_rooms_have_no_path(self):
        data = inventory(WALLED)
        data["gyms"][0]["settings"] = {"near_meters": 20}
        self.write(data)
        gym = self.viewer.state()["gyms"][0]
        self.assertEqual(gym["separated"], [])
        edge = gym["graph"]["edges"][0]
        self.assertEqual((edge["path"][0], edge["path"][-1]), ([2, 2], [8, 2]))
        # Pared de lado a lado sin puerta: al lado en línea recta y sin camino.
        closed = dict(WALLED, walls=[{"id": "w", "from": [5, 0], "to": [5, 10], "doors": []}])
        self.write(inventory(closed))
        gym = self.viewer.state()["gyms"][0]
        self.assertEqual([(p["a"], p["b"], p["walking_m"]) for p in gym["separated"]], [("prensa", "curl", None)])
        self.assertIsNone(gym["routines"][0]["current"])

    def test_without_layout_nothing_is_marked_as_separated(self):
        self.write(inventory())
        self.assertEqual(self.viewer.state()["gyms"][0]["separated"], [])


class PathServerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "gyms.json"
        self.path.write_text(json.dumps(inventory()), encoding="utf-8")
        self.viewer = gym_path.Viewer(self.path, ROUTINES, TEMPLATES, lambda: {})
        self.server, self.url = gym_path.serve(self.viewer, 0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.folder.cleanup()

    def request(self, method, route, token=True, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        if token:
            headers["X-Editor-Token"] = self.viewer.token
        connection.request(method, route, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response.status, payload

    def test_page_and_models_are_public_but_data_needs_token(self):
        self.assertIn(f"/#token={self.viewer.token}", self.url)
        status, page = self.request("GET", "/", token=False)
        self.assertEqual(status, 200)
        self.assertIn(b"Recorrido del gimnasio", page)
        self.assertIn(b"./machine_models.js", page)
        self.assertEqual(self.request("GET", "/machine_models.js", token=False)[0], 200)
        self.assertEqual(self.request("GET", "/api/path", token=False)[0], 403)
        self.assertEqual(self.request("GET", "/api/path", host="evil.example")[0], 403)
        status, payload = self.request("GET", "/api/path")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)["gyms"][0]["id"], "g")

    def test_is_read_only_and_reports_invalid_inventory(self):
        self.assertEqual(self.request("POST", "/api/save")[0], 405)
        self.assertEqual(self.request("GET", "/api/state")[0], 404)
        self.path.write_text(json.dumps({"format": 9}), encoding="utf-8")
        status, payload = self.request("GET", "/api/path")
        self.assertEqual(status, 400)
        self.assertIn("formato", json.loads(payload)["error"])


if __name__ == "__main__":
    unittest.main()
