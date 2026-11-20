from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from fitness_agent.cli import private_write
from fitness_agent.session_report import generate


NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
TEMPLATES = {"fly": {"primary_muscle_group": "chest"}, "row": {"primary_muscle_group": "upper_back"},
             "omit": {"primary_muscle_group": "upper_back"}}


def s(weight, reps, kind="normal", rep_range=None):
    return {"type": kind, "weight_kg": weight, "reps": reps, "rep_range": rep_range}


ROUTINE = {"id": "D", "title": "D", "updated_at": "2026-11-13T00:00:00Z", "exercises": [
    {"title": "Chest Fly", "exercise_template_id": "fly", "rest_seconds": 90,
     "sets": [s(None, None, rep_range={"start": 8, "end": 12})] * 2},
    {"title": "Row", "exercise_template_id": "row", "rest_seconds": 90,
     "sets": [s(None, None, rep_range={"start": 8, "end": 12})] * 2},
    {"title": "Iso", "exercise_template_id": "omit", "rest_seconds": 90, "sets": [s(None, None)] * 2},
]}
PREFERENCES = {"temporarily_omitted_exercises_by_routine": {"D": ["omit"]}}


def session(workout_id, day, exercises, routine_id="D", **changes):
    result = {"id": workout_id, "title": "D", "routine_id": routine_id, "updated_at": f"2026-11-{day}T13:00:00Z",
              "start_time": f"2026-11-{day}T12:00:00Z", "end_time": f"2026-11-{day}T12:45:00Z",
              "description": "", "exercises": [
                  {"title": title, "exercise_template_id": template, "notes": None, "superset_id": None, "sets": sets}
                  for title, template, sets in exercises]}
    result.update(changes)
    return result


OLD = session("old", "06", [("Chest Fly", "fly", [s(25, 9), s(20, 9)]), ("Row", "row", [s(45, 11), s(45, 11)])])
NEW = session("NEW-ID", "13", [("Chest Fly", "fly", [s(10, 12, "warmup"), s(25, 6), s(20, 8)]),
                               ("Row", "row", [s(45, 12), s(45, 13)])])


class SessionReportTests(unittest.TestCase):
    def run_generate(self, folder, received, history, force=False):
        written = []

        def write(path, content):
            written.append(path.name)
            private_write(path, content)
        result = generate(received, history, lambda rid: ROUTINE if rid == "D" else None, TEMPLATES,
                          PREFERENCES, Path(folder), write, NOW, force)
        return result, written

    def load(self, folder, workout_id):
        base = Path(folder) / workout_id.lower()
        return json.loads(base.with_suffix(".json").read_text()), base.with_suffix(".md").read_text()

    def test_report_metrics_and_structure(self):
        with tempfile.TemporaryDirectory() as folder:
            result, written = self.run_generate(folder, [NEW], [OLD, NEW])
            self.assertEqual(result["generated"], ["NEW-ID"])
            self.assertEqual(written, ["new-id.md", "new-id.json"])
            context, md = self.load(folder, "NEW-ID")
            fly, row = context["exercises"]
            self.assertEqual(fly["warmups"], 1)
            self.assertEqual(fly["previous"]["deltas_equal_load"], [-3, -1])
            self.assertEqual(fly["out_of_range"], ["6 < 8"])
            self.assertTrue(row["all_sets_at_top_of_range"])
            self.assertEqual(context["totals"]["working_sets"], 4)
            self.assertEqual(context["totals"]["planned_working_sets"], 4)  # El omitido no cuenta.
            self.assertEqual(context["totals"]["planned_not_done"], [])
            self.assertEqual(context["totals"]["sets_by_primary_muscle"], {"chest": 2, "upper_back": 2})
            self.assertEqual(context["recent"]["sessions_7d"], 2)
            for heading in ("## 1. Lectura", "## 2. Análisis por ejercicio", "## 3. Trabajo para hipertrofia",
                            "## 4. Contexto reciente", "## 5. Próximas acciones", "## 6. Datos faltantes"):
                self.assertIn(heading, md)
            self.assertIn("Row: todas las series en o sobre el tope del rango previsto.", md)
            self.assertIn("No se registró RPE", md)
            self.assertIn("1 mejoraron, 1 con alguna caída", md)

    def test_idempotent_and_regenerates_after_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_generate(folder, [NEW], [OLD, NEW])
            result, written = self.run_generate(folder, [NEW], [OLD, NEW])
            self.assertEqual((result["generated"], written), ([], []))
            edited = deepcopy(NEW)
            edited["description"] = "Molestia leve en hombro"
            # La copia recibida es la vieja; el historial de Hevy trae la edición y prevalece.
            result, _ = self.run_generate(folder, [NEW], [OLD, edited])
            self.assertEqual(result["generated"], ["NEW-ID"])
            self.assertIn("Molestia leve en hombro", self.load(folder, "NEW-ID")[1])

    def test_without_routine_or_history_still_reports_limits(self):
        lone = session("lone", "13", [("Running", "run", [s(None, None)])], routine_id=None)
        with tempfile.TemporaryDirectory() as folder:
            self.run_generate(folder, [lone], [])
            context, md = self.load(folder, "lone")
            self.assertIsNone(context["routine"])
            self.assertIn("Sin rutina asociada", md)
            self.assertIn("Sin sesión anterior comparable: Running.", md)
            self.assertIn("ya no figura en el historial de Hevy", md)

    def test_missing_and_omitted_exercises_are_visible(self):
        partial = session("partial", "13", [("Iso", "omit", [s(40, 8)])])
        with tempfile.TemporaryDirectory() as folder:
            self.run_generate(folder, [partial], [OLD, partial])
            context, md = self.load(folder, "partial")
            self.assertEqual(context["totals"]["planned_not_done"], ["Chest Fly", "Row"])
            self.assertEqual(context["totals"]["omitted_but_logged"], ["Iso"])
            self.assertIn("omitido por preferencia", md)

    def test_unfinished_workouts_are_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            result, written = self.run_generate(folder, [dict(NEW, end_time=None)], [])
            self.assertEqual((result["generated"], written), ([], []))


if __name__ == "__main__":
    unittest.main()
