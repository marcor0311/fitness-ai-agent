"""Contexto verificable para revisar las rutinas; no inventa progreso ni prescribe cargas."""

from collections import Counter
import json
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


def load_preferences(path):
    """Lee data/preferences.json. Sin archivo devuelve None; con formato inválido falla antes de escribir."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        prefs = json.loads(raw)
    except ValueError:
        raise HevyError(f"{path.name} no es JSON válido; no se reemplazó la descarga anterior.") from None
    if not isinstance(prefs, dict):
        raise HevyError(f"{path.name} debe contener un objeto JSON.")
    omitted = prefs.get("temporarily_omitted_exercises_by_routine", {})
    if not isinstance(omitted, dict) or not all(
            isinstance(ids, list) and all(isinstance(i, str) for i in ids) for ids in omitted.values()):
        raise HevyError("temporarily_omitted_exercises_by_routine debe asociar IDs de rutina a listas de IDs.")
    order = prefs.get("D_exercise_order", [])
    if not isinstance(order, list) or not all(isinstance(i, str) for i in order):
        raise HevyError("D_exercise_order debe ser una lista de exercise_template_id.")
    rest = prefs.get("rest_seconds")
    if rest is not None and (type(rest) is not int or rest <= 0):
        raise HevyError("rest_seconds debe ser un entero positivo.")
    return prefs


def omitted_ids(preferences, routine_id):
    return set((preferences or {}).get("temporarily_omitted_exercises_by_routine", {}).get(routine_id, []))


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


LB_PER_KG = 1 / 0.45359237


def number(value):
    return f"{value:.1f}".rstrip("0").rstrip(".")


def load(s):
    # Hevy guarda kg; se muestra también en lb porque las cargas suelen cargarse en libras.
    kg = s.get("weight_kg")
    return "sin carga" if kg is None else f"{number(kg)} kg ({number(kg * LB_PER_KG)} lb)"


def performed(s):
    reps = s.get("reps")
    return f"{load(s)} × {reps if reps is not None else '?'}"


def out_of_range(planned, done):
    """Compara las repeticiones registradas con el rango previsto de la misma serie."""
    rep_range = (planned or {}).get("rep_range") or {}
    low, high, reps = rep_range.get("start"), rep_range.get("end"), done.get("reps")
    if low is None or high is None or reps is None:
        return None
    if reps < low:
        return f"{reps} < {low}"
    if reps > high:
        return f"{reps} > {high}"
    return None


def compare_sessions(routine, previous, current, omitted):
    """Contrasta dos sesiones de la misma rutina por exercise_template_id, sin interpretar."""
    def index(workout):
        return {ex["exercise_template_id"]: (i, ex) for i, ex in enumerate(workout.get("exercises", []))}
    before, after = index(previous), index(current)
    lines = [
        f"Sesiones comparadas: {previous['start_time']} y {current['start_time']}.",
        "Solo series de trabajo. Δ reps se calcula serie a serie cuando la carga es igual;",
        "Hevy no registró RPE, por lo que no se evalúa proximidad al fallo.", "",
        "| Ejercicio | Anterior | Última | Δ reps a igual carga | Fuera del rango previsto | Condiciones |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    planned = {ex["exercise_template_id"]: ex for ex in routine.get("exercises", [])}
    order = [ex["exercise_template_id"] for ex in routine.get("exercises", [])]
    order += [i for i in [*before, *after] if i not in order and i not in omitted]
    for template_id in dict.fromkeys(order):
        if template_id in omitted and template_id not in before and template_id not in after:
            continue
        (pos_a, ex_a), (pos_b, ex_b) = before.get(template_id, (None, None)), after.get(template_id, (None, None))
        title = (ex_b or ex_a or planned.get(template_id, {})).get("title", template_id)
        sets_a, sets_b = working_sets(ex_a or {}), working_sets(ex_b or {})
        deltas = []
        for a, b in zip(sets_a, sets_b):
            if a.get("weight_kg") is not None and a.get("weight_kg") == b.get("weight_kg") \
                    and a.get("reps") is not None and b.get("reps") is not None:
                deltas.append(f"{b['reps'] - a['reps']:+d}")
            else:
                deltas.append("carga distinta")
        targets = working_sets(planned.get(template_id, {}))
        misses = [m for m in (out_of_range(t, d) for t, d in zip(targets, sets_b)) if m]
        conditions = []
        if ex_a is None and ex_b is None:
            conditions.append("no se registró en ninguna")
        elif ex_a is None or ex_b is None:
            conditions.append("no se registró en la " + ("anterior" if ex_a is None else "última"))
        else:
            if pos_a != pos_b:
                conditions.append(f"posición {pos_a + 1} → {pos_b + 1}")
            if ex_a.get("superset_id") != ex_b.get("superset_id"):
                conditions.append("cambió la superserie")
            if len(sets_a) != len(sets_b):
                conditions.append(f"series {len(sets_a)} → {len(sets_b)}")
        if template_id in omitted:
            conditions.append("marcado como omitido")
        lines.append("| " + " | ".join(map(cell, [
            title, "; ".join(map(performed, sets_a)) or "—", "; ".join(map(performed, sets_b)) or "—",
            ", ".join(deltas) or "—", ", ".join(misses) or "—", "; ".join(conditions) or "—",
        ])) + " |")
    minutes = []
    for w in (previous, current):
        minutes.append(round((timestamp(w["end_time"]) - timestamp(w["start_time"])).total_seconds() / 60))
    lines.extend(["", f"Duración registrada: {minutes[0]} min → {minutes[1]} min."])
    return lines


def build_snapshot(routines, workouts, templates, weeks, now=None, preferences=None):
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
        # Copia de las preferencias usadas, para que el informe sea reproducible desde el snapshot.
        "preferences": preferences,
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
    preferences = snapshot.get("preferences")
    lines.insert(-1, "Preferencias aplicadas desde data/preferences.json." if preferences
                 else "Sin data/preferences.json: no se aplicaron omisiones ni preferencias.")
    muscle_totals = Counter()
    for routine in snapshot["routines"]:
        own = [s for s in sessions if s["routine_id"] == routine["id"]]
        fallback = sum(s["match"] == "title_fallback" for s in own)
        omitted = omitted_ids(preferences, routine["id"])
        exercises = routine.get("exercises", [])
        planned = sum(len(working_sets(ex)) for ex in exercises if ex["exercise_template_id"] not in omitted)
        reference = sum(len(working_sets(ex)) for ex in exercises if ex["exercise_template_id"] in omitted)
        lines.extend([
            f"## {cell(routine['title'])}", "", f"ID: `{routine['id']}`.",
            f"Sesiones en la ventana: {len(own)} ({len(own) / weeks:.2f}/semana).",
            f"Asociaciones por título sin routine_id: {fallback}; verificar si corresponden.",
            f"Series de trabajo previstas: {planned}." + (
                f" Guardadas solo como referencia (omitidas por preferencia): {reference}." if reference else ""),
            "",
            "| Ejercicio | Estado | Series de trabajo | Objetivos por serie | Descanso | Superserie |",
            "| --- | --- | ---: | --- | --- | --- |",
        ])
        notes = []
        for ex in exercises:
            sets = working_sets(ex)
            rest = ex.get("rest_seconds")
            lines.append("| " + " | ".join(map(cell, [
                ex["title"], "omitido, referencia" if ex["exercise_template_id"] in omitted else "a realizar",
                len(sets), "; ".join(target(s) for s in sets) or "—",
                f"{rest} s" if rest is not None else "sin registrar",
                ex.get("superset_id") if ex.get("superset_id") is not None else "—",
            ])) + " |")
            if ex.get("notes"):
                notes.append(f"- Nota de {cell(ex['title'])}: {cell(ex['notes'])}")
        missing = sorted(omitted - {ex["exercise_template_id"] for ex in exercises})
        notes.extend(f"- La preferencia omite `{cell(i)}`, que ya no está en la rutina; revisar preferences.json."
                     for i in missing)
        if notes:
            lines.extend(["", *notes])
        if own:
            lines.extend(["", "Últimas sesiones (series de trabajo registradas en Hevy):", ""])
            for entry in own[-3:]:
                w = entry["workout"]
                done = sum(len(working_sets(ex)) for ex in w.get("exercises", []))
                lines.append(f"- {w['start_time']}: {cell(w['title'])} (ID `{w['id']}`): {done} de {planned} previstas.")
                for ex in w.get("exercises", []):
                    if ex["exercise_template_id"] in omitted and working_sets(ex):
                        lines.append(f"  - Se registró {cell(ex['title'])}, marcado como omitido: revisar.")
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
    if preferences:
        omitted = omitted_ids(preferences, priority["id"])
        expected_rest = preferences.get("rest_seconds")
        if expected_rest is not None:
            for ex in priority.get("exercises", []):
                rest = ex.get("rest_seconds")
                if ex["exercise_template_id"] not in omitted and rest is not None and rest != expected_rest:
                    findings.append(f"{cell(ex['title'])}: descanso de {rest} s; la preferencia es {expected_rest} s.")
        fly_sets = preferences.get("chest_fly_sets_per_session")
        if type(fly_sets) is int:
            for ex in priority.get("exercises", []):
                if normalize(ex["title"]).startswith("chest fly") and len(working_sets(ex)) != fly_sets:
                    findings.append(f"{cell(ex['title'])}: {len(working_sets(ex))} series; la preferencia es {fly_sets}.")
        expected_order = preferences.get("D_exercise_order") or []
        actual_order = [ex["exercise_template_id"] for ex in priority.get("exercises", [])]
        if expected_order and actual_order != expected_order:
            position = next((i for i, (a, b) in enumerate(zip(actual_order, expected_order)) if a != b),
                            min(len(actual_order), len(expected_order)))
            findings.append(f"El orden de D difiere del acordado desde la posición {position + 1}; "
                            "confirmar antes de comparar sesiones.")
    own_d = [s for s in sessions if s["routine_id"] == priority["id"] and s["match"] == "routine_id"]
    if len(own_d) < 2:
        findings.append("Faltan al menos dos sesiones inequívocas de D para comparar rendimiento.")
    lines.extend(f"- {finding}" for finding in findings)
    if not findings:
        lines.append("No se detectaron objetivos ni descansos ausentes. Esto no demuestra que D sea óptima.")
    if len(own_d) >= 2:
        lines.extend(["", "## D: últimas dos sesiones por ejercicio", "",
                      *compare_sessions(priority, own_d[-2]["workout"], own_d[-1]["workout"],
                                        omitted_ids(preferences, priority["id"]))])
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
