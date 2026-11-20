"""Cambios de rutina reproducibles: exportar, revisar diferencias y aplicar con versión, respaldo y verificación."""

from datetime import datetime, timezone
import json

from .hevy import HevyError, NotFound, normalize


FORMAT = 1
SET_TYPES = ("warmup", "normal", "failure", "dropset")
SET_FIELDS = ("type", "weight_kg", "reps", "distance_meters", "duration_seconds", "custom_metric", "rep_range")
EXERCISE_FIELDS = ("exercise_template_id", "superset_id", "rest_seconds", "notes")
# Hevy devuelve 0 o null indistintamente en métricas que la rutina no usa.
ZERO_IS_EMPTY = ("distance_meters", "duration_seconds", "custom_metric")


def to_body(routine):
    """Convierte una rutina leída de Hevy en el cuerpo que acepta PUT /v1/routines/{id}."""
    return {"title": routine["title"], "exercises": [
        {
            "exercise_title": ex.get("title"),  # Solo informativo; se quita antes de enviar.
            **{field: ex.get(field) for field in EXERCISE_FIELDS},
            "sets": [{field: s.get(field) for field in SET_FIELDS} for s in ex.get("sets", [])],
        }
        for ex in routine.get("exercises", [])
    ]}


def export(routine, now=None):
    now = now or datetime.now(timezone.utc)
    return {
        "format": FORMAT, "routine_id": routine["id"], "base_updated_at": routine.get("updated_at"),
        "exported_at": now.isoformat(),
        "instructions": "Editar 'routine' y aplicar con: python3 -m fitness_agent routine apply <archivo>. "
                        "exercise_title es informativo; los ejercicios se identifican por exercise_template_id.",
        "routine": to_body(routine),
    }


def is_int(value):
    return type(value) is int


def is_number(value):
    return type(value) in (int, float)


def validate(proposal):
    if not isinstance(proposal, dict) or proposal.get("format") != FORMAT:
        raise HevyError("El archivo no es una exportación de rutina compatible (format 1).")
    for key in ("routine_id", "base_updated_at"):
        if not isinstance(proposal.get(key), str) or not proposal[key]:
            raise HevyError(f"Falta {key} en el archivo de rutina.")
    routine = proposal.get("routine")
    if not isinstance(routine, dict) or not isinstance(routine.get("title"), str) or not routine["title"].strip():
        raise HevyError("La rutina necesita un título.")
    exercises = routine.get("exercises")
    if not isinstance(exercises, list) or not exercises:
        raise HevyError("La rutina necesita al menos un ejercicio.")
    for n, ex in enumerate(exercises, 1):
        where = f"Ejercicio {n}"
        if not isinstance(ex, dict) or not isinstance(ex.get("exercise_template_id"), str) or not ex["exercise_template_id"]:
            raise HevyError(f"{where}: falta exercise_template_id.")
        unknown = set(ex) - {"exercise_title", "sets", *EXERCISE_FIELDS}
        if unknown:
            raise HevyError(f"{where}: campos no admitidos: {', '.join(sorted(unknown))}.")
        if ex.get("superset_id") is not None and not is_int(ex["superset_id"]):
            raise HevyError(f"{where}: superset_id debe ser entero o null.")
        if ex.get("rest_seconds") is not None and (not is_int(ex["rest_seconds"]) or ex["rest_seconds"] < 0):
            raise HevyError(f"{where}: rest_seconds debe ser un entero no negativo o null.")
        if ex.get("notes") is not None and not isinstance(ex["notes"], str):
            raise HevyError(f"{where}: notes debe ser texto o null.")
        sets = ex.get("sets")
        if not isinstance(sets, list) or not sets:
            raise HevyError(f"{where}: necesita al menos una serie.")
        for m, s in enumerate(sets, 1):
            label = f"{where}, serie {m}"
            if not isinstance(s, dict) or s.get("type") not in SET_TYPES:
                raise HevyError(f"{label}: type debe ser {', '.join(SET_TYPES)}.")
            if set(s) - set(SET_FIELDS):
                raise HevyError(f"{label}: campos no admitidos: {', '.join(sorted(set(s) - set(SET_FIELDS)))}.")
            for field in ("weight_kg", "custom_metric"):
                if s.get(field) is not None and (not is_number(s[field]) or s[field] < 0):
                    raise HevyError(f"{label}: {field} debe ser un número no negativo o null.")
            for field in ("reps", "distance_meters", "duration_seconds"):
                if s.get(field) is not None and (not is_int(s[field]) or s[field] < 0):
                    raise HevyError(f"{label}: {field} debe ser un entero no negativo o null.")
            rep_range = s.get("rep_range")
            if rep_range is not None:
                if not isinstance(rep_range, dict) or set(rep_range) - {"start", "end"}:
                    raise HevyError(f"{label}: rep_range debe tener solo start y end.")
                low, high = rep_range.get("start"), rep_range.get("end")
                if any(v is not None and (not is_int(v) or v < 0) for v in (low, high)) or \
                        (low is not None and high is not None and low > high):
                    raise HevyError(f"{label}: rep_range inválido.")
    return proposal


def request_body(body):
    return {"routine": {"title": body["title"], "exercises": [
        {k: v for k, v in ex.items() if k != "exercise_title"} for ex in body["exercises"]
    ]}}


