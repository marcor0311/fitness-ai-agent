"""Cliente de lectura de la API oficial. Sin dependencias externas."""

import json
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


ACTIVE_ROUTINES = (
    "B - Lower",
    "D - I Am The Shadows",
    "E - Redemption (Now or Never)",
)


class HevyError(Exception):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HevyError("Hevy devolvió una redirección inesperada; se canceló la consulta.")


def normalize(title):
    # Ignora adornos emoji, conservando la comparación del título completo.
    title = unicodedata.normalize("NFKC", title)
    title = "".join(
        c for c in title
        if unicodedata.category(c) not in ("So", "Sk")
        and c not in ("\u200d", "\ufe0e", "\ufe0f")
    )
    for dash in ("–", "—", "−", "‑"):
        title = title.replace(dash, "-")
    return " ".join(title.casefold().split())


def select_routines(routines):
    selected = []
    for title in ACTIVE_ROUTINES:
        matches = [r for r in routines if normalize(r["title"]) == normalize(title)]
        if not matches:
            available = ", ".join(r["title"] for r in routines) or "ninguna"
            raise HevyError(f"No se encontró '{title}'. Rutinas disponibles: {available}")
        if len(matches) > 1:
            raise HevyError(f"Hay varias rutinas llamadas '{title}'. Asignales nombres únicos en Hevy.")
        selected.append(matches[0])
    return selected


class HevyClient:
    BASE_URL = "https://api.hevyapp.com/v1"

    def __init__(self, api_key, opener=None, sleep=time.sleep):
        self.api_key = api_key.strip()
        if not self.api_key:
            raise HevyError("Falta HEVY_API_KEY. Ejecutá: python3 -m fitness_agent setup")
        self.opener = opener or build_opener(NoRedirects())
        self.sleep = sleep

    def _get(self, path, **params):
        url = f"{self.BASE_URL}/{path}"
        if params:
            url += "?" + urlencode(params)
        req = Request(url, headers={"api-key": self.api_key, "Accept": "application/json"}, method="GET")
        for attempt in range(3):
            try:
                with self.opener.open(req, timeout=30) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict):
                    raise HevyError("Hevy devolvió un formato inesperado.")
                return payload
            except HTTPError as exc:
                status = exc.code
                retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
                exc.close()
                if status in (429, 500, 502, 503, 504) and attempt < 2:
                    delay = min(int(retry_after), 30) if retry_after.isdigit() else 2 ** attempt
                    self.sleep(delay)
                    continue
                if status in (401, 403):
                    raise HevyError("Hevy rechazó el acceso. Revisá la API key y tu suscripción Pro.") from None
                raise HevyError(f"Error HTTP {status} al consultar Hevy.") from None
            except (URLError, TimeoutError, OSError):
                if attempt < 2:
                    self.sleep(2 ** attempt)
                    continue
                raise HevyError("No se pudo conectar con Hevy. Revisá tu conexión y volvé a intentar.") from None
            except (ValueError, UnicodeError):
                raise HevyError("Hevy devolvió una respuesta JSON inválida.") from None

    def _pages(self, resource):
        result = []
        seen = set()
        page = 1
        while True:
            payload = self._get(resource, page=page, pageSize=10)
            rows, count = payload.get(resource), payload.get("page_count")
            if (not isinstance(rows, list) or type(count) is not int
                    or count < 0 or count > 10000 or payload.get("page") != page):
                raise HevyError(f"Paginación inesperada en {resource}.")
            if (not rows and page < count) or (rows and count == 0):
                raise HevyError(f"Página incompleta en {resource}; volvé a sincronizar.")
            for row in rows:
                if not isinstance(row, dict) or not row.get("id") or not isinstance(row.get("title"), str):
                    raise HevyError(f"Registro inválido en {resource}.")
                if row["id"] in seen:
                    raise HevyError(f"El historial cambió durante la consulta de {resource}; volvé a sincronizar.")
                seen.add(row["id"])
                result.append(row)
            if page >= count:
                return result
            page += 1

    def routines(self):
        return self._pages("routines")

    def workouts(self):
        return self._pages("workouts")

    def exercise(self, template_id):
        return self._get("exercise_templates/" + quote(template_id, safe=""))
