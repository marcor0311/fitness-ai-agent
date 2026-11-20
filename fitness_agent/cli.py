import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import sys
import tempfile
import webbrowser

from datetime import datetime, timedelta, timezone

from . import cloud, gym, gym_path, gym_space, routines, session_report
from .hevy import HevyClient, HevyError, NotFound, select_routines
from .review import build_snapshot, load_preferences, render_report, timestamp


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
    folder = ROOT / "data"
    # Validar preferencias antes de consultar Hevy: un archivo inválido no debe reemplazar la descarga.
    preferences = load_preferences(folder / "preferences.json")
    client = HevyClient(load_key())
    print("Consultando rutinas de Hevy…", flush=True)
    routines = select_routines(client.routines())
    print("Encontradas B, D y E. Consultando historial paginado…", flush=True)
    workouts = client.workouts()
    template_ids = {ex["exercise_template_id"] for r in routines for ex in r.get("exercises", [])}
    # Primero acotar el historial para no consultar catálogos de rutinas inactivas.
    snapshot = build_snapshot(routines, workouts, {}, weeks, preferences=preferences)
    for entry in snapshot["sessions"]:
        template_ids.update(ex["exercise_template_id"] for ex in entry["workout"].get("exercises", []))
    templates = {}
    for template_id in sorted(template_ids):
        templates[template_id] = client.exercise(template_id)
    snapshot["exercise_templates"] = templates
    # Generar todo antes de reemplazar la última descarga válida.
    report = render_report(snapshot)
    private_write(folder / "snapshot.json", json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    private_write(folder / "review.md", report)
    print(f"Descargadas {len(routines)} rutinas y {len(snapshot['sessions'])} sesiones en {weeks} semanas.")
    print(f"Datos: {folder / 'snapshot.json'}")
    print(f"Revisión: {folder / 'review.md'}")


def load_read_auth():
    value = os.environ.get("READ_API_AUTH", "").strip()
    if value:
        return value
    secrets = cloud.read_json(ROOT / "data" / "cloudflare-private.json", {})
    value = secrets.get("READ_API_AUTH") if isinstance(secrets, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise HevyError("Falta READ_API_AUTH en el entorno o en data/cloudflare-private.json.")
    return value.strip()


def pull():
    folder = ROOT / "data"
    client = cloud.CloudClient(load_read_auth(), os.environ.get("CLOUD_API_URL", cloud.DEFAULT_URL))
    print("Consultando entrenamientos recibidos por el webhook…", flush=True)
    result = cloud.pull(client, folder / "cloud-workouts.json", folder / "cloud-cursor.json", private_write)
    print(f"Nuevos: {result['added']}. Actualizados: {result['updated']}. Total local: {result['total']}.")
    print(f"Datos: {folder / 'cloud-workouts.json'}")


def routine_export(reference, out):
    client = HevyClient(load_key())
    routine = client.routine(routines.find_routine(client.routines(), reference)["id"])
    path = Path(out) if out else ROOT / "data" / "routines" / f"{routine['id']}.json"
    private_write(path, json.dumps(routines.export(routine), ensure_ascii=False, indent=2) + "\n")
    print(f"Exportada '{routine['title']}' (versión {routine.get('updated_at')}).")
    print(f"Editá {path} y revisá con: python3 -m fitness_agent routine apply {path}")


def routine_apply(file, confirm):
    try:
        proposal = json.loads(Path(file).read_text(encoding="utf-8"))
    except ValueError:
        raise HevyError(f"{file} no es JSON válido.") from None

    def backup(routine_id, now, content):
        path = ROOT / "data" / "changes" / f"{routine_id}-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        private_write(path, content)
        return path

    result = routines.apply(HevyClient(load_key()), proposal, backup, confirm)
    if result["status"] == "sin_cambios":
        print("La rutina en Hevy ya coincide con el archivo. No se escribió nada.")
        return
    print("Cambios:")
    for line in result["changes"]:
        print(f"  {line}")
    if result["status"] == "simulacion":
        print("Simulación: no se escribió nada. Para aplicar, repetí con --confirm.")
    else:
        print(f"Aplicado y verificado con una nueva lectura (versión {result['updated_at']}).")
        print(f"Respaldo del estado anterior: {result['backup']}")


def report(workout_id, force):
    folder = ROOT / "data"
    preferences = load_preferences(folder / "preferences.json")
    targets = []
    if workout_id:
        client = HevyClient(load_key())
        targets.append(client.workout(workout_id))
    else:
        result = cloud.pull(cloud.CloudClient(load_read_auth(), os.environ.get("CLOUD_API_URL", cloud.DEFAULT_URL)),
                            folder / "cloud-workouts.json", folder / "cloud-cursor.json", private_write)
        print(f"Webhook: {result['added']} nuevos, {result['total']} en total.")
        targets = list(cloud.read_json(folder / "cloud-workouts.json", {"workouts": {}})["workouts"].values())
        if not targets:
            print("No hay entrenamientos recibidos para reportar.")
            return
        client = HevyClient(load_key())
    print("Consultando historial de Hevy…", flush=True)
    history = client.workouts()
    dated = [timestamp(w["start_time"]) for w in targets if w.get("start_time")]
    earliest = (min(dated) if dated else datetime.now(timezone.utc)) - timedelta(days=28)
    relevant = targets + [w for w in history if w.get("start_time") and timestamp(w["start_time"]) >= earliest]
    templates = {}
    for template_id in sorted({e["exercise_template_id"] for w in relevant for e in w.get("exercises", [])}):
        try:
            templates[template_id] = client.exercise(template_id)
        except NotFound:
            continue
    cache = {}

    def load_routine(routine_id):
        if routine_id not in cache:
            try:
                cache[routine_id] = client.routine(routine_id)
            except NotFound:
                cache[routine_id] = None
        return cache[routine_id]

    result = session_report.generate(targets, history, load_routine, templates, preferences, folder / "reports",
                                     private_write, datetime.now(timezone.utc), force)
    print(f"Reportes generados: {len(result['generated'])}. Sin cambios: {len(result['unchanged'])}.")
    for generated in result["generated"]:
        print(f"  {folder / 'reports' / (generated.lower() + '.md')}")


def load_snapshot():
    snapshot = cloud.read_json(ROOT / "data" / "snapshot.json", None)
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("routines"), list):
        raise HevyError("Falta data/snapshot.json. Ejecutá primero: python3 -m fitness_agent sync")
    return snapshot


def snapshot_routines():
    return load_snapshot()["routines"]


def load_inventory(path):
    inventory = cloud.read_json(path, None)
    if inventory is None:
        raise HevyError("Falta data/gyms.json. Ejecutá: python3 -m fitness_agent gym init (o gym space)")
    return inventory


def download_catalog(folder):
    client = HevyClient(load_key())
    print("Descargando el catálogo de ejercicios de Hevy…", flush=True)
    templates = client.exercise_templates()
    keep = ("id", "title", "type", "primary_muscle_group", "secondary_muscle_groups", "equipment", "is_custom",
            "thumbnail_url")
    catalog = {"downloaded_at": datetime.now(timezone.utc).isoformat(),
               "templates": [{k: t.get(k) for k in keep} for t in templates]}
    private_write(folder / "exercise-catalog.json", json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(templates)} ejercicios en {folder / 'exercise-catalog.json'}.")
    return catalog


def gym_space_command(folder, path, port, open_browser):
    snapshot = load_snapshot()
    catalog = cloud.read_json(folder / "exercise-catalog.json", None) or download_catalog(folder)
    entries = gym_space.catalog_entries(snapshot.get("exercise_templates"), catalog)

    def backup(content, now):
        private_write(folder / "changes" / f"gyms-{now.strftime('%Y%m%dT%H%M%SZ')}.json", content)

    editor = gym_space.Editor(path, snapshot["routines"], entries, private_write, backup)
    try:
        server, url = gym_space.serve(editor, port)
    except OSError:
        raise HevyError(f"El puerto {port} está en uso. Probá con: gym space --port 0") from None
    print(f"Espacio del gimnasio: {len(entries)} ejercicios de Hevy con máquina, barra o mancuernas.")
    print(f"Abrí {url}", flush=True)
    print("Solo accesible desde este equipo. Guardá desde la página; Ctrl+C cierra el servidor.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEspacio cerrado.")
    finally:
        server.server_close()


def gym_path_command(folder, path, port, open_browser):
    snapshot = load_snapshot()
    load_preferences(folder / "preferences.json")  # Validar antes de abrir; la página vuelve a leerlo al recargar.
    viewer = gym_path.Viewer(path, snapshot["routines"], snapshot.get("exercise_templates"),
                             lambda: load_preferences(folder / "preferences.json"))
    try:
        server, url = gym_path.serve(viewer, port)
    except OSError:
        raise HevyError(f"El puerto {port} está en uso. Probá con: gym path --port 0") from None
    print("Recorrido 3D de las rutinas sobre las máquinas ubicadas en gym space (solo lectura).")
    print(f"Abrí {url}", flush=True)
    print("Solo accesible desde este equipo. Tras guardar en gym space, tocá Recargar; Ctrl+C cierra el servidor.",
          flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRecorrido cerrado.")
    finally:
        server.server_close()


DEFAULT_PORTS = {"space": 8765, "path": 8766}


def gym_command(action, port=None, open_browser=True):
    folder = ROOT / "data"
    path = folder / "gyms.json"
    if action == "init":
        if path.exists():
            raise HevyError(f"Ya existe {path}; editalo en lugar de reemplazarlo.")
        snapshot = load_snapshot()
        inventory = gym.template(snapshot["routines"], snapshot.get("exercise_templates"))
        private_write(path, json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
        print(f"Inventario inicial en {path}. Ubicá las máquinas con: python3 -m fitness_agent gym space")
        return
    if action == "catalog":
        download_catalog(folder)
        return
    if port is None:
        port = DEFAULT_PORTS.get(action, 8765)
    if action == "space":
        gym_space_command(folder, path, port, open_browser)
        return
    if action == "path":
        gym_path_command(folder, path, port, open_browser)
        return
    preferences = load_preferences(folder / "preferences.json")
    inventory = load_inventory(path)
    if action == "graph":
        analysis = gym.analyze(inventory, snapshot_routines(), preferences)
        private_write(folder / "gym-graph.json", json.dumps(analysis, ensure_ascii=False, indent=2) + "\n")
        for line in gym.graph_lines(analysis):
            print(line)
        print(f"Detalle: {folder / 'gym-graph.json'}")
        return
    for line in gym.check_lines(inventory, snapshot_routines(), preferences):
        print(line)


def positive_weeks(value):
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Las semanas deben ser un entero positivo.") from None
    if not 1 <= result <= 520:
        raise argparse.ArgumentTypeError("Las semanas deben estar entre 1 y 520.")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hevy: rutinas, historial y reportes para hipertrofia.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="Ingresar y validar la API key localmente.")
    sync_parser = sub.add_parser("sync", help="Descargar las tres rutinas y preparar su revisión.")
    sync_parser.add_argument("--weeks", type=positive_weeks, default=12, help="Ventana del historial (12 por defecto).")
    sub.add_parser("pull", help="Descargar los entrenamientos que el webhook guardó en Cloudflare.")
    report_parser = sub.add_parser("report", help="Generar el reporte de cada entrenamiento recibido.")
    report_parser.add_argument("--workout", help="Reportar un entrenamiento concreto de Hevy por ID.")
    report_parser.add_argument("--force", action="store_true", help="Regenerar aunque no haya cambios.")
    routine_parser = sub.add_parser("routine", help="Exportar o aplicar cambios de una rutina.")
    routine_sub = routine_parser.add_subparsers(dest="action", required=True)
    export_parser = routine_sub.add_parser("export", help="Guardar la rutina actual como archivo editable.")
    export_parser.add_argument("reference", help="ID o título completo de la rutina.")
    export_parser.add_argument("--out", help="Ruta del archivo (por defecto data/routines/<id>.json).")
    apply_parser = routine_sub.add_parser("apply", help="Mostrar diferencias; con --confirm, aplicarlas en Hevy.")
    apply_parser.add_argument("file")
    apply_parser.add_argument("--confirm", action="store_true", help="Escribir en Hevy tras respaldar.")
    gym_parser = sub.add_parser("gym", help="Espacio 3D de máquinas, recorrido 3D, inventario y grafo de cercanía.")
    gym_parser.add_argument("action", choices=("space", "path", "graph", "check", "init", "catalog"), help=(
        "space: abrir el espacio 3D para ubicar máquinas; path: ver en 3D el recorrido de cada rutina; graph: "
        "distancias y orden propuesto en texto; check: validar y "
        "contar zonas; init: crear data/gyms.json; catalog: volver a descargar el catálogo de Hevy."))
    gym_parser.add_argument("--port", type=int, help="Puerto local de gym space (8765) o gym path (8766); 0 elige uno libre.")
    gym_parser.add_argument("--no-browser", action="store_true", help="No abrir el navegador con gym space o gym path.")
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            setup()
        elif args.command == "pull":
            pull()
        elif args.command == "report":
            report(args.workout, args.force)
        elif args.command == "gym":
            gym_command(args.action, args.port, not args.no_browser)
        elif args.command == "routine" and args.action == "export":
            routine_export(args.reference, args.out)
        elif args.command == "routine":
            routine_apply(args.file, args.confirm)
        else:
            sync(args.weeks)
        return 0
    except (HevyError, OSError, EOFError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperación cancelada.", file=sys.stderr)
        return 130
