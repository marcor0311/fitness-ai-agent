"""Forma del gimnasio: contorno, secciones, paredes y puertas, y distancia caminando entre puntos.

El contorno es un polígono en planta [[x, z], ...] en metros. Las secciones son polígonos con nombre dentro del
contorno (peso libre, cardio…); si tienen muros, cada borde bloquea el paso salvo en sus puertas, y si son abiertas
solo marcan una zona. Cada pared suelta es un segmento con huecos de puerta.
La distancia caminando es el camino más corto que no cruza el contorno ni las paredes: un grafo de visibilidad
con puntos de paso alrededor de esquinas, extremos de pared y marcos de puerta. Las máquinas no se consideran
obstáculos para caminar.

gym space dibuja el plano pintando salas sobre casillas de 1 m (layout.grid). De ahí deriva el contorno, una
sección abierta por sala (solo para nombrar zonas) y las paredes sueltas entre salas, con las puertas como huecos.
"""

import heapq
import math

from .hevy import HevyError


CLEARANCE = 0.35   # distancia de los puntos de paso a una esquina o extremo de pared
MIN_DOOR = 0.6
MIN_WALL = 0.2
EPS = 1e-9


def _is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _is_point(value):
    return isinstance(value, list) and len(value) == 2 and all(_is_number(v) for v in value)


def _orient(a, b, c):
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return 0 if abs(value) < EPS else (1 if value > 0 else -1)


def _on_segment(a, b, c):
    return (min(a[0], b[0]) - EPS <= c[0] <= max(a[0], b[0]) + EPS
            and min(a[1], b[1]) - EPS <= c[1] <= max(a[1], b[1]) + EPS)


def segments_cross(p1, p2, q1, q2):
    """Intersección de segmentos cerrados: tocar un extremo también bloquea el paso."""
    o1, o2, o3, o4 = _orient(p1, p2, q1), _orient(p1, p2, q2), _orient(q1, q2, p1), _orient(q1, q2, p2)
    if o1 != o2 and o3 != o4:
        return True
    return ((o1 == 0 and _on_segment(p1, p2, q1)) or (o2 == 0 and _on_segment(p1, p2, q2))
            or (o3 == 0 and _on_segment(q1, q2, p1)) or (o4 == 0 and _on_segment(q1, q2, p2)))


def point_in_polygon(point, polygon):
    x, z = point
    inside = False
    for (x1, z1), (x2, z2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            inside = not inside
    return inside


def segment_point_distance(a, b, p):
    dx, dz = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dz * dz
    t = 0 if length == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / length))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dz)


def wall_length(wall):
    return math.dist(wall["from"], wall["to"])


def wall_pieces(wall):
    """Tramos macizos de una pared, sin los huecos de sus puertas."""
    start, end = wall["from"], wall["to"]
    length = wall_length(wall)
    ux, uz = (end[0] - start[0]) / length, (end[1] - start[1]) / length
    cuts = sorted((d["offset"] - d["width"] / 2, d["offset"] + d["width"] / 2) for d in wall.get("doors", []))
    pieces, cursor = [], 0.0
    for a, b in cuts + [(length, length)]:
        if a - cursor > EPS:
            pieces.append(([start[0] + ux * cursor, start[1] + uz * cursor], [start[0] + ux * a, start[1] + uz * a]))
        cursor = max(cursor, b)
    return pieces


def polygon_area(polygon):
    return abs(sum(x1 * z2 - x2 * z1 for (x1, z1), (x2, z2) in zip(polygon, polygon[1:] + polygon[:1]))) / 2


def _validate_polygon(where, polygon, name):
    if not isinstance(polygon, list) or len(polygon) < 3 or not all(_is_point(p) for p in polygon):
        raise HevyError(f"{where}: {name} necesita al menos tres puntos [x, z].")
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    for i, (a, b) in enumerate(edges):
        if math.dist(a, b) < 0.05:
            raise HevyError(f"{where}: {name} tiene dos puntos seguidos en el mismo lugar.")
        for j in range(i + 2, len(edges)):
            if i == 0 and j == len(edges) - 1:
                continue
            if segments_cross(a, b, *edges[j]):
                raise HevyError(f"{where}: {name} se cruza consigo mismo.")
    if polygon_area(polygon) < 1:
        raise HevyError(f"{where}: {name} encierra menos de 1 m².")


