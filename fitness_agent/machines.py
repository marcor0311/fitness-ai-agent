"""Máquinas físicas del gimnasio y su relación con el catálogo de ejercicios de Hevy.

Hevy describe ejercicios, no máquinas: varios ejercicios se hacen en la misma máquina (Chest Fly y Rear Delt
Reverse Fly en el pec deck; casi todo lo que dice "Cable" en una polea). Cada modelo agrupa esos ejercicios y
tiene un modelo 3D con el mismo id en gym_space.html. Las reglas se evalúan en orden: gana la primera.
"""

from collections import namedtuple


Model = namedtuple("Model", "id name category size equipment keywords exclude")

MACHINE = ("machine",)
# size: ancho (x), alto (y) y fondo (z) aproximados, en metros. El frente de la máquina mira hacia +z.
MODELS = (
    Model("smith", "Máquina Smith", "Peso libre y racks", [2.2, 2.3, 1.5], ("machine", "barbell"), ("smith",), ()),
    Model("assisted", "Dominadas y fondos asistidos", "Espalda", [1.3, 2.4, 1.6], MACHINE, ("(assisted)",), ()),
    Model("lat_pulldown", "Jalón al pecho", "Espalda", [1.4, 2.3, 1.6], MACHINE,
          ("lat pulldown", "vertical traction"), ("straight arm",)),
    Model("seated_row", "Remo sentado en polea", "Espalda", [0.9, 1.5, 2.3], MACHINE, ("seated cable row",), ()),
    Model("leg_press", "Prensa de piernas", "Piernas", [1.5, 1.6, 2.4], MACHINE, ("leg press", "calf press"), ()),
    Model("cable_station", "Polea ajustable", "Polea", [1.4, 2.3, 1.0], ("machine", "resistance_band"),
          ("cable", "pushdown", "pressdown", "face pull", "rope", "pallof", "pull through", "y raise",
           "kneeling pulldown"), ("battle",)),
    Model("belt_squat", "Belt squat", "Piernas", [1.4, 1.2, 2.0], MACHINE, ("belt squat",), ()),
    Model("hack_squat", "Hack squat", "Piernas", [1.4, 1.9, 2.2], MACHINE,
          ("hack squat", "pendulum squat", "squat (machine)", "v squat"), ()),
    Model("leg_extension", "Extensión de cuádriceps", "Piernas", [1.1, 1.3, 1.4], MACHINE,
          ("leg extension", "single leg extensions"), ()),
    Model("lying_leg_curl", "Curl femoral acostado", "Piernas", [1.0, 1.1, 2.0], MACHINE, ("lying leg curl",), ()),
    Model("seated_leg_curl", "Curl femoral sentado", "Piernas", [1.1, 1.3, 1.4], MACHINE,
          ("seated leg curl", "standing leg curl"), ()),
    Model("hip_ab_adductor", "Abductores y aductores", "Piernas", [1.2, 1.3, 1.5], MACHINE,
          ("hip abduction (machine)", "hip adduction (machine)"), ()),
    Model("hip_thrust", "Hip thrust", "Piernas", [1.3, 1.1, 1.8], MACHINE, ("hip thrust (machine)",), ()),
    Model("glute_machine", "Patada de glúteo", "Piernas", [1.0, 1.4, 1.5], MACHINE,
          ("glute kickback (machine)", "rear kick (machine)"), ()),
    Model("standing_calf", "Gemelos de pie", "Piernas", [1.1, 2.1, 1.1], MACHINE,
          ("standing calf raise (machine)", "single leg standing calf raise", "calf extension"), ()),
    Model("seated_calf", "Gemelos sentado", "Piernas", [0.8, 1.1, 1.3], MACHINE, ("seated calf raise",), ()),
    Model("pec_deck", "Pec deck (aperturas y deltoide posterior)", "Pecho y hombro", [1.5, 2.0, 1.4], MACHINE,
          ("pec deck", "chest fly (machine)", "rear delt reverse fly (machine)"), ()),
    Model("chest_press", "Press de pecho", "Pecho y hombro", [1.5, 1.7, 1.5], MACHINE,
          ("chest press", "bench press (machine)"), ()),
    Model("shoulder_press", "Press de hombro", "Pecho y hombro", [1.4, 1.8, 1.4], MACHINE, ("shoulder press",), ()),
    Model("lateral_raise", "Elevaciones laterales", "Pecho y hombro", [1.3, 1.4, 1.2], MACHINE,
          ("lateral raise (machine)",), ()),
    Model("plate_row", "Remo de discos (iso-lateral)", "Espalda", [1.6, 1.6, 1.6], MACHINE,
          ("iso-lateral", "seated row (machine)"), ()),
    Model("t_bar_row", "Remo en T", "Espalda", [1.0, 1.2, 2.2], MACHINE, ("t bar row", "t-bar"), ()),
    Model("pullover", "Pullover", "Espalda", [1.3, 1.9, 1.4], MACHINE, ("pullover (machine)",), ()),
    Model("preacher_curl", "Curl predicador", "Brazos", [0.9, 1.2, 1.2], MACHINE,
          ("preacher curl (machine)", "bicep curl (machine)"), ()),
    Model("triceps_machine", "Tríceps en máquina", "Brazos", [1.2, 1.5, 1.3], MACHINE,
          ("triceps extension (machine)", "seated dip machine", "seated triceps press"), ()),
    Model("back_extension", "Banco de hiperextensiones", "Core y lumbar", [0.8, 1.1, 1.4], MACHINE,
          ("back extension", "hyperextension", "glute ham raise"), ()),
    Model("ab_machine", "Abdominales en máquina", "Core y lumbar", [1.2, 1.5, 1.3], MACHINE,
          ("crunch (machine)", "torso rotation"), ()),
    Model("shrug_machine", "Encogimientos", "Espalda", [1.2, 1.4, 1.2], MACHINE, ("shrug (machine)",), ()),
    Model("power_tower", "Torre de dominadas y fondos", "Peso corporal", [1.3, 2.3, 1.2], MACHINE,
          ("pull up", "chin up", "muscle up", "dip", "parallel bars", "inverted row"), ()),
    Model("treadmill", "Cinta de correr", "Cardio", [0.9, 1.5, 2.0], MACHINE, ("treadmill",), ()),
    Model("bike", "Bicicleta", "Cardio", [0.6, 1.3, 1.3], MACHINE, ("cycling", "spinning", "bike"), ()),
    Model("elliptical", "Elíptica", "Cardio", [0.8, 1.7, 2.0], MACHINE, ("elliptical",), ()),
    Model("rower", "Remo ergómetro", "Cardio", [0.6, 0.9, 2.4], MACHINE, ("rowing machine",), ()),
    Model("stair", "Escaladora", "Cardio", [1.0, 2.0, 1.5], MACHINE, ("stair machine",), ()),
    Model("ski_erg", "Ski erg", "Cardio", [0.7, 2.2, 1.2], MACHINE, ("ski erg",), ()),
    Model("dumbbells", "Mancuernas y banco", "Peso libre y racks", [2.2, 1.0, 1.8], ("dumbbell",), ("",), ()),
    Model("bench_press", "Banco de press con barra", "Peso libre y racks", [1.8, 1.4, 2.0], ("barbell",),
          ("bench press", "floor press"), ()),
    Model("squat_rack", "Rack de sentadilla", "Peso libre y racks", [2.2, 2.3, 1.6], ("barbell",),
          ("squat", "overhead press", "military", "rack", "lunge", "pin press", "good morning"), ()),
    Model("barbell_area", "Zona de barra", "Peso libre y racks", [2.4, 0.5, 2.4], ("barbell",), ("",), ()),
    Model("generic", "Otra máquina", "Otras", [1.2, 1.6, 1.4], MACHINE, ("",), ()),
)
MODEL_IDS = {m.id for m in MODELS}
# Ejercicios de Hevy con equipo "machine" que el usuario no hace; no se ofrecen en el espacio 3D.
IGNORED_TITLES = {"battle ropes", "kelso shrug", "squat row", "wrist roller"}
CATEGORIES = ("Piernas", "Pecho y hombro", "Espalda", "Brazos", "Polea", "Core y lumbar", "Peso corporal",
              "Peso libre y racks", "Cardio", "Otras")


def classify(template):
    """Modelo de máquina para un ejercicio de Hevy, o None si no usa máquina ni barra ni mancuernas."""
    title = " ".join(str(template.get("title") or "").casefold().split())
    if title in IGNORED_TITLES:
        return None
    equipment = template.get("equipment")
    for model in MODELS:
        if equipment in model.equipment and any(k in title for k in model.keywords) \
                and not any(x in title for x in model.exclude):
            return model.id
    return None


def describe():
    """Modelos para la interfaz, sin las reglas internas."""
    return [{"id": m.id, "name": m.name, "category": m.category, "size": m.size} for m in MODELS]


def infer(station, model_by_template):
    """Modelo de una estación sin modelo: el de su primer ejercicio reconocido."""
    for template_id in station.get("exercise_template_ids", []):
        if model_by_template.get(template_id):
            return model_by_template[template_id]
    return None
