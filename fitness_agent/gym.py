"""Inventario por gimnasio (docs/draft.md): estaciones, zonas y ejercicios de Hevy que admite cada una.

Con posiciones en metros, calcula un grafo de cercanía entre estaciones y, para cada rutina, los metros
recorridos y un orden propuesto que adelanta las máquinas más ocupadas sin alejarse del orden acordado.
"""

import itertools
import math

from .hevy import ACTIVE_ROUTINES, HevyError, normalize
from .layout import Walker, section_of, validate_layout
from .machines import MODEL_IDS, classify
from .review import omitted_ids


FORMAT = 1
# Valores por defecto de "settings" de cada gimnasio. Las penalizaciones se expresan en metros equivalentes.
DEFAULT_SETTINGS = {
    "floor": [30, 20],       # ancho (x) y fondo (z) del plano, en metros
    "near_meters": 6,        # distancia máxima para unir dos estaciones en el grafo
    "vertical_weight": 3,    # cada metro de desnivel (otra planta) cuenta como este número de metros
    "busy_weight_m": 5,      # costo por nivel de ocupación y por cada lugar que se retrasa la estación
    "order_weight_m": 3,     # costo por cada lugar que un ejercicio se aleja de su posición actual
}
BUSY_LABELS = {0: "casi siempre libre", 1: "a veces ocupada", 2: "suele estar ocupada", 3: "casi siempre ocupada"}
MAX_STATION_OPTIONS = 3
MAX_COMBOS = 4
SEARCH_LIMIT = 4_000_000


def template(routines, templates=None):
    """Primer borrador: una estación por ejercicio de las rutinas, sin zona ni posición.

    Con el catálogo de ejercicios, cada estación recibe el modelo de máquina que usa el espacio 3D.
    """
    stations, seen = [], set()
    for routine in routines:
        for ex in routine.get("exercises", []):
            template_id = ex["exercise_template_id"]
            if template_id in seen:
                continue
            seen.add(template_id)
            stations.append({
                "id": f"estacion-{len(stations) + 1}", "name": ex.get("title") or template_id, "type": None,
                "zone": None, "accessories": [], "notes": "", "exercise_template_ids": [template_id],
                "model": classify((templates or {}).get(template_id) or {}),
            })
    return {
        "format": FORMAT,
        "instructions": "Completar zone con una de 'zones'. Unir en una estación los ejercicios que comparten máquina "
                        "(por ejemplo Chest Fly y Rear Delt Reverse Fly). 'nearby' lista pares de zonas cercanas.",
        "gyms": [{"id": "principal", "name": "Gimnasio actual", "zones": [], "nearby": [], "stations": stations}],
    }


def is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def is_vector(value, length, positive=False):
    return isinstance(value, list) and len(value) == length and all(
        is_number(v) and (not positive or v > 0) for v in value)


def validate_settings(gym):
    cfg = gym.get("settings", {})
    if not isinstance(cfg, dict) or not set(cfg) <= set(DEFAULT_SETTINGS):
        raise HevyError(f"{gym['id']}: settings solo admite {', '.join(DEFAULT_SETTINGS)}.")
    if "floor" in cfg and not is_vector(cfg["floor"], 2, positive=True):
        raise HevyError(f"{gym['id']}: floor debe ser [ancho, fondo] en metros positivos.")
    for name in ("near_meters", "vertical_weight", "busy_weight_m", "order_weight_m"):
        if name in cfg and (not is_number(cfg[name]) or cfg[name] < 0 or (name == "near_meters" and cfg[name] == 0)):
            raise HevyError(f"{gym['id']}: {name} debe ser un número positivo.")


def validate_placement(gym, station):
    where = f"{gym['id']}/{station['id']}"
    if station.get("position") is not None and not is_vector(station["position"], 3):
        raise HevyError(f"{where}: position debe ser [x, y, z] en metros o null.")
    if station.get("size") is not None and not is_vector(station["size"], 3, positive=True):
        raise HevyError(f"{where}: size debe ser [ancho, alto, fondo] en metros positivos o null.")
    if station.get("rotation_deg") is not None and not is_number(station["rotation_deg"]):
        raise HevyError(f"{where}: rotation_deg debe ser un número de grados o null.")
    if station.get("model") is not None and station["model"] not in MODEL_IDS:
        raise HevyError(f"{where}: model '{station['model']}' no es un modelo de máquina conocido.")
    busy = station.get("busy")
    if busy is not None and (type(busy) is not int or busy not in BUSY_LABELS):
        raise HevyError(f"{where}: busy debe ser 0, 1, 2, 3 o null.")


