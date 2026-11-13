"""Contexto verificable para revisar las rutinas; no inventa progreso ni prescribe cargas."""

from collections import Counter
from datetime import datetime, timedelta, timezone

from .hevy import HevyError, normalize


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed
    except (AttributeError, TypeError, ValueError):
        raise HevyError("Hay un entrenamiento con fecha inválida; no se generó un análisis parcial.") from None


def working_sets(exercise):
    return [s for s in exercise.get("sets", []) if s.get("type") != "warmup"]


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def target(s):
    rep_range = s.get("rep_range") or {}
    if rep_range.get("start") is not None and rep_range.get("end") is not None:
        return f"{rep_range['start']}–{rep_range['end']} reps"
    if s.get("reps") is not None:
        return f"{s['reps']} reps"
    if s.get("duration_seconds") is not None:
        return f"{s['duration_seconds']} s"
    if s.get("distance_meters") is not None:
        return f"{s['distance_meters']} m"
    return "sin objetivo registrado"


def build_snapshot(routines, workouts, templates, weeks, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(weeks=weeks)
    ids = {r["id"] for r in routines}
    by_title = {normalize(r["title"]): r["id"] for r in routines}
    selected = []
    unmatched = 0
    for workout in workouts:
        start = timestamp(workout.get("start_time"))
        if not cutoff <= start <= now:
            continue
        linked = workout.get("routine_id")
        # Si existe otro ID, un nombre parecido no permite atribuir la sesión.
        if linked in ids:
            matched_id, match = linked, "routine_id"
        elif linked is None and normalize(workout["title"]) in by_title:
            matched_id, match = by_title[normalize(workout["title"])], "title_fallback"
        else:
            unmatched += 1
            continue
        if not workout.get("end_time"):
            continue
        if timestamp(workout["end_time"]) < start:
            raise HevyError("Hay un entrenamiento con duración negativa.")
        selected.append({"routine_id": matched_id, "match": match, "workout": workout})
    selected.sort(key=lambda item: timestamp(item["workout"]["start_time"]))
    return {
        "fetched_at": now.isoformat(), "since": cutoff.isoformat(), "weeks": weeks,
        "goal": "hipertrofia", "priority": "D - I Am The Shadows",
        "routines": routines, "exercise_templates": templates, "sessions": selected,
        "unmatched_workouts_in_window": unmatched,
    }


def render_report(snapshot):
    weeks = snapshot["weeks"]
    sessions = snapshot["sessions"]
    templates = snapshot["exercise_templates"]
    lines = [
        "# Rutinas actuales · hipertrofia",
        "", f"Datos consultados: {snapshot['fetched_at']}.",
        f"Ventana: {snapshot['since']} hasta la consulta ({weeks} semanas).",
        "Pesos en kg y distancias en metros, como los entrega Hevy.",
        "Las series de calentamiento se excluyen de los conteos de trabajo.",
        "", "Objetivo: revisar primero D considerando también B y E.",
        "",
    ]
    muscle_totals = Counter()
    for routine in snapshot["routines"]:
        own = [s for s in sessions if s["routine_id"] == routine["id"]]
        fallback = sum(s["match"] == "title_fallback" for s in own)
        lines.extend([
            f"## {cell(routine['title'])}", "", f"ID: `{routine['id']}`.",
            f"Sesiones en la ventana: {len(own)} ({len(own) / weeks:.2f}/semana).",
            f"Asociaciones por título sin routine_id: {fallback}; verificar si corresponden.", "",
            "| Ejercicio | Series de trabajo | Objetivos por serie | Descanso | Superserie |",
            "| --- | ---: | --- | --- | --- |",
        ])
        notes = []
        for ex in routine.get("exercises", []):
            sets = working_sets(ex)
            rest = ex.get("rest_seconds")
            lines.append("| " + " | ".join(map(cell, [
                ex["title"], len(sets), "; ".join(target(s) for s in sets) or "—",
                f"{rest} s" if rest is not None else "sin registrar",
                ex.get("superset_id") if ex.get("superset_id") is not None else "—",
            ])) + " |")
            if ex.get("notes"):
                notes.append(f"- Nota de {cell(ex['title'])}: {cell(ex['notes'])}")
        if notes:
            lines.extend(["", *notes])
        if own:
            lines.extend(["", "Últimas sesiones:", ""])
            for entry in own[-3:]:
                w = entry["workout"]
                lines.append(f"- {w['start_time']}: {cell(w['title'])} (ID `{w['id']}`).")
    # Solo IDs inequívocos: las coincidencias por título quedan fuera del volumen.
    for entry in sessions:
        if entry["match"] != "routine_id":
            continue
        for ex in entry["workout"].get("exercises", []):
            template = templates.get(ex["exercise_template_id"], {})
            muscle = template.get("primary_muscle_group") or "sin clasificar"
            muscle_totals[muscle] += len(working_sets(ex))
    lines.extend([
        "", "## Series registradas por músculo principal", "",
        "Solo sesiones vinculadas por ID. Cada serie se atribuye una vez al músculo principal de Hevy;",
        "no mide estímulo efectivo ni incluye trabajo indirecto. La media usa toda la ventana,",
        "incluidas las semanas sin sesiones. No representa necesariamente tu frecuencia actual.", "",
        "| Músculo de Hevy | Series registradas | Media semanal |",
        "| --- | ---: | ---: |",
    ])
    for muscle, count in sorted(muscle_totals.items()):
        lines.append(f"| {cell(muscle)} | {count} | {count / weeks:.2f} |")
    lines.extend(["", "## Revisión inicial de D", ""])
    priority = next(r for r in snapshot["routines"] if normalize(r["title"]) == normalize(snapshot["priority"]))
    findings = []
    for ex in priority.get("exercises", []):
        title = cell(ex["title"])
        sets = working_sets(ex)
        if not sets:
            findings.append(f"{title}: no tiene series de trabajo programadas; confirmar si es intencional.")
        if any(target(s) == "sin objetivo registrado" for s in sets):
            findings.append(f"{title}: completar los objetivos ausentes antes de evaluar progresión.")
        if ex.get("rest_seconds") is None:
            findings.append(f"{title}: registrar un descanso para comparar sesiones en condiciones similares.")
    own_d = [s for s in sessions if s["routine_id"] == priority["id"] and s["match"] == "routine_id"]
    if len(own_d) < 2:
        findings.append("Faltan al menos dos sesiones inequívocas de D para comparar rendimiento.")
    lines.extend(f"- {finding}" for finding in findings)
    if not findings:
        lines.append("No se detectaron objetivos ni descansos ausentes. Esto no demuestra que D sea óptima.")
    lines.extend([
        "", "## Contexto para preparar la mejora", "",
        "Usar snapshot.json para inspeccionar series, repeticiones, cargas, RPE, notas y superseries.",
        "Comparar cada ejercicio por exercise_template_id, separando calentamientos, dropsets y fallo.",
        "Revisar D junto con la distribución de ejercicios y frecuencia real de B y E.",
        "Preparar una propuesta de D con orden, series, rangos, descansos y criterio de progresión;",
        "justificar cada cambio con los datos. No inferir estancamiento por comparar solo tonelaje.",
        "Faltan: días disponibles, orden semanal, tiempo por sesión, equipo y molestias/limitaciones.",
        "El objetivo ya está definido: hipertrofia. No cambiar Hevy durante la revisión.",
        "", f"Otras sesiones en la ventana no atribuibles a estas rutinas: {snapshot['unmatched_workouts_in_window']}.",
        "Este archivo contiene observaciones de los datos, no una rutina mejorada por IA.", "",
    ])
    return "\n".join(lines)
