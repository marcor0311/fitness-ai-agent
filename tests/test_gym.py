import itertools
from pathlib import Path
import random
import unittest

from fitness_agent import gym, machines
from fitness_agent.hevy import ACTIVE_ROUTINES, HevyError


ROUTINE = {"id": "D", "title": "D", "exercises": [
    {"title": "Triceps", "exercise_template_id": "tri"},
    {"title": "Chest Fly", "exercise_template_id": "fly"},
    {"title": "Rear Delt", "exercise_template_id": "rear"},
    {"title": "Iso", "exercise_template_id": "iso"},
    {"title": "Curl", "exercise_template_id": "curl"},
]}


def inventory():
    return {"format": 1, "gyms": [{"id": "g", "name": "G", "zones": ["poleas", "maquinas", "pesas"],
                                   "nearby": [["poleas", "maquinas"]], "stations": [
        {"id": "polea", "name": "Polea", "zone": "poleas", "exercise_template_ids": ["tri", "curl"]},
        {"id": "fly", "name": "Pec deck", "zone": "maquinas", "exercise_template_ids": ["fly", "rear"]},
    ]}]}


class GymTests(unittest.TestCase):
    def test_template_has_one_station_per_exercise(self):
        result = gym.template([ROUTINE, ROUTINE])
        stations = result["gyms"][0]["stations"]
        self.assertEqual([s["exercise_template_ids"] for s in stations], [["tri"], ["fly"], ["rear"], ["iso"], ["curl"]])
        self.assertTrue(all(s["zone"] is None for s in stations))
        gym.validate(result)

    def test_route_counts_zone_changes_and_skips_omitted(self):
        result = gym.route(inventory()["gyms"][0], ROUTINE, {"temporarily_omitted_exercises_by_routine": {"D": ["iso"]}})
        self.assertEqual([zone for _, zone, _ in result["steps"]], ["poleas", "maquinas", "maquinas", "poleas"])
        self.assertEqual(result["zone_changes"], 2)
        self.assertEqual(result["far_changes"], 0)
        self.assertEqual(result["revisits"], ["poleas"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(gym.route(inventory()["gyms"][0], ROUTINE)["missing"], ["Iso"])

    def test_check_lines_and_validation(self):
        lines = gym.check_lines(inventory(), [ROUTINE], {"temporarily_omitted_exercises_by_routine": {"D": ["iso"]}})
        self.assertIn("  D: 2 cambios de zona (0 entre zonas no marcadas como cercanas).", lines)
        incomplete = inventory()
        incomplete["gyms"][0]["stations"][1]["zone"] = None
        self.assertIn("  D: recorrido sin calcular; faltan zona en 2 y estación en 1 ejercicios.",
                      gym.check_lines(incomplete, [ROUTINE]))
        bad_zone = inventory()
        bad_zone["gyms"][0]["stations"][0]["zone"] = "otra"
        duplicate = inventory()
        duplicate["gyms"][0]["stations"][1]["id"] = "polea"
        bad_pair = inventory()
        bad_pair["gyms"][0]["nearby"] = [["poleas", "x"]]
        for broken in (bad_zone, duplicate, bad_pair, {"format": 2, "gyms": []}):
            with self.subTest(broken=broken), self.assertRaises(HevyError):
                gym.validate(broken)



def placed_gym(stations, **settings):
    return {"id": "g", "name": "G", "zones": [], "nearby": [], "settings": settings, "stations": [
        {"id": sid, "name": sid.upper(), "exercise_template_ids": ids, "position": position, "busy": busy}
        for sid, ids, position, busy in stations]}


def routine(*template_ids, title="Libre", supersets=None):
    supersets = supersets or {}
    return {"id": "r", "title": title, "exercises": [
        {"title": t.upper(), "exercise_template_id": t, "superset_id": supersets.get(t)} for t in template_ids]}


def titles(plan):
    return [step["title"] for step in plan["steps"]]


class GraphTests(unittest.TestCase):
    def test_graph_joins_close_stations_and_weights_other_floors(self):
        g = placed_gym([
            ("a", ["x"], [0, 0, 0], None), ("b", ["y"], [3, 0, 4], 2),
            ("c", ["z"], [20, 0, 0], None), ("d", ["w"], [0, 4, 0], None), ("e", ["v"], None, None),
        ])
        graph = gym.proximity_graph(g)
        self.assertEqual(graph["edges"], [{"a": "a", "b": "b", "meters": 5.0}])
        self.assertEqual(graph["clusters"], [["a", "b"], ["c"], ["d"]])
        self.assertEqual(graph["unplaced"], ["e"])
        # Otra planta: 4 m de desnivel con peso 3 quedan a 12 m; con peso 1, a 4 m y conectadas.
        self.assertIn({"a": "a", "b": "d", "meters": 4.0},
                      gym.proximity_graph(dict(g, settings={"vertical_weight": 1}))["edges"])

    def test_proposal_reduces_walking_and_keeps_current_when_best(self):
        g = placed_gym([("a", ["a"], [0, 0, 0], 0), ("b", ["b"], [10, 0, 0], 0), ("c", ["c"], [1, 0, 0], 0)])
        result = gym.plan(g, routine("a", "b", "c"))
        self.assertEqual(result["current"]["walk_m"], 19.0)
        self.assertEqual(titles(result["proposal"]), ["A", "C", "B"])
        self.assertEqual(result["proposal"]["walk_m"], 10.0)
        self.assertEqual(result["proposal"]["moved"], 2)
        best = gym.plan(g, routine("a", "c", "b"))
        self.assertIsNone(best["proposal"])
        self.assertIn("menor costo", best["note"])
        # Con mucho peso al orden actual, no conviene mover nada.
        self.assertIsNone(gym.plan(placed_gym([("a", ["a"], [0, 0, 0], 0), ("b", ["b"], [10, 0, 0], 0),
                                               ("c", ["c"], [1, 0, 0], 0)], order_weight_m=50),
                                   routine("a", "b", "c"))["proposal"])

    def test_busy_station_moves_first(self):
        g = placed_gym([("a", ["a"], [0, 0, 0], 0), ("b", ["b"], [0, 0, 0.5], 3)])
        result = gym.plan(g, routine("a", "b"))
        self.assertEqual(titles(result["proposal"]), ["B", "A"])
        self.assertEqual(result["proposal"]["steps"][0]["busy"], 3)
        unknown = placed_gym([("a", ["a"], [0, 0, 0], None), ("b", ["b"], [0, 0, 0.5], None)])
        self.assertIsNone(gym.plan(unknown, routine("a", "b"))["proposal"])

    def test_supersets_move_together_and_omitted_are_skipped(self):
        g = placed_gym([("a", ["a"], [0, 0, 0], 0), ("fly", ["fly", "rear"], [8, 0, 0], 3),
                        ("c", ["c"], [0, 0, 1], 0), ("iso", ["iso"], [30, 0, 0], 0)])
        result = gym.plan(g, routine("a", "c", "iso", "fly", "rear", supersets={"fly": 0, "rear": 0}),
                          {"temporarily_omitted_exercises_by_routine": {"r": ["iso"]}})
        order = titles(result["proposal"])
        self.assertNotIn("ISO", order)
        self.assertEqual(order[order.index("FLY") + 1], "REAR")
        self.assertEqual(order[:2], ["FLY", "REAR"])

    def test_nearest_station_is_chosen_when_exercise_has_options(self):
        g = placed_gym([("a", ["a"], [0, 0, 0], 0), ("far", ["b"], [20, 0, 0], 0), ("near", ["b"], [1, 0, 0], 0)])
        result = gym.plan(g, routine("a", "b"))
        self.assertEqual([s["station_id"] for s in result["current"]["steps"]], ["a", "near"])
        self.assertEqual(result["current"]["walk_m"], 1.0)

    def test_fixed_order_and_missing_stations(self):
        g = placed_gym([("a", ["a"], [0, 0, 0], 0), ("b", ["b"], [10, 0, 0], 0), ("c", ["c"], [1, 0, 0], 0),
                        ("d", ["d"], None, 0)])
        fixed = gym.analyze({"format": 1, "gyms": [g]}, [routine("a", "b", "c", title=ACTIVE_ROUTINES[1] + " 🧬")],
                            {"D_exercise_order": ["a", "b", "c"]})["gyms"][0]["routines"][0]
        self.assertTrue(fixed["fixed_order"])
        self.assertIsNone(fixed["proposal"])
        self.assertEqual(fixed["current"]["walk_m"], 19.0)
        missing = gym.plan(g, routine("a", "d", "e"))
        self.assertIsNone(missing["current"])
        self.assertEqual(missing["missing"], ["D", "E"])

    def test_optimizer_matches_brute_force(self):
        rng = random.Random(7)
        for _ in range(25):
            n = rng.randint(2, 6)
            stations = [(f"s{i}", [f"e{i}"], [rng.uniform(0, 20), rng.choice([0, 0, 4]), rng.uniform(0, 15)],
                         rng.choice([None, 0, 1, 2, 3])) for i in range(n)]
            stations.append(("extra", [f"e{rng.randrange(n)}"], [rng.uniform(0, 20), 0, rng.uniform(0, 15)], 1))
            g = placed_gym(stations)
            cfg = dict(gym.settings(g), measure=gym.metric(g))
            units = gym._units(routine(*[f"e{i}" for i in range(n)]), set())
            for unit in units:
                unit["combos"] = gym._combos(unit, {t: [s for s in g["stations"] if t in s["exercise_template_ids"]]
                                                    for t in {f"e{i}" for i in range(n)}}, cfg["measure"])
            brute = min(gym._evaluate(cfg, units, order)["score"] for order in itertools.permutations(range(n)))
            self.assertAlmostEqual(gym._optimize(cfg, units)["score"], brute, places=6)

    def test_graph_lines_and_new_field_validation(self):
        g = placed_gym([("a", ["a"], [0, 0, 0], 0), ("b", ["b"], [10, 0, 0], 0), ("c", ["c"], [1, 0, 0], 0)])
        lines = gym.graph_lines(gym.analyze({"format": 1, "gyms": [g]}, [routine("a", "b", "c")]))
        self.assertIn("  Libre: 19,0 m. Propuesta: 10,0 m, 2 bloque(s) cambian de lugar:", lines)
        self.assertIn("    2. C · casi siempre libre", lines)
        broken_station = [
            {"position": [0, 0]}, {"position": [0, 0, float("nan")]}, {"size": [1, 0, 1]}, {"busy": 4},
            {"busy": True}, {"rotation_deg": "90"}, {"name": " "},
        ]
        for change in broken_station:
            inventory = {"format": 1, "gyms": [placed_gym([("a", ["a"], [0, 0, 0], 0)])]}
            inventory["gyms"][0]["stations"][0].update(change)
            with self.subTest(change=change), self.assertRaises(HevyError):
                gym.validate(inventory)
        for settings in ({"otra": 1}, {"near_meters": 0}, {"floor": [10]}, {"busy_weight_m": -1}):
            with self.subTest(settings=settings), self.assertRaises(HevyError):
                gym.validate({"format": 1, "gyms": [placed_gym([], **settings)]})



class MachineTests(unittest.TestCase):
    def test_exercises_map_to_the_physical_machine(self):
        cases = {
            ("Chest Fly (Machine)", "machine"): "pec_deck",
            ("Rear Delt Reverse Fly (Machine)", "machine"): "pec_deck",
            ("Rear Delt Reverse Fly (Cable)", "machine"): "cable_station",
            ("Lat Pulldown (Cable)", "machine"): "lat_pulldown",
            ("Straight Arm Lat Pulldown (Cable)", "machine"): "cable_station",
            ("Seated Cable Row - V Grip (Cable)", "machine"): "seated_row",
            ("Iso-Lateral Low Row", "machine"): "plate_row",
            ("Iso-Lateral Chest Press (Machine)", "machine"): "chest_press",
            ("Belt Squat (Machine)", "machine"): "belt_squat",
            ("Hack Squat (Machine)", "machine"): "hack_squat",
            ("Calf Press (Machine)", "machine"): "leg_press",
            ("Squat (Smith Machine)", "machine"): "smith",
            ("Pull Up (Assisted)", "machine"): "assisted",
            ("Pull Up", "machine"): "power_tower",
            ("Battle Ropes", "machine"): None,
            ("Kelso Shrug", "machine"): None,
            ("Wrist Roller", "machine"): None,
            ("Some New Machine", "machine"): "generic",
            ("Seated Incline Curl (Dumbbell)", "dumbbell"): "dumbbells",
            ("Bench Press (Barbell)", "barbell"): "bench_press",
            ("Front Squat", "barbell"): "squat_rack",
            ("Deadlift (Barbell)", "barbell"): "barbell_area",
            ("Push Up", "none"): None,
            ("Kettlebell Swing", "kettlebell"): None,
        }
        for (title, equipment), expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(machines.classify({"title": title, "equipment": equipment}), expected)

    def test_models_are_consistent(self):
        self.assertEqual(len(machines.MODEL_IDS), len(machines.MODELS))
        page = (Path(gym.__file__).parent / "machine_models.js").read_text(encoding="utf-8")
        for model_id in machines.MODEL_IDS:
            self.assertIn(f"  {model_id}(g) {{", page, f"Falta el modelo 3D de {model_id}")
        for model in machines.MODELS:
            self.assertIn(model.category, machines.CATEGORIES)
            self.assertEqual(len(model.size), 3)
        self.assertEqual(machines.infer({"exercise_template_ids": ["x", "b"]}, {"b": "pec_deck"}), "pec_deck")
        self.assertIsNone(machines.infer({"exercise_template_ids": ["x"]}, {}))

    def test_template_assigns_models_and_validation_rejects_unknown(self):
        result = gym.template([ROUTINE], {"fly": {"title": "Chest Fly (Machine)", "equipment": "machine"}})
        self.assertEqual([s["model"] for s in result["gyms"][0]["stations"]], [None, "pec_deck", None, None, None])
        gym.validate(result)
        result["gyms"][0]["stations"][0]["model"] = "otra"
        with self.assertRaises(HevyError):
            gym.validate(result)


if __name__ == "__main__":
    unittest.main()
