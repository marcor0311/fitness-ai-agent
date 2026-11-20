import math
import unittest

from fitness_agent import gym
from fitness_agent.hevy import HevyError
from fitness_agent.layout import Walker, section_of, validate_layout, wall_pieces


RECT = [[0, 0], [10, 0], [10, 6], [0, 6]]


def wall(start, end, *doors, wall_id="w1"):
    return {"id": wall_id, "from": start, "to": end, "doors": [{"offset": o, "width": w} for o, w in doors]}


class LayoutTests(unittest.TestCase):
    def test_open_room_is_straight_line(self):
        self.assertAlmostEqual(Walker({"outline": RECT, "walls": []}).distance([1, 3], [9, 3]), 8.0)

    def test_wall_forces_a_detour_and_door_shortens_it(self):
        # Pared en x=5 de z=0 a z=5: se rodea por el hueco de 1 m del fondo.
        blocked = Walker({"outline": RECT, "walls": [wall([5, 0], [5, 5])]})
        around = blocked.distance([4, 1], [6, 1])
        self.assertGreater(around, 8.0)
        self.assertLess(around, 9.5)
        door = Walker({"outline": RECT, "walls": [wall([5, 0], [5, 5], (1.0, 1.0))]})
        self.assertAlmostEqual(door.distance([4, 1], [6, 1]), 2.0)

    def test_path_matches_distance(self):
        walker = Walker({"outline": RECT, "walls": [wall([5, 0], [5, 5])]})
        path = walker.path([4, 1], [6, 1])
        self.assertEqual((path[0], path[-1]), ((4, 1), (6, 1)))
        self.assertAlmostEqual(sum(math.dist(p, q) for p, q in zip(path, path[1:])), walker.distance([4, 1], [6, 1]))
        self.assertTrue(all(z > 5 for _, z in path[1:-1]))  # pasa por el hueco del fondo
        self.assertEqual(walker.path([1, 1], [2, 2]), [(1, 1), (2, 2)])
        closed = Walker({"outline": RECT, "walls": [wall([5, 0], [5, 6])]})
        self.assertIsNone(closed.path([2, 3], [8, 3]))
        self.assertIsNone(closed.path([2, 3], [12, 3]))

    def test_closed_room_and_outside_points_are_unreachable(self):
        closed = Walker({"outline": RECT, "walls": [wall([5, 0], [5, 6])]})
        self.assertTrue(math.isinf(closed.distance([2, 3], [8, 3])))
        self.assertTrue(math.isinf(closed.distance([2, 3], [12, 3])))

    def test_l_shape_goes_around_the_inner_corner(self):
        l_shape = [[0, 0], [10, 0], [10, 4], [4, 4], [4, 10], [0, 10]]
        walker = Walker({"outline": l_shape, "walls": []})
        # La recta de (9, 2) a (2, 9) sale del local; el camino rodea la esquina (4, 4).
        expected = math.dist([9, 2], [4, 4]) + math.dist([4, 4], [2, 9])
        meters = walker.distance([9, 2], [2, 9])
        self.assertGreater(meters, expected - 0.01)
        self.assertLess(meters, expected + 0.6)

    def test_wall_pieces_skip_doors(self):
        pieces = wall_pieces(wall([0, 0], [6, 0], (1.5, 1.0), (4.0, 1.0)))
        self.assertEqual([[round(v, 2) for p in piece for v in p] for piece in pieces],
                         [[0, 0, 1.0, 0], [2.0, 0, 3.5, 0], [4.5, 0, 6, 0]])

    def test_validation(self):
        validate_layout("g", {"outline": RECT, "walls": [wall([5, 0], [5, 5], (1.0, 0.9))]})
        broken = [
            {"outline": [[0, 0], [1, 0]]},
            {"outline": [[0, 0], [4, 4], [4, 0], [0, 4]]},          # se cruza consigo mismo
            {"outline": [[0, 0], [0.5, 0], [0.5, 0.5]]},             # menos de 1 m²
            {"outline": RECT, "walls": [wall([1, 1], [1, 1.1])]},    # pared demasiado corta
            {"outline": RECT, "walls": [wall([0, 1], [3, 1], (0.2, 0.9))]},   # puerta fuera
            {"outline": RECT, "walls": [wall([0, 1], [3, 1], (1.0, 0.4))]},   # puerta angosta
            {"outline": RECT, "walls": [wall([0, 1], [5, 1], (1.0, 1.0), (1.6, 1.0))]},  # se superponen
            {"outline": RECT, "walls": [wall([0, 1], [5, 1]), wall([0, 2], [5, 2])]},    # ids repetidos
        ]
        for layout in broken:
            with self.subTest(layout=layout), self.assertRaises(HevyError):
                validate_layout("g", layout)