def _validate_doors(where, doors, length):
    if not isinstance(doors, list):
        raise HevyError(f"{where}: doors debe ser una lista.")
    spans = []
    for door in doors:
        if not isinstance(door, dict) or not _is_number(door.get("offset")) or not _is_number(door.get("width")) \
                or door["width"] < MIN_DOOR:
            raise HevyError(f"{where}: cada puerta necesita offset y un ancho de al menos {MIN_DOOR} m.")
        a, b = door["offset"] - door["width"] / 2, door["offset"] + door["width"] / 2
        if a < -EPS or b > length + EPS:
            raise HevyError(f"{where}: una puerta queda fuera de su pared.")
        spans.append((a, b))
    spans.sort()
    if any(b1 > a2 + EPS for (_, b1), (a2, _) in zip(spans, spans[1:])):
        raise HevyError(f"{where}: dos puertas se superponen.")


def on_or_inside(point, polygon, tolerance=0.05):
    return point_in_polygon(point, polygon) or any(
        segment_point_distance(a, b, point) <= tolerance for a, b in zip(polygon, polygon[1:] + polygon[:1]))


def validate_layout(gym_id, layout):
    if not isinstance(layout, dict):
        raise HevyError(f"{gym_id}: layout debe ser un objeto con outline, sections y walls.")
    outline = layout.get("outline")
    _validate_polygon(gym_id, outline, "el contorno")
    walls = layout.get("walls", [])
    if not isinstance(walls, list):
        raise HevyError(f"{gym_id}: walls debe ser una lista.")
    ids = set()
    for wall in walls:
        if not isinstance(wall, dict) or not isinstance(wall.get("id"), str) or wall["id"] in ids:
            raise HevyError(f"{gym_id}: cada pared necesita un id único.")
        ids.add(wall["id"])
        where = f"{gym_id}/{wall['id']}"
        if not _is_point(wall.get("from")) or not _is_point(wall.get("to")) or wall_length(wall) < MIN_WALL:
            raise HevyError(f"{where}: la pared necesita from y to [x, z] separados al menos {MIN_WALL} m.")
        _validate_doors(where, wall.get("doors", []), wall_length(wall))
    grid = layout.get("grid")
    if grid is not None and not (isinstance(grid, dict) and isinstance(grid.get("cells"), list)
                                 and isinstance(grid.get("rooms"), list) and isinstance(grid.get("doors", []), list)):
        raise HevyError(f"{gym_id}: grid debe ser el plano de casillas de gym space (cells, rooms y doors).")
    sections = layout.get("sections", [])
    if not isinstance(sections, list):
        raise HevyError(f"{gym_id}: sections debe ser una lista.")
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("id"), str) or section["id"] in ids:
            raise HevyError(f"{gym_id}: cada sección necesita un id único.")
        ids.add(section["id"])
        where = f"{gym_id}/{section['id']}"
        if not isinstance(section.get("name"), str) or not section["name"].strip():
            raise HevyError(f"{where}: la sección necesita un nombre.")
        if type(section.get("walled", True)) is not bool:
            raise HevyError(f"{where}: walled debe ser true o false.")
        polygon = section.get("outline")
        _validate_polygon(where, polygon, f"la sección '{section['name']}'")
        if not all(on_or_inside(p, outline) for p in polygon):
            raise HevyError(f"{where}: la sección '{section['name']}' sale del contorno del gimnasio.")
        doors = section.get("doors", [])
        if not isinstance(doors, list) or not all(isinstance(d, dict) and type(d.get("edge")) is int
                                                  and 0 <= d["edge"] < len(polygon) for d in doors):
            raise HevyError(f"{where}: cada puerta de una sección necesita el número de borde (edge).")
        for edge, wall in enumerate(section_edges(section)):
            _validate_doors(f"{where} borde {edge + 1}", wall["doors"], wall_length(wall))


def section_edges(section):
    """Bordes de una sección como paredes, cada uno con sus puertas."""
    polygon = section["outline"]
    doors = section.get("doors", [])
    return [{"from": a, "to": b, "doors": [{"offset": d["offset"], "width": d["width"]} for d in doors if d["edge"] == i]}
            for i, (a, b) in enumerate(zip(polygon, polygon[1:] + polygon[:1]))]