def validate(inventory):
    if not isinstance(inventory, dict) or inventory.get("format") != FORMAT or not isinstance(inventory.get("gyms"), list):
        raise HevyError("El inventario no tiene el formato esperado (format 1 con lista gyms).")
    gym_ids = set()
    for gym in inventory["gyms"]:
        if not isinstance(gym, dict) or not isinstance(gym.get("id"), str) or gym["id"] in gym_ids:
            raise HevyError("Cada gimnasio necesita un id único.")
        gym_ids.add(gym["id"])
        validate_settings(gym)
        if gym.get("layout") is not None:
            validate_layout(gym["id"], gym["layout"])
        zones = gym.get("zones")
        if not isinstance(zones, list) or not all(isinstance(z, str) and z for z in zones) or len(set(zones)) != len(zones):
            raise HevyError(f"{gym['id']}: zones debe ser una lista de nombres únicos.")
        for pair in gym.get("nearby", []):
            if not isinstance(pair, list) or len(pair) != 2 or not set(pair) <= set(zones):
                raise HevyError(f"{gym['id']}: cada par de nearby debe nombrar dos zonas existentes.")
        station_ids = set()
        for station in gym.get("stations", []):
            if not isinstance(station, dict) or not isinstance(station.get("id"), str) or station["id"] in station_ids:
                raise HevyError(f"{gym['id']}: cada estación necesita un id único.")
            station_ids.add(station["id"])
            if not isinstance(station.get("name"), str) or not station["name"].strip():
                raise HevyError(f"{gym['id']}/{station['id']}: la estación necesita un nombre.")
            validate_placement(gym, station)
            if station.get("zone") is not None and station["zone"] not in zones:
                raise HevyError(f"{gym['id']}/{station['id']}: la zona '{station['zone']}' no está en zones.")
            ids = station.get("exercise_template_ids")
            if not isinstance(ids, list) or not all(isinstance(i, str) and i for i in ids):
                raise HevyError(f"{gym['id']}/{station['id']}: exercise_template_ids debe ser una lista de IDs.")
    return inventory


def route(gym, routine, preferences=None):
    """Recorrido por zonas siguiendo el orden de la rutina, sin los ejercicios omitidos."""
    omitted = omitted_ids(preferences, routine["id"])
    stations = {}
    for station in gym.get("stations", []):
        for template_id in station["exercise_template_ids"]:
            stations.setdefault(template_id, []).append(station)
    near = {frozenset(pair) for pair in gym.get("nearby", [])}
    steps, missing, unzoned = [], [], []
    for ex in routine.get("exercises", []):
        if ex["exercise_template_id"] in omitted:
            continue
        options = stations.get(ex["exercise_template_id"], [])
        if not options:
            missing.append(ex["title"])
            continue
        station = options[0]
        if len(options) > 1:
            # Con varias estaciones posibles, preferir la de la zona actual.
            current = steps[-1][1] if steps else None
            station = next((o for o in options if o.get("zone") == current), options[0])
        if station.get("zone") is None:
            unzoned.append(ex["title"])
        steps.append((ex["title"], station.get("zone"), station["name"]))
    zones = [zone for _, zone, _ in steps if zone]
    changes = [(a, b) for a, b in zip(zones, zones[1:]) if a != b]
    return {
        "steps": steps, "missing": missing, "unzoned": unzoned, "zone_changes": len(changes),
        "far_changes": sum(1 for a, b in changes if frozenset((a, b)) not in near),
        "revisits": sorted({z for i, z in enumerate(zones) if z in zones[:i] and zones[i - 1] != z}),
    }


def check_lines(inventory, routines, preferences=None):
    lines = []
    for gym in validate(inventory)["gyms"]:
        lines.append(f"{gym.get('name') or gym['id']}: {len(gym.get('stations', []))} estaciones, "
                     f"{len(gym['zones'])} zonas.")
        pending = [s["name"] for s in gym.get("stations", []) if s.get("zone") is None]
        if pending:
            lines.append(f"  Sin zona: {len(pending)} estaciones.")
        for routine in routines:
            result = route(gym, routine, preferences)
            if result["unzoned"] or result["missing"]:
                lines.append(f"  {routine['title']}: recorrido sin calcular; faltan zona en {len(result['unzoned'])} "
                             f"y estación en {len(result['missing'])} ejercicios.")
                if result["missing"]:
                    lines.append(f"    Sin estación: {', '.join(result['missing'])}.")
                continue
            lines.append(f"  {routine['title']}: {result['zone_changes']} cambios de zona"
                         f" ({result['far_changes']} entre zonas no marcadas como cercanas).")
            if result["revisits"]:
                lines.append(f"    Vuelve a: {', '.join(result['revisits'])}.")
        placed = sum(1 for s in gym.get("stations", []) if s.get("position"))
        lines.append(f"  Ubicadas en el plano: {placed} de {len(gym.get('stations', []))}. "
                     "Distancias y orden propuesto: gym graph.")
    return lines


