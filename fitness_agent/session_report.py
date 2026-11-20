"""Reporte por entrenamiento: métricas calculadas con código y estructura acordada en docs/draft.md.

No llama a modelos de IA. Las secciones de interpretación quedan marcadas como pendientes hasta elegir
modelo, entorno y presupuesto; las cifras ya son verificables y sirven de entrada para ese agente.
"""

from collections import Counter
from datetime import timedelta
import hashlib
import json

from .review import cell, number, omitted_ids, out_of_range, performed, timestamp, working_sets


ANALYSIS_VERSION = "1"


def fingerprint(workout):
    return hashlib.sha256(json.dumps(workout, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def key(workout):
    return workout["id"].lower()


def set_summary(s):
    return {k: s.get(k) for k in ("type", "weight_kg", "reps", "rpe", "duration_seconds", "distance_meters")
            if s.get(k) not in (None, 0) or k in ("type", "reps")}


def equal_load_deltas(previous, current):
    deltas = []
    for a, b in zip(previous, current):
        if a.get("weight_kg") is not None and a.get("weight_kg") == b.get("weight_kg") \
                and a.get("reps") is not None and b.get("reps") is not None:
            deltas.append(b["reps"] - a["reps"])
        else:
            deltas.append(None)
    return deltas


def drop_between_sets(sets):
    """Repeticiones perdidas entre la primera y la última serie con la misma carga."""
    if len(sets) < 2:
        return None
    first, last = sets[0], sets[-1]
    if first.get("weight_kg") != last.get("weight_kg") or first.get("reps") is None or last.get("reps") is None:
        return None
    return first["reps"] - last["reps"]


def build_context(workout, history, routine, templates, preferences, in_hevy, now):
    start = timestamp(workout["start_time"])
    end = timestamp(workout["end_time"]) if workout.get("end_time") else None
    earlier = sorted(
        (w for w in history if key(w) != key(workout) and w.get("start_time") and timestamp(w["start_time"]) < start),
        key=lambda w: timestamp(w["start_time"]),
    )
    omitted = omitted_ids(preferences, routine["id"]) if routine else set()
    planned_pool = list(enumerate(routine.get("exercises", []))) if routine else []
    exercises, muscles, set_types = [], Counter(), Counter()
    for position, ex in enumerate(workout.get("exercises", [])):
        template_id = ex["exercise_template_id"]
        sets = working_sets(ex)
        set_types.update(s.get("type") for s in sets)
        muscle = (templates.get(template_id) or {}).get("primary_muscle_group") or "sin clasificar"
        muscles[muscle] += len(sets)
        plan = next((pair for pair in planned_pool if pair[1]["exercise_template_id"] == template_id), None)
        if plan:
            planned_pool.remove(plan)
        plan_sets = working_sets(plan[1]) if plan else []
        previous = None
        for old in reversed(earlier):
            match = next((e for e in old.get("exercises", []) if e["exercise_template_id"] == template_id), None)
            if match:
                old_sets = working_sets(match)
                conditions = []
                if old.get("routine_id") != workout.get("routine_id"):
                    conditions.append("otra rutina")
                if [s.get("type") for s in old_sets] != [s.get("type") for s in sets]:
                    conditions.append("cambian los tipos de serie")
                if len(old_sets) != len(sets):
                    conditions.append(f"series {len(old_sets)} → {len(sets)}")
                if old.get("routine_id") == workout.get("routine_id"):
                    old_position = old["exercises"].index(match)
                    if old_position != position:
                        conditions.append(f"posición {old_position + 1} → {position + 1}")
                previous = {
                    "below_range": any("<" in (out_of_range(t, d) or "") for t, d in zip(plan_sets, old_sets)),
                    "workout_id": old["id"], "start_time": old["start_time"], "title": old.get("title"),
                    "sets": [set_summary(s) for s in old_sets], "deltas_equal_load": equal_load_deltas(old_sets, sets),
                    "conditions": conditions, "days_before": (start - timestamp(old["start_time"])).days,
                }
                break
        below = [i for i, (t, d) in enumerate(zip(plan_sets, sets)) if "<" in (out_of_range(t, d) or "")]
        top = [(t.get("rep_range") or {}).get("end") for t in plan_sets]
        at_top = bool(sets) and len(sets) >= len(plan_sets) > 0 and all(
            t is not None and d.get("reps") is not None and d["reps"] >= t for t, d in zip(top, sets))
        exercises.append({
            "position": position + 1, "exercise_template_id": template_id, "title": ex.get("title"),
            "primary_muscle": muscle, "sets": [set_summary(s) for s in sets],
            "warmups": len(ex.get("sets", [])) - len(sets),
            "rpe_recorded": any(s.get("rpe") is not None for s in sets),
            "planned_sets": len(plan_sets) if plan else None,
            "planned_rest_seconds": plan[1].get("rest_seconds") if plan else None,
            "out_of_range": [m for m in (out_of_range(t, d) for t, d in zip(plan_sets, sets)) if m],
            "below_range_sets": below, "all_sets_at_top_of_range": at_top,
            "drop_between_sets": drop_between_sets(sets), "marked_omitted": template_id in omitted,
            "previous": previous, "notes": ex.get("notes") or None,
        })
    not_done = [ex.get("title") for _, ex in planned_pool if ex["exercise_template_id"] not in omitted]
    week = [w for w in earlier if timestamp(w["start_time"]) >= start - timedelta(days=7)] + [workout]
    month = [w for w in earlier if timestamp(w["start_time"]) >= start - timedelta(days=28)] + [workout]

    def muscle_sets(workouts):
        total = Counter()
        for w in workouts:
            for e in w.get("exercises", []):
                total[(templates.get(e["exercise_template_id"]) or {}).get("primary_muscle_group") or "sin clasificar"] += \
                    len(working_sets(e))
        return dict(sorted(total.items()))

    missing = []
    if not any(e["rpe_recorded"] for e in exercises):
        missing.append("No se registró RPE: no se evalúa proximidad al fallo.")
    missing.append("Hevy no registra los descansos reales; solo los programados en la rutina.")
    if routine is None:
        missing.append("Sin rutina asociada: no se compara con lo previsto.")
    else:
        missing.append("La rutina comparada es la versión actual en Hevy, que puede diferir de la vigente en la sesión.")
    without_history = [e["title"] for e in exercises if e["previous"] is None]
    if without_history:
        missing.append("Sin sesión anterior comparable: " + ", ".join(without_history) + ".")
    if not in_hevy:
        missing.append("El entrenamiento ya no figura en el historial de Hevy (posible eliminación); se usó la copia recibida.")
    if any(t not in templates for t in {e["exercise_template_id"] for e in exercises}):
        missing.append("Algún ejercicio no tiene grupo muscular disponible.")
    missing.append("Sueño, molestias, técnica y equipo usado no se conocen salvo que estén en las notas.")

    planned_total = sum(len(working_sets(ex)) for ex in routine.get("exercises", [])
                        if ex["exercise_template_id"] not in omitted) if routine else None
    return {
        "analysis_version": ANALYSIS_VERSION, "generated_at": now.isoformat(),
        "workout": {
            "id": workout["id"], "title": workout.get("title"), "start_time": workout["start_time"],
            "end_time": workout.get("end_time"), "updated_at": workout.get("updated_at"),
            "duration_minutes": round((end - start).total_seconds() / 60) if end else None,
            "description": workout.get("description") or None, "routine_id": workout.get("routine_id"),
            "fingerprint": fingerprint(workout), "in_hevy_history": in_hevy,
        },
        "routine": {"id": routine["id"], "title": routine["title"], "updated_at": routine.get("updated_at")} if routine else None,
        "preferences_applied": bool(preferences),
        "totals": {
            "working_sets": sum(len(e["sets"]) for e in exercises), "planned_working_sets": planned_total,
            "set_types": dict(set_types), "sets_by_primary_muscle": dict(sorted(muscles.items())),
            "planned_not_done": not_done,
            "omitted_but_logged": [e["title"] for e in exercises if e["marked_omitted"] and e["sets"]],
        },
        "recent": {
            "sessions_7d": len(week), "sets_by_primary_muscle_7d": muscle_sets(week),
            "sessions_28d": len(month), "history_sessions_available": len(earlier),
        },
        "exercises": exercises, "missing": missing,
    }


def fmt_sets(sets):
    return "; ".join(performed(s) + (f" @RPE {number(s['rpe'])}" if s.get("rpe") is not None else "")
                     + ("" if s.get("type") in (None, "normal") else f" ({s['type']})") for s in sets) or "—"


def render(context):
    w, totals, recent = context["workout"], context["totals"], context["recent"]
    routine = context["routine"]
    exercises = context["exercises"]
    improved = sum(1 for e in exercises if e["previous"] and any(d and d > 0 for d in e["previous"]["deltas_equal_load"])
                   and not any(d is not None and d < 0 for d in e["previous"]["deltas_equal_load"]))
    declined = sum(1 for e in exercises if e["previous"] and any(d is not None and d < 0 for d in e["previous"]["deltas_equal_load"]))
    planned = totals["planned_working_sets"]
    lines = [
        f"# {cell(w['title'] or 'Entrenamiento')} · {w['start_time'][:10]}", "",
        f"Entrenamiento `{w['id']}`. Análisis v{context['analysis_version']} generado {context['generated_at']}.",
        f"Rutina: {cell(routine['title'])} (`{routine['id']}`)." if routine else "Sin rutina asociada.",
        "Pesos en kg y lb. Solo series de trabajo; los calentamientos se excluyen.", "",
        "## 1. Lectura de la sesión", "",
        "> Pendiente: la interpretación la hará el agente analista cuando se elijan modelo y presupuesto.", "",
        f"- Duración: {w['duration_minutes']} min." if w["duration_minutes"] is not None else "- Duración sin registrar.",
        f"- Series de trabajo: {totals['working_sets']}" + (f" de {planned} previstas." if planned is not None else "."),
        f"- Frente a la sesión anterior de cada ejercicio, a igual carga: {improved} mejoraron, {declined} con alguna caída.",
    ]
    if totals["planned_not_done"]:
        lines.append("- Previstos sin registrar: " + ", ".join(map(cell, totals["planned_not_done"])) + ".")
    if totals["omitted_but_logged"]:
        lines.append("- Registrados aunque están omitidos por preferencia: " + ", ".join(map(cell, totals["omitted_but_logged"])) + ".")
    if w["description"]:
        lines.append(f"- Nota de la sesión: {cell(w['description'])}")
    lines.extend([
        "", "## 2. Análisis por ejercicio", "",
        "| # | Ejercicio | Series | Anterior comparable | Δ reps a igual carga | Fuera de rango | Condiciones |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ])
    for e in exercises:
        prev = e["previous"]
        conditions = list(prev["conditions"]) if prev else ["sin historial"]
        if e["marked_omitted"]:
            conditions.append("omitido por preferencia")
        lines.append("| " + " | ".join(map(cell, [
            e["position"], e["title"], fmt_sets(e["sets"]),
            f"{prev['start_time'][:10]}: {fmt_sets(prev['sets'])}" if prev else "—",
            ", ".join("≠ carga" if d is None else f"{d:+d}" for d in prev["deltas_equal_load"]) if prev else "—",
            ", ".join(e["out_of_range"]) or "—", "; ".join(conditions) or "—",
        ])) + " |")
    notes = [f"- {cell(e['title'])}: {cell(e['notes'])}" for e in exercises if e["notes"]]
    if notes:
        lines.extend(["", "Notas registradas:", "", *notes])
    lines.extend([
        "", "## 3. Trabajo para hipertrofia", "",
        "Series atribuidas una vez al músculo principal de Hevy; no mide estímulo ni trabajo indirecto.", "",
        "| Músculo de Hevy | Series de trabajo |", "| --- | ---: |",
        *(f"| {cell(m)} | {n} |" for m, n in totals["sets_by_primary_muscle"].items()),
        "", "Tipos de serie: " + (", ".join(f"{t}: {n}" for t, n in sorted(totals["set_types"].items())) or "ninguna") + ".",
    ])
    drops = [f"{cell(e['title'])} ({e['drop_between_sets']:+d})" for e in exercises if e["drop_between_sets"]]
    if drops:
        lines.append("Repeticiones de la primera menos la última serie, con la misma carga: " + ", ".join(drops) + ".")
    lines.extend([
        "", "## 4. Contexto reciente", "",
        f"Sesiones en los 7 días hasta esta (incluida): {recent['sessions_7d']}. En 28 días: {recent['sessions_28d']}.",
        f"Sesiones anteriores disponibles en Hevy: {recent['history_sessions_available']}.", "",
        "| Músculo de Hevy | Series en 7 días |", "| --- | ---: |",
        *(f"| {cell(m)} | {n} |" for m, n in recent["sets_by_primary_muscle_7d"].items()),
        "", "## 5. Próximas acciones", "",
        "> Pendiente: las propuestas las hará el agente analista. Señales calculadas para considerar:", "",
    ])
    signals = []
    for e in exercises:
        if e["all_sets_at_top_of_range"]:
            signals.append(f"{cell(e['title'])}: todas las series en o sobre el tope del rango previsto.")
        if e["below_range_sets"]:
            repeated = e["previous"] and e["previous"]["below_range"]
            signals.append(f"{cell(e['title'])}: {len(e['below_range_sets'])} serie(s) por debajo del rango previsto"
                           + ("; también en la sesión anterior." if repeated else "."))
    lines.extend(f"- {signal}" for signal in signals or ["Sin señales calculadas."])
    lines.extend(["", "## 6. Datos faltantes y límites", "", *(f"- {m}" for m in context["missing"]), ""])
    return "\n".join(lines)


def generate(workouts, history, load_routine, templates, preferences, folder, write, now, force=False):
    """Genera un reporte por entrenamiento si no existe uno de la misma versión para los mismos datos."""
    by_id = {key(w): w for w in history}
    result = {"generated": [], "unchanged": []}
    for received in workouts:
        workout = by_id.get(key(received), received)  # La copia de Hevy refleja ediciones posteriores.
        if not workout.get("end_time") or not workout.get("start_time"):
            continue
        path = folder / f"{key(workout)}.json"
        if path.exists() and not force:
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                old = {}
            if old.get("analysis_version") == ANALYSIS_VERSION and \
                    old.get("workout", {}).get("fingerprint") == fingerprint(workout):
                result["unchanged"].append(workout["id"])
                continue
        routine = load_routine(workout["routine_id"]) if workout.get("routine_id") else None
        context = build_context(workout, history, routine, templates, preferences, key(workout) in by_id, now)
        # El Markdown se escribe primero: el JSON con la huella marca el reporte como completo.
        write(folder / f"{key(workout)}.md", render(context))
        write(path, json.dumps(context, ensure_ascii=False, indent=2) + "\n")
        result["generated"].append(workout["id"])
    return result