def comparable(body):
    def value(field, v):
        if field in ZERO_IS_EMPTY and v in (0, None):
            return None
        if field == "weight_kg" and v is not None:
            return round(v, 3)
        if field == "rep_range" and (v is None or (v.get("start") is None and v.get("end") is None)):
            return None
        if field == "rep_range":
            return (v.get("start"), v.get("end"))
        return v
    return (body["title"].strip(), tuple(
        (tuple(ex.get(f) for f in EXERCISE_FIELDS),
         tuple(tuple(value(f, s.get(f)) for f in SET_FIELDS) for s in ex["sets"]))
        for ex in body["exercises"]
    ))


def describe_set(s):
    parts = [s.get("type") or "?"]
    if s.get("weight_kg") is not None:
        parts.append(f"{round(s['weight_kg'], 2)} kg")
    rep_range = s.get("rep_range") or {}
    if rep_range.get("start") is not None or rep_range.get("end") is not None:
        parts.append(f"{rep_range.get('start')}–{rep_range.get('end')} reps")
    elif s.get("reps") is not None:
        parts.append(f"{s['reps']} reps")
    return " ".join(parts)


def diff(current, desired):
    """Diferencias legibles entre dos cuerpos de rutina. Lista vacía si son equivalentes."""
    if comparable(current) == comparable(desired):
        return []
    lines = []
    if current["title"].strip() != desired["title"].strip():
        lines.append(f"Título: {current['title']} → {desired['title']}")

    def name(ex):
        return ex.get("exercise_title") or ex["exercise_template_id"]
    before = [ex["exercise_template_id"] for ex in current["exercises"]]
    after = [ex["exercise_template_id"] for ex in desired["exercises"]]
    if before != after:
        titles = {ex["exercise_template_id"]: name(ex) for ex in current["exercises"] + desired["exercises"]}
        lines.append("Ejercicios: " + " → ".join(titles[i] for i in before))
        lines.append("        a: " + " → ".join(titles[i] for i in after))
        for i in dict.fromkeys(before):
            if i not in after:
                lines.append(f"Se quita: {titles[i]}")
        for i in dict.fromkeys(after):
            if i not in before:
                lines.append(f"Se agrega: {titles[i]}")
    # Emparejar cada ejercicio deseado con la primera aparición libre del mismo template.
    pending = list(enumerate(current["exercises"]))
    for ex in desired["exercises"]:
        match = next((pair for pair in pending if pair[1]["exercise_template_id"] == ex["exercise_template_id"]), None)
        if match is None:
            continue
        pending.remove(match)
        old = match[1]
        for field in ("superset_id", "rest_seconds", "notes"):
            if old.get(field) != ex.get(field):
                lines.append(f"{name(ex)}: {field} {old.get(field)!r} → {ex.get(field)!r}")
        old_sets = [describe_set(s) for s in old["sets"]]
        new_sets = [describe_set(s) for s in ex["sets"]]
        if comparable({"title": "", "exercises": [old]}) != comparable({"title": "", "exercises": [dict(old, sets=ex["sets"])]}):
            lines.append(f"{name(ex)}: series [{'; '.join(old_sets)}] → [{'; '.join(new_sets)}]")
    return lines or ["Cambios menores en valores de series."]


def apply(client, proposal, write_backup, confirm=False, now=None):
    """Simula por defecto. Con confirm: comprueba versión, respalda, escribe y vuelve a leer para verificar."""
    validate(proposal)
    now = now or datetime.now(timezone.utc)
    routine_id = proposal["routine_id"]
    current = client.routine(routine_id)
    if current.get("updated_at") != proposal["base_updated_at"]:
        raise HevyError(
            f"La rutina cambió en Hevy desde la exportación ({proposal['base_updated_at']} → {current.get('updated_at')}). "
            "Terminar un entrenamiento también la actualiza. Exportala de nuevo y repetí los cambios."
        )
    desired = proposal["routine"]
    changes = diff(to_body(current), desired)
    if not changes:
        return {"status": "sin_cambios", "changes": []}
    known = {ex["exercise_template_id"] for ex in current.get("exercises", [])}
    for template_id in {ex["exercise_template_id"] for ex in desired["exercises"]} - known:
        try:
            client.exercise(template_id)
        except NotFound:
            raise HevyError(f"El ejercicio {template_id} no existe en Hevy; no se modificó la rutina.") from None
    if not confirm:
        return {"status": "simulacion", "changes": changes}
    backup = write_backup(routine_id, now, json.dumps({
        "routine_before": current, "requested": request_body(desired), "saved_at": now.isoformat(),
    }, ensure_ascii=False, indent=2) + "\n")
    client.update_routine(routine_id, request_body(desired))
    verified = client.routine(routine_id)
    if comparable(to_body(verified)) != comparable(desired) or verified.get("folder_id") != current.get("folder_id"):
        raise HevyError(f"Hevy no quedó como se pidió. Revisá la rutina; el estado anterior está en {backup}.")
    return {"status": "aplicado", "changes": changes, "backup": str(backup), "updated_at": verified.get("updated_at")}


def find_routine(routines, reference):
    """Acepta el ID exacto o el título completo (mismas reglas que sync)."""
    by_id = [r for r in routines if r["id"] == reference]
    if by_id:
        return by_id[0]
    matches = [r for r in routines if normalize(r["title"]) == normalize(reference)]
    if len(matches) != 1:
        raise HevyError(f"No se encontró una única rutina para '{reference}'. Usá el ID o el título completo.")
    return matches[0]
