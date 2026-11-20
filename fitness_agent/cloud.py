"""Lectura privada de los entrenamientos que el Worker guardó en D1. Sin dependencias externas."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .hevy import HevyError


DEFAULT_URL = "https://fitness-hevy-webhook.fitness-hevy-webhook.workers.dev"


class NoCloudRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # No reenviar el encabezado de lectura a otro destino.
        raise HevyError("Cloudflare devolvió una redirección inesperada; se canceló la consulta.")


class CloudClient:
    def __init__(self, auth, base_url=DEFAULT_URL, opener=None):
        self.auth = (auth or "").strip()
        if not self.auth.startswith("Bearer ") or len(self.auth) < 32:
            raise HevyError("Falta READ_API_AUTH completo (incluido 'Bearer ').")
        if not base_url.startswith("https://"):
            raise HevyError("La URL del Worker debe usar HTTPS.")
        self.base_url = base_url.rstrip("/")
        self.opener = opener or build_opener(NoCloudRedirects())

    def page(self, cursor):
        url = f"{self.base_url}/api/workouts?" + urlencode({"cursor": cursor})
        req = Request(url, headers={
            # Cloudflare rechaza con 403 el User-Agent predeterminado de urllib.
            "Authorization": self.auth, "Accept": "application/json", "User-Agent": "fitness-agent-cli/1",
        }, method="GET")
        try:
            with self.opener.open(req, timeout=30) as response:
                payload = json.load(response)
        except HTTPError as exc:
            status = exc.code
            exc.close()
            if status == 401:
                raise HevyError("Cloudflare rechazó la lectura. Revisá READ_API_AUTH.") from None
            raise HevyError(f"Error HTTP {status} al consultar Cloudflare.") from None
        except (URLError, TimeoutError, OSError):
            raise HevyError("No se pudo conectar con Cloudflare. Revisá tu conexión y volvé a intentar.") from None
        except (ValueError, UnicodeError):
            raise HevyError("Cloudflare devolvió una respuesta JSON inválida.") from None
        workouts = payload.get("workouts") if isinstance(payload, dict) else None
        following = payload.get("cursor") if isinstance(payload, dict) else None
        if (not isinstance(workouts, list) or not isinstance(following, str) or not following.isdigit()
                or type(payload.get("has_more")) is not bool or int(following) < int(cursor)):
            raise HevyError("Cloudflare devolvió una página con formato inesperado.")
        if any(not isinstance(w, dict) or not isinstance(w.get("id"), str) or not w["id"] for w in workouts):
            raise HevyError("Cloudflare devolvió un entrenamiento sin ID.")
        if payload["has_more"] and following == cursor:
            raise HevyError("La paginación de Cloudflare no avanzó; se detuvo para no repetir páginas.")
        return payload


def read_json(path, default):
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        raise HevyError(f"{path.name} está dañado; no se modificó. Revisalo antes de volver a descargar.") from None


def pull(client, store_path, cursor_path, write, max_pages=1000):
    """Agrega los entrenamientos nuevos al archivo local y guarda el cursor solo después de persistirlos."""
    state = read_json(cursor_path, {"cursor": "0"})
    store = read_json(store_path, {"workouts": {}})
    cursor = state.get("cursor") if isinstance(state, dict) else None
    if not isinstance(cursor, str) or not cursor.isdigit():
        raise HevyError(f"{cursor_path.name} no contiene un cursor válido.")
    if not isinstance(store, dict) or not isinstance(store.get("workouts"), dict):
        raise HevyError(f"{store_path.name} no tiene el formato esperado.")
    added = updated = 0
    for _ in range(max_pages):
        page = client.page(cursor)
        for workout in page["workouts"]:
            key = workout["id"].lower()
            if key in store["workouts"]:
                updated += store["workouts"][key] != workout
            else:
                added += 1
            store["workouts"][key] = workout
        # Orden obligatorio: si falla la escritura del cursor, la próxima descarga repite la página sin perder datos.
        write(store_path, json.dumps(store, ensure_ascii=False, indent=2) + "\n")
        cursor = page["cursor"]
        write(cursor_path, json.dumps({"cursor": cursor}) + "\n")
        if not page["has_more"]:
            return {"added": added, "updated": updated, "total": len(store["workouts"]), "cursor": cursor}
    raise HevyError("Se alcanzó el límite de páginas; volvé a ejecutar para continuar desde el cursor guardado.")
