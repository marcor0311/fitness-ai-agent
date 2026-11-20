"""Recorrido 3D de cada rutina: sirve gym_path.html con el grafo de cercanía y el orden actual y propuesto.

Es otra interfaz, separada de gym space: solo lee data/gyms.json y no guarda nada. Cada consulta vuelve a leer el
inventario, así que al guardar cambios en gym space basta con recargar esta página. Mismas reglas de acceso que
gym space: solo 127.0.0.1, Host local y un token por arranque.
"""

import json
import math
from http.server import ThreadingHTTPServer
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from . import gym, layout, machines
from .gym_space import local_handler
from .hevy import HevyError


PAGE = Path(__file__).with_name("gym_path.html")


def _floor_point(station):
    return station["position"][0], station["position"][2]


def _walking_path(walker, a, b):
    """Polilínea [[x, z], ...] cuando el camino rodea algo; None si es recto (la página dibuja la línea directa)."""
    found = walker.path(a, b) if a != b else None
    return [[round(x, 3), round(z, 3)] for x, z in found] if found and len(found) > 2 else None


def add_walking_paths(result, source, walker):
    """Agrega "path" a cada paso (desde la estación anterior) y a cada unión del grafo que rodea paredes.

    Solo con forma del gimnasio; sin ella la página dibuja líneas directas. Un Walker por gimnasio reutiliza su caché.
    """
    where = {s["id"]: _floor_point(s) for s in source.get("stations", []) if s.get("position")}
    for routine in result["routines"]:
        for order in (routine["current"], routine["proposal"]):
            previous = None
            for step in (order or {}).get("steps", []):
                point = where.get(step["station_id"])
                if previous and point:
                    path = _walking_path(walker, previous, point)
                    if path:
                        step["path"] = path
                previous = point
    for edge in result["graph"]["edges"]:
        path = _walking_path(walker, where[edge["a"]], where[edge["b"]])
        if path:
            edge["path"] = path


def separated_pairs(source, outside):
    """Estaciones cercanas en línea recta pero no caminando: una pared las separa y la puerta queda lejos.

    El grafo ya las excluye; la página las marca para que estar al lado no se confunda con estar cerca.
    """
    cfg = gym.settings(source)
    measure = gym.metric(source)
    placed = [s for s in source.get("stations", []) if s.get("position") and s["id"] not in outside]
    pairs = []
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            straight = gym.distance(a, b, cfg["vertical_weight"])
            if straight > cfg["near_meters"]:
                continue
            walking = measure(a, b)
            if walking > cfg["near_meters"]:
                pairs.append({"a": a["id"], "b": b["id"], "straight_m": round(straight, 2),
                              "walking_m": round(walking, 2) if math.isfinite(walking) else None})
    return sorted(pairs, key=lambda pair: pair["straight_m"])


class Viewer:
    """Estado de solo lectura. load_preferences llega desde el CLI para validar el archivo en cada consulta."""

    def __init__(self, path, routines, templates, load_preferences):
        self.path, self.routines, self.load_preferences = path, routines, load_preferences
        self.model_by_template = {i: machines.classify(t) for i, t in (templates or {}).items() if isinstance(t, dict)}
        self.token = secrets.token_urlsafe(24)

    def state(self):
        try:
            inventory = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise HevyError("Falta data/gyms.json. Ubicá las máquinas con: python3 -m fitness_agent gym space") from None
        except ValueError:
            raise HevyError(f"{self.path.name} no es JSON válido; corregilo en gym space o a mano.") from None
        analysis = gym.analyze(inventory, self.routines, self.load_preferences())
        sizes = {m["id"]: m["size"] for m in machines.describe()}
        gyms = []
        for source, result in zip(inventory["gyms"], analysis["gyms"]):
            stations = []
            for station in source.get("stations", []):
                model = station.get("model") or machines.infer(station, self.model_by_template) or "generic"
                stations.append({
                    "id": station["id"], "name": station["name"], "model": model, "position": station.get("position"),
                    "rotation_deg": station.get("rotation_deg") or 0, "busy": station.get("busy"),
                    "size": station.get("size") or sizes[model],
                })
            shape = source.get("layout")
            separated = []
            if shape:
                add_walking_paths(result, source, layout.Walker(shape))
                separated = separated_pairs(source, set(result["graph"].get("outside") or []))
            walls = [{"id": w.get("id"), "pieces": layout.wall_pieces(w), "doors": w.get("doors", [])}
                     for w in (shape or {}).get("walls", [])]
            gyms.append(dict(result, floor=result["settings"]["floor"], stations=stations,
                             outline=(shape or {}).get("outline"), walls=walls, separated=separated))
        return {"format": analysis["format"], "gyms": gyms, "busy_labels": gym.BUSY_LABELS}


def handler_for(viewer, port):
    class Handler(local_handler(viewer.token, port, PAGE)):
        def do_GET(self):
            route = urlsplit(self.path).path
            if self._static(route):
                return
            if route == "/api/path":
                if self._allowed(needs_token=True):
                    self._run(viewer.state)
            else:
                self._send(404, {"error": "No existe."})

        def do_POST(self):
            self._send(405, {"error": "Esta página es de solo lectura."})

    return Handler


def serve(viewer, port=8766):
    """Crea el servidor; el llamador ejecuta serve_forever y lo cierra."""
    server = ThreadingHTTPServer(("127.0.0.1", port), None)
    server.RequestHandlerClass = handler_for(viewer, server.server_address[1])
    return server, f"http://127.0.0.1:{server.server_address[1]}/#token={viewer.token}"