def section(section_id, name, outline, walled=True, doors=()):
    return {"id": section_id, "name": name, "outline": outline, "walled": walled,
            "doors": [{"edge": e, "offset": o, "width": w} for e, o, w in doors]}


# Sala de 4 × 4 en la esquina: bordes 0 (z=0), 1 (x=4), 2 (z=4) y 3 (x=0).
ROOM = [[0, 0], [4, 0], [4, 4], [0, 4]]


class SectionTests(unittest.TestCase):
    def test_walled_section_blocks_until_it_has_a_door(self):
        closed = Walker({"outline": RECT, "sections": [section("s1", "Peso libre", ROOM)]})
        self.assertTrue(math.isinf(closed.distance([2, 2], [7, 2])))
        door = Walker({"outline": RECT, "sections": [section("s1", "Peso libre", ROOM, doors=[(1, 2.0, 1.0)])]})
        self.assertAlmostEqual(door.distance([2, 2], [7, 2]), 5.0)
        self.assertEqual(door.path([2, 2], [7, 2]), [(2, 2), (7, 2)])
        open_zone = Walker({"outline": RECT, "sections": [section("s1", "Cardio", ROOM, walled=False)]})
        self.assertAlmostEqual(open_zone.distance([2, 2], [7, 2]), 5.0)

    def test_neighbouring_sections_connect_through_doors_on_both(self):
        left = section("s1", "Peso libre", [[0, 0], [5, 0], [5, 6], [0, 6]], doors=[(1, 3.0, 1.0)])
        right = section("s2", "Máquinas", [[5, 0], [10, 0], [10, 6], [5, 6]], doors=[(3, 3.0, 1.0)])
        walker = Walker({"outline": RECT, "sections": [left, right]})
        self.assertAlmostEqual(walker.distance([2, 3], [8, 3]), 6.0)
        only_one_side = dict(right, doors=[])
        self.assertTrue(math.isinf(Walker({"outline": RECT, "sections": [left, only_one_side]}).distance([2, 3], [8, 3])))

    def test_section_of_and_validation(self):
        layout = {"outline": RECT, "sections": [section("s1", "Sala", [[0, 0], [8, 0], [8, 6], [0, 6]]),
                                                 section("s2", "Rincón", ROOM)]}
        validate_layout("g", layout)
        self.assertEqual(section_of(layout, (2, 2)), "s2")   # la más chica gana si están anidadas
        self.assertEqual(section_of(layout, (6, 2)), "s1")
        self.assertIsNone(section_of(layout, (9, 2)))
        broken = [
            section("s1", "Afuera", [[8, 0], [12, 0], [12, 4], [8, 4]]),
            section("s1", " ", ROOM),
            section("s1", "Sala", ROOM, doors=[(7, 1.0, 1.0)]),
            section("s1", "Sala", ROOM, doors=[(0, 3.9, 1.0)]),
            dict(section("s1", "Sala", ROOM), walled="sí"),
        ]
        for bad in broken:
            with self.subTest(section=bad), self.assertRaises(HevyError):
                validate_layout("g", {"outline": RECT, "sections": [bad]})
        with self.assertRaises(HevyError):
            validate_layout("g", {"outline": RECT, "sections": [section("x", "A", ROOM)],
                                  "walls": [wall([5, 0], [5, 5], wall_id="x")]})


    def test_painted_plan_layout_walks_through_doors(self):
        # Lo que deriva gym space de un plano pintado: L de 30 × 20, Cardio y Vestuario con puerta de 1 m.
        plan = {
            "outline": [[0, 0], [30, 0], [30, 15], [25, 15], [25, 20], [0, 20]],
            "sections": [
                {"id": "seccion-a-1", "name": "Sala principal", "walled": False, "doors": [], "room": "a",
                 "outline": [[0, 0], [20, 0], [20, 8], [30, 8], [30, 15], [25, 15], [25, 20], [6, 20], [6, 15], [0, 15]]},
                {"id": "seccion-b-1", "name": "Cardio", "walled": False, "doors": [], "room": "b",
                 "outline": [[20, 0], [30, 0], [30, 8], [20, 8]]},
                {"id": "seccion-c-1", "name": "Vestuario", "walled": False, "doors": [], "room": "c",
                 "outline": [[0, 15], [6, 15], [6, 20], [0, 20]]},
            ],
            "walls": [wall([6, 15], [6, 20], wall_id="pared-1"), wall([20, 0], [20, 8], (3.5, 1), wall_id="pared-2"),
                      wall([20, 8], [30, 8], wall_id="pared-3"), wall([0, 15], [6, 15], (2.5, 1), wall_id="pared-4")],
            "grid": {"cell": 1, "cols": 30, "rows": 20, "cells": [], "rooms": [], "doors": []},
        }
        validate_layout("g", plan)
        walker = Walker(plan)
        # Pegados a ambos lados de la pared de Cardio: 3 m en línea recta, más del doble caminando por la puerta.
        self.assertGreater(walker.distance([18.5, 6.5], [21.5, 6.5]), 6.0)
        self.assertAlmostEqual(walker.distance([2.5, 17], [2.5, 13]), 4.0)
        self.assertFalse(walker.inside([27, 17]))
        self.assertEqual(section_of(plan, [25, 4]), "seccion-b-1")
        self.assertEqual(section_of(plan, [10, 10]), "seccion-a-1")
        with self.assertRaises(HevyError):
            validate_layout("g", dict(plan, grid=["no"]))