def settings(gym):
    result = dict(DEFAULT_SETTINGS)
    result.update(gym.get("settings") or {})
    return result


def distance(a, b, vertical_weight):
    """Línea recta en planta más el desnivel ponderado. Se usa cuando el gimnasio no tiene forma dibujada."""
    (ax, ay, az), (bx, by, bz) = a["position"], b["position"]
    return math.hypot(ax - bx, az - bz) + vertical_weight * abs(ay - by)


def metric(gym):
    """Distancia entre estaciones: caminando por la forma del gimnasio si existe, o en línea recta."""
    vertical = settings(gym)["vertical_weight"]
    if not gym.get("layout"):
        def straight(a, b):
            return distance(a, b, vertical)
        straight.inside = lambda station: True
        return straight
    walker = Walker(gym["layout"])
    cache = {}

    def walking(a, b):
        (ax, ay, az), (bx, by, bz) = a["position"], b["position"]
        key = (ax, az, bx, bz) if (ax, az) <= (bx, bz) else (bx, bz, ax, az)
        if key not in cache:
            cache[key] = walker.distance(key[:2], key[2:])
        return cache[key] + vertical * abs(ay - by)

    walking.inside = lambda station: walker.inside((station["position"][0], station["position"][2]))
    return walking


def proximity_graph(gym, measure=None):
    """Aristas entre estaciones a near_meters o menos (caminando si hay forma) y grupos conectados."""
    cfg = settings(gym)
    measure = measure or metric(gym)
    stations = gym.get("stations", [])
    outside = [s["id"] for s in stations if s.get("position") and not measure.inside(s)]
    placed = [s for s in stations if s.get("position") and s["id"] not in outside]
    edges = []
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            meters = measure(a, b)
            if meters <= cfg["near_meters"]:
                edges.append({"a": a["id"], "b": b["id"], "meters": round(meters, 2)})
    parent = {s["id"]: s["id"] for s in placed}

    def root(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for edge in edges:
        parent[root(edge["a"])] = root(edge["b"])
    groups = {}
    for station in placed:
        groups.setdefault(root(station["id"]), []).append(station["id"])
    return {
        "near_meters": cfg["near_meters"], "names": {s["id"]: s["name"] for s in stations},
        "placed": [s["id"] for s in placed], "unplaced": [s["id"] for s in stations if not s.get("position")],
        "outside": outside, "walking": bool(gym.get("layout")), "edges": edges,
        "section_names": {sec["id"]: sec["name"] for sec in (gym.get("layout") or {}).get("sections", [])},
        "sections": {st["id"]: section_of(gym.get("layout"), (st["position"][0], st["position"][2])) for st in placed},
        "clusters": list(groups.values()),
    }


def _units(routine, omitted):
    """Bloques que se mueven juntos: un ejercicio o una superserie consecutiva de Hevy."""
    units = []
    for ex in routine.get("exercises", []):
        if ex["exercise_template_id"] in omitted:
            continue
        superset = ex.get("superset_id")
        if superset is not None and units and units[-1]["superset_id"] == superset:
            units[-1]["exercises"].append(ex)
        else:
            units.append({"superset_id": superset, "exercises": [ex]})
    return units


def _combos(unit, placed_by_template, measure):
    """Estaciones posibles para el bloque. Dentro de una superserie se cuenta un solo recorrido."""
    options = []
    for ex in unit["exercises"]:
        found = placed_by_template.get(ex["exercise_template_id"])
        if not found:
            return None
        options.append(found[:MAX_STATION_OPTIONS])
    combos = []
    for chosen in itertools.product(*options):
        combos.append({
            "stations": chosen, "busy": max(s.get("busy") or 0 for s in chosen),
            "internal": sum(measure(a, b) for a, b in zip(chosen, chosen[1:])),
        })
    combos.sort(key=lambda c: c["internal"])
    return combos[:MAX_COMBOS]


def _step(cfg, previous, combo, unit_index, position):
    walk = combo["internal"]
    if previous is not None:
        walk += cfg["measure"](previous["stations"][-1], combo["stations"][0])
    score = walk + cfg["busy_weight_m"] * combo["busy"] * position + cfg["order_weight_m"] * abs(position - unit_index)
    return walk, score


def _evaluate(cfg, units, order):
    """Mejor elección de estaciones para un orden dado (programación dinámica por etapas)."""
    best, previous_unit = {None: (0.0, 0.0, [])}, None
    for position, u in enumerate(order):
        layer = {}
        for k, combo in enumerate(units[u]["combos"]):
            candidates = []
            for j, (score, walk, path) in best.items():
                prev = units[previous_unit]["combos"][j] if j is not None else None
                step_walk, step_score = _step(cfg, prev, combo, u, position)
                candidates.append((score + step_score, walk + step_walk, path + [k]))
            layer[k] = min(candidates, key=lambda c: c[0])
        best, previous_unit = layer, u
    score, walk, combos = min(best.values(), key=lambda c: c[0])
    return {"order": list(order), "combos": combos, "score": score, "walk": walk}


def _optimize(cfg, units):
    """Orden de menor costo entre todos los posibles (Held-Karp sobre bloques y estaciones)."""
    n = len(units)
    dp = [dict() for _ in range(1 << n)]
    for u in range(n):
        for k, combo in enumerate(units[u]["combos"]):
            walk, score = _step(cfg, None, combo, u, 0)
            dp[1 << u][(u, k)] = (score, walk, None)
    for mask in range(1, 1 << n):
        position = bin(mask).count("1")
        for (v, j), (score, walk, _) in dp[mask].items():
            previous = units[v]["combos"][j]
            for u in range(n):
                if mask >> u & 1:
                    continue
                following = dp[mask | 1 << u]
                for k, combo in enumerate(units[u]["combos"]):
                    step_walk, step_score = _step(cfg, previous, combo, u, position)
                    current = following.get((u, k))
                    if current is None or score + step_score < current[0] - 1e-9:
                        following[(u, k)] = (score + step_score, walk + step_walk, (mask, v, j))
    (u, k), (score, walk, link) = min(dp[(1 << n) - 1].items(), key=lambda item: item[1][0])
    order, combos = [u], [k]
    while link:
        mask, v, j = link
        order.append(v)
        combos.append(j)
        link = dp[mask][(v, j)][2]
    return {"order": order[::-1], "combos": combos[::-1], "score": score, "walk": walk}


def _describe(cfg, units, result):
    """Pasos del orden elegido. leg_m son los metros desde la estación anterior; suman walk_m."""
    steps, previous = [], None
    for block, (u, k) in enumerate(zip(result["order"], result["combos"])):
        combo = units[u]["combos"][k]
        for ex, station in zip(units[u]["exercises"], combo["stations"]):
            leg = cfg["measure"](previous, station) if previous else 0.0
            steps.append({"title": ex.get("title"), "exercise_template_id": ex["exercise_template_id"],
                          "station_id": station["id"], "station": station["name"], "busy": station.get("busy"),
                          "block": block, "leg_m": round(leg, 2)})
            previous = station
    return {"walk_m": round(result["walk"], 1), "score": round(result["score"], 1), "steps": steps,
            "moved": sum(1 for position, u in enumerate(result["order"]) if position != u)}


def plan(gym, routine, preferences=None, fixed=False, measure=None):
    """Metros del orden actual y, si no está fijado, un orden propuesto para revisar."""
    cfg = dict(settings(gym), measure=measure or metric(gym))
    placed = {}
    for station in gym.get("stations", []):
        if station.get("position") and cfg["measure"].inside(station):
            for template_id in station["exercise_template_ids"]:
                placed.setdefault(template_id, []).append(station)
    units = _units(routine, omitted_ids(preferences, routine["id"]))
    missing = []
    for unit in units:
        unit["combos"] = _combos(unit, placed, cfg["measure"])
        if unit["combos"] is None:
            missing.extend(ex.get("title") for ex in unit["exercises"] if ex["exercise_template_id"] not in placed)
    result = {"routine_id": routine["id"], "title": routine["title"], "fixed_order": fixed,
              "missing": missing, "current": None, "proposal": None, "note": None}
    if missing or not units:
        result["note"] = "Faltan estaciones ubicadas para calcular el recorrido." if missing else "Rutina sin ejercicios."
        return result
    current = _evaluate(cfg, units, range(len(units)))
    if math.isinf(current["score"]):
        result["note"] = "No hay camino caminando entre algunas estaciones: revisá paredes y puertas."
        return result
    result["current"] = _describe(cfg, units, current)
    if fixed:
        result["note"] = "Orden fijado por preferencias; no se propone otro."
        return result
    total = sum(len(u["combos"]) for u in units)
    if (1 << len(units)) * total * total > SEARCH_LIMIT:
        result["note"] = "Demasiados ejercicios o estaciones posibles para buscar el mejor orden completo."
        return result
    best = _optimize(cfg, units)
    if best["score"] < current["score"] - 0.01:
        result["proposal"] = _describe(cfg, units, best)
    else:
        result["note"] = "El orden actual ya es el de menor costo con estos criterios."
    return result


def analyze(inventory, routines, preferences=None):
    """Grafo y planes de todas las rutinas para cada gimnasio. D conserva el orden acordado."""
    fixed_title = normalize(ACTIVE_ROUTINES[1]) if (preferences or {}).get("D_exercise_order") else None
    gyms = []
    for gym in validate(inventory)["gyms"]:
        stations = gym.get("stations", [])
        measure = metric(gym)
        gyms.append({
            "id": gym["id"], "name": gym.get("name") or gym["id"], "settings": settings(gym),
            "graph": proximity_graph(gym, measure),
            "busy_unknown": [s["id"] for s in stations if s.get("busy") is None],
            "routines": [plan(gym, r, preferences, normalize(r["title"]) == fixed_title, measure) for r in routines],
        })
    return {"format": FORMAT, "gyms": gyms}


def _names(ids, names, limit=8):
    shown = [names[i] for i in ids[:limit]]
    return ", ".join(shown) + (f" y {len(ids) - limit} más" if len(ids) > limit else "")


def _meters(value):
    return f"{value:.1f}".replace(".", ",") + " m"


def graph_lines(analysis):
    lines = []
    for gym in analysis["gyms"]:
        graph, names = gym["graph"], gym["graph"]["names"]
        how = "caminando por la forma del gimnasio" if graph["walking"] else "en línea recta (sin forma dibujada)"
        lines.append(f"{gym['name']}: {len(graph['placed'])} de {len(names)} estaciones ubicadas; "
                     f"cercanas hasta {_meters(graph['near_meters'])} {how}.")
        if graph["outside"]:
            lines.append(f"  Fuera de la forma del gimnasio: {_names(graph['outside'], names)}.")
        if graph["unplaced"]:
            lines.append(f"  Sin ubicar: {_names(graph['unplaced'], names)}.")
        if gym["busy_unknown"]:
            lines.append(f"  Sin dato de ocupación: {len(gym['busy_unknown'])} estaciones (se tratan como libres).")
        for section_id, section_name in graph["section_names"].items():
            inside = [i for i, sec in graph["sections"].items() if sec == section_id]
            lines.append(f"  Sección {section_name}: {_names(inside, names) if inside else 'sin máquinas'}.")
        groups = [c for c in graph["clusters"] if len(c) > 1]
        alone = [c[0] for c in graph["clusters"] if len(c) == 1]
        for index, group in enumerate(groups, 1):
            lines.append(f"  Grupo cercano {index}: {_names(group, names)}.")
        if alone:
            lines.append(f"  Aisladas: {_names(alone, names)}.")
        for routine in gym["routines"]:
            current, proposal = routine["current"], routine["proposal"]
            if current is None:
                detail = f"Falta ubicar: {', '.join(routine['missing'])}." if routine["missing"] else routine["note"]
                lines.append(f"  {routine['title']}: recorrido sin calcular. {detail}")
                continue
            if proposal is None:
                lines.append(f"  {routine['title']}: {_meters(current['walk_m'])}. {routine['note']}")
                continue
            lines.append(f"  {routine['title']}: {_meters(current['walk_m'])}. Propuesta: {_meters(proposal['walk_m'])}, "
                         f"{proposal['moved']} bloque(s) cambian de lugar:")
            for number, step in enumerate(proposal["steps"], 1):
                busy = "" if step["busy"] is None else f" · {BUSY_LABELS[step['busy']]}"
                station = "" if step["station"] == step["title"] else f" — {step['station']}"
                lines.append(f"    {number}. {step['title']}{station}{busy}")
    if any(r["proposal"] for g in analysis["gyms"] for r in g["routines"]):
        lines.append("Las propuestas solo consideran recorrido, ocupación y cercanía al orden actual; no evalúan "
                     "prioridades de entrenamiento. Para aplicarlas: routine export → editar → routine apply.")
    return lines
