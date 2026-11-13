import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import sys
import tempfile

from .hevy import HevyClient, HevyError, select_routines
from .review import build_snapshot, render_report


ROOT = Path(__file__).resolve().parent.parent


def private_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".hevy-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_key():
    value = os.environ.get("HEVY_API_KEY", "").strip()
    if value:
        return value
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip().startswith("HEVY_API_KEY="):
                return line.strip().split("=", 1)[1].strip().strip("\"'")
    raise HevyError("Falta la credencial. Ejecutá: python3 -m fitness_agent setup")


def setup():
    path = ROOT / ".env"
    if path.exists():
        raise HevyError("Ya existe .env. Editalo localmente si necesitás reemplazar la clave.")
    if not sys.stdin.isatty():
        raise HevyError("Ejecutá setup en una terminal interactiva para ocultar la clave.")
    print("Generá tu API key en https://hevy.com/settings?developer")
    print("La clave se guardará solo en .env, excluido de Git.")
    key = getpass("API key de Hevy (entrada oculta): ").strip()
    if not key or any(c.isspace() for c in key):
        raise HevyError("La clave está vacía o contiene espacios.")
    # Validar la credencial antes de guardarla, sin imprimir datos de la cuenta.
    HevyClient(key).routines()
    private_write(path, f"HEVY_API_KEY={key}\n")
    print("Credencial validada y guardada. Ejecutá: python3 -m fitness_agent sync")


def sync(weeks):
    client = HevyClient(load_key())
    print("Consultando rutinas de Hevy…", flush=True)
    routines = select_routines(client.routines())
    print("Encontradas B, D y E. Consultando historial paginado…", flush=True)
    workouts = client.workouts()
    template_ids = {ex["exercise_template_id"] for r in routines for ex in r.get("exercises", [])}
    # Primero acotar el historial para no consultar catálogos de rutinas inactivas.
    snapshot = build_snapshot(routines, workouts, {}, weeks)
    for entry in snapshot["sessions"]:
        template_ids.update(ex["exercise_template_id"] for ex in entry["workout"].get("exercises", []))
    templates = {}
    for template_id in sorted(template_ids):
        templates[template_id] = client.exercise(template_id)
    snapshot["exercise_templates"] = templates
    # Generar todo antes de reemplazar la última descarga válida.
    report = render_report(snapshot)
    folder = ROOT / "data"
    private_write(folder / "snapshot.json", json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    private_write(folder / "review.md", report)
    print(f"Descargadas {len(routines)} rutinas y {len(snapshot['sessions'])} sesiones en {weeks} semanas.")
    print(f"Datos: {folder / 'snapshot.json'}")
    print(f"Revisión: {folder / 'review.md'}")


def positive_weeks(value):
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Las semanas deben ser un entero positivo.") from None
    if not 1 <= result <= 520:
        raise argparse.ArgumentTypeError("Las semanas deben estar entre 1 y 520.")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hevy: B, D y E para hipertrofia; prioridad D.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="Ingresar y validar la API key localmente.")
    sync_parser = sub.add_parser("sync", help="Descargar las tres rutinas y preparar su revisión.")
    sync_parser.add_argument("--weeks", type=positive_weeks, default=12, help="Ventana del historial (12 por defecto).")
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            setup()
        else:
            sync(args.weeks)
        return 0
    except (HevyError, OSError, EOFError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperación cancelada.", file=sys.stderr)
        return 130
