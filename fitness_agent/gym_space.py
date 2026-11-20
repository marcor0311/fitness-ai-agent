"""Espacio 3D del gimnasio: sirve gym_space.html para ubicar máquinas y guarda data/gyms.json validado.

El grafo de cercanía es otra función (gym graph) y su recorrido 3D otra página (gym path, en gym_path.py); este
servidor solo carga, valida y guarda el plano. Ambas páginas comparten local_handler y machine_models.js.

Solo escucha en 127.0.0.1. Cada arranque genera un token que la página envía en cada consulta; sin él, o con
otro Host, se rechaza la solicitud. Así otra página abierta en el navegador no puede leer ni escribir el inventario.
"""

from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit

from . import gym, machines
from .hevy import HevyError


PAGE = Path(__file__).with_name("gym_space.html")
MAX_BODY = 4 * 1024 * 1024


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest() if text is not None else None


def catalog_entries(snapshot_templates, catalog):
    """Ejercicios de Hevy que usan una máquina, barra o mancuernas, con el modelo de máquina de cada uno.

    Une el catálogo completo descargado con el snapshot, que incluye los ejercicios personalizados usados.
    """
    entries = {}
    for template in list((catalog or {}).get("templates", [])) + list((snapshot_templates or {}).values()):
        if not isinstance(template, dict) or not isinstance(template.get("id"), str):
            continue
        model = machines.classify(template)
        if model:
            entries[template["id"]] = dict({k: template.get(k) for k in
                                            ("id", "title", "equipment", "primary_muscle_group", "thumbnail_url",
                                             "is_custom")}, model=model)
    return sorted(entries.values(), key=lambda t: (t["title"] or "").casefold())


class Editor:
    """Estado de una sesión del editor. Las funciones de E/S llegan desde el CLI para poder probarlas."""

    def __init__(self, path, routines, catalog, write, backup, now=lambda: datetime.now(timezone.utc)):
        self.path, self.routines, self.catalog = path, routines, catalog
        self.write, self.backup, self.now = write, backup, now
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.Lock()
        self.backed_up = False
        self.loaded = self._read()

    def _read(self):
        try:
            return self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    def state(self):
        with self.lock:
            raw = self.loaded = self._read()
        if raw is None:
            inventory, source = gym.template(self.routines), "nuevo"
        else:
            try:
                inventory, source = json.loads(raw), "archivo"
            except ValueError:
                raise HevyError(f"{self.path.name} no es JSON válido; corregilo antes de abrir el editor.") from None
        # Las estaciones creadas antes del espacio 3D no tienen modelo: se propone el de su primer ejercicio.
        by_template = {t["id"]: t["model"] for t in self.catalog}
        for g in inventory.get("gyms", []) if isinstance(inventory, dict) else []:
            for station in g.get("stations", []) if isinstance(g, dict) else []:
                if isinstance(station, dict) and not station.get("model"):
                    station["model"] = machines.infer(station, by_template)
        return {
            "inventory": inventory, "source": source, "catalog": self.catalog, "models": machines.describe(),
            "categories": machines.CATEGORIES,
            "routines": [{"id": r["id"], "title": r["title"],
                          "exercise_template_ids": [ex["exercise_template_id"] for ex in r.get("exercises", [])]}
                         for r in self.routines],
        }

    def save(self, inventory):
        gym.validate(inventory)  # Antes de tocar el archivo.
        content = json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"
        with self.lock:
            current = self._read()
            if digest(current) != digest(self.loaded):
                raise Conflict("data/gyms.json cambió fuera del editor. Recargá la página para no pisar esos cambios.")
            if current is not None and not self.backed_up:
                self.backup(current, self.now())
                self.backed_up = True
            self.write(self.path, content)
            self.loaded = content
        return {"saved_at": self.now().isoformat()}


class Conflict(HevyError):
    pass


MODELS_JS = Path(__file__).with_name("machine_models.js")


def local_handler(token, port, page):
    """Base para las páginas locales: solo Host local, token en cada consulta de datos y archivos estáticos.

    La usan gym space y gym path; cada una agrega sus rutas de datos en do_GET/do_POST.
    """
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    static = {"/": (page, "text/html; charset=utf-8"),
              "/machine_models.js": (MODELS_JS, "text/javascript; charset=utf-8")}

    class LocalHandler(BaseHTTPRequestHandler):
        server_version = "fitness-gym"

        def log_message(self, *args):
            pass

        def _send(self, status, body, content_type="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def _allowed(self, needs_token):
            if self.headers.get("Host") not in allowed_hosts:
                self._send(403, {"error": "Host no permitido."})
                return False
            if needs_token and not secrets.compare_digest(self.headers.get("X-Editor-Token", ""), token):
                self._send(403, {"error": "Token inválido. Abrí la URL que mostró el CLI."})
                return False
            return True

        def _static(self, route):
            """Sirve la página o el módulo de modelos; devuelve False si la ruta no es estática."""
            if route not in static:
                return False
            if self._allowed(needs_token=False):
                path, content_type = static[route]
                self._send(200, path.read_bytes(), content_type)
            return True

        def _run(self, action):
            try:
                self._send(200, action())
            except Conflict as exc:
                self._send(409, {"error": str(exc)})
            except HevyError as exc:
                self._send(400, {"error": str(exc)})
            except OSError:
                self._send(500, {"error": "No se pudo leer o escribir data/gyms.json."})

    return LocalHandler


def handler_for(editor, port):
    class Handler(local_handler(editor.token, port, PAGE)):
        def do_GET(self):
            route = urlsplit(self.path).path
            if self._static(route):
                return
            if route == "/api/state":
                if self._allowed(needs_token=True):
                    self._run(editor.state)
            else:
                self._send(404, {"error": "No existe."})

        def do_POST(self):
            route = urlsplit(self.path).path
            if route != "/api/save":
                self._send(404, {"error": "No existe."})
                return
            if not self._allowed(needs_token=True):
                return
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                self._send(415, {"error": "Se espera JSON."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if not 0 < length <= MAX_BODY:
                self._send(413, {"error": "Cuerpo vacío o demasiado grande."})
                return
            try:
                body = json.loads(self.rfile.read(length))
            except ValueError:
                self._send(400, {"error": "JSON inválido."})
                return
            inventory = body.get("inventory") if isinstance(body, dict) else None
            self._run(lambda: editor.save(inventory))

    return Handler


def serve(editor, port=8765):
    """Crea el servidor; el llamador ejecuta serve_forever y lo cierra."""
    server = ThreadingHTTPServer(("127.0.0.1", port), None)
    server.RequestHandlerClass = handler_for(editor, server.server_address[1])
    return server, f"http://127.0.0.1:{server.server_address[1]}/#token={editor.token}"