class WalkingGraphTests(unittest.TestCase):
    def inventory(self, walls):
        stations = [
            {"id": "a", "name": "A", "exercise_template_ids": ["a"], "position": [4, 0, 1]},
            {"id": "b", "name": "B", "exercise_template_ids": ["b"], "position": [6, 0, 1]},
            {"id": "c", "name": "C", "exercise_template_ids": ["c"], "position": [12, 0, 1]},
        ]
        return {"format": 1, "gyms": [{"id": "g", "name": "G", "zones": [], "nearby": [], "stations": stations,
                                       "layout": {"outline": RECT, "walls": walls}}]}

    def test_graph_uses_walking_distance_and_flags_outside(self):
        routine = {"id": "r", "title": "R", "exercises": [
            {"title": "A", "exercise_template_id": "a"}, {"title": "B", "exercise_template_id": "b"}]}
        open_gym = gym.analyze(self.inventory([]), [routine])["gyms"][0]
        self.assertEqual(open_gym["graph"]["edges"], [{"a": "a", "b": "b", "meters": 2.0}])
        self.assertEqual(open_gym["graph"]["outside"], ["c"])
        self.assertTrue(open_gym["graph"]["walking"])
        walled = gym.analyze(self.inventory([wall([5, 0], [5, 5])]), [routine])["gyms"][0]
        self.assertEqual(walled["graph"]["edges"], [])  # 2 m en línea recta, más de 8 m caminando.
        self.assertGreater(walled["routines"][0]["current"]["walk_m"], 8)
        closed = gym.analyze(self.inventory([wall([5, 0], [5, 6])]), [routine])["gyms"][0]
        self.assertEqual(closed["graph"]["edges"], [])
        self.assertIsNone(closed["routines"][0]["current"])
        self.assertIn("puertas", closed["routines"][0]["note"])
        lines = gym.graph_lines(gym.analyze(self.inventory([]), [routine]))
        self.assertIn("caminando por la forma del gimnasio", lines[0])
        self.assertIn("  Fuera de la forma del gimnasio: C.", lines)

    def test_graph_reports_sections(self):
        inventory = self.inventory([])
        inventory["gyms"][0]["layout"]["sections"] = [section("s1", "Peso libre", [[0, 0], [5, 0], [5, 6], [0, 6]], walled=False)]
        analysis = gym.analyze(inventory, [])
        graph = analysis["gyms"][0]["graph"]
        self.assertEqual(graph["sections"], {"a": "s1", "b": None})
        self.assertEqual(graph["section_names"], {"s1": "Peso libre"})
        self.assertIn("  Sección Peso libre: A.", gym.graph_lines(analysis))

    def test_invalid_layout_is_rejected_by_inventory_validation(self):
        inventory = self.inventory([])
        inventory["gyms"][0]["layout"]["outline"] = [[0, 0], [4, 4], [4, 0], [0, 4]]
        with self.assertRaises(HevyError):
            gym.validate(inventory)


if __name__ == "__main__":
    unittest.main()