def all_walls(layout):
    """Paredes que bloquean el paso: las sueltas y los bordes de las secciones con muros."""
    walls = list(layout.get("walls", []))
    for section in layout.get("sections", []):
        if section.get("walled", True):
            walls.extend(section_edges(section))
    return walls


def section_of(layout, point):
    """Id de la sección que contiene el punto; la más chica si hay secciones anidadas."""
    found = [s for s in (layout or {}).get("sections", []) if point_in_polygon(point, s["outline"])]
    return min(found, key=lambda s: polygon_area(s["outline"]))["id"] if found else None


class Walker:
    """Distancia caminando dentro del contorno, rodeando paredes. Calcula una vez por forma y reutiliza."""

    def __init__(self, layout):
        self.outline = [tuple(p) for p in layout["outline"]]
        self.blocks = list(zip(self.outline, self.outline[1:] + self.outline[:1]))
        for wall in all_walls(layout):
            self.blocks.extend((tuple(a), tuple(b)) for a, b in wall_pieces(wall))
        corners = {tuple(round(v, 4) for v in p) for block in self.blocks for p in block}
        step = CLEARANCE / math.sqrt(2)
        points = set()
        for x, z in corners:
            for dx, dz in ((step, step), (step, -step), (-step, step), (-step, -step)):
                p = (round(x + dx, 3), round(z + dz, 3))
                if self.inside(p) and all(segment_point_distance(a, b, p) >= 0.1 for a, b in self.blocks):
                    points.add(p)
        self.waypoints = sorted(points)
        self.links = {w: [] for w in self.waypoints}
        for i, a in enumerate(self.waypoints):
            for b in self.waypoints[i + 1:]:
                if self.visible(a, b):
                    meters = math.dist(a, b)
                    self.links[a].append((b, meters))
                    self.links[b].append((a, meters))
        self._sources = {}

    def inside(self, point):
        return point_in_polygon(point, self.outline)

    def visible(self, a, b):
        return not any(segments_cross(a, b, p, q) for p, q in self.blocks)

    def _reach(self, point):
        """Distancia desde un punto a cada punto de paso (Dijkstra) y el paso anterior de cada uno, en caché."""
        if point not in self._sources:
            best, previous = {}, {}
            queue = [(math.dist(point, w), w, point) for w in self.waypoints if self.visible(point, w)]
            heapq.heapify(queue)
            while queue:
                meters, node, before = heapq.heappop(queue)
                if node in best:
                    continue
                best[node], previous[node] = meters, before
                for following, step in self.links[node]:
                    if following not in best:
                        heapq.heappush(queue, (meters + step, following, node))
            self._sources[point] = (best, previous)
        return self._sources[point]

    def _meeting(self, a, b):
        """Punto de paso donde se unen los caminos más cortos desde a y desde b."""
        (from_a, _), (from_b, _) = self._reach(a), self._reach(b)
        shared = from_a.keys() & from_b.keys()
        return min(shared, key=lambda w: (from_a[w] + from_b[w], w)) if shared else None

    def distance(self, a, b):
        """Metros caminando entre dos puntos; infinito si alguno está fuera o no hay camino."""
        a, b = tuple(a), tuple(b)
        if a == b:
            return 0.0
        if not self.inside(a) or not self.inside(b):
            return math.inf
        if self.visible(a, b):
            return math.dist(a, b)
        meeting = self._meeting(a, b)
        return math.inf if meeting is None else self._reach(a)[0][meeting] + self._reach(b)[0][meeting]

    def path(self, a, b):
        """Polilínea caminando [(x, z), ...] con los extremos incluidos; None si no hay camino."""
        a, b = tuple(a), tuple(b)
        if not self.inside(a) or not self.inside(b):
            return None
        if a == b or self.visible(a, b):
            return [a, b]
        meeting = self._meeting(a, b)
        if meeting is None:
            return None

        def back(source, node):
            previous = self._reach(source)[1]
            chain = [node]
            while chain[-1] != source:
                chain.append(previous[chain[-1]])
            return chain

        return back(a, meeting)[::-1] + back(b, meeting)[1:]
