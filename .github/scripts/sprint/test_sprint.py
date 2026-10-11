"""Tests de sprint.py (lógica pura, sin red). Corren en CI: ver ci.yml."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sprint  # noqa: E402

NOW = datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc)   # martes 13/10, 12h ART


def issue(ident, state_type, due=None, who="Juan", sp=2, updated="2026-10-13T10:00:00Z",
          completed=None, state_name=None):
    names = {"completed": "Done", "started": "In Progress", "unstarted": "Todo",
             "backlog": "Backlog", "canceled": "Canceled"}
    return {"identifier": ident, "title": f"Ticket {ident}", "url": f"https://linear.app/x/{ident}",
            "estimate": sp, "dueDate": due, "updatedAt": updated, "completedAt": completed,
            "state": {"name": state_name or names[state_type], "type": state_type},
            "assignee": {"name": who} if who else None}


def pr(n, created, draft=False, decision=""):
    return {"number": n, "title": f"PR {n}", "url": f"https://gh/pr/{n}", "createdAt": created,
            "isDraft": draft, "reviewDecision": decision, "baseRefName": "dev",
            "mergedAt": None}


class SprintOf(unittest.TestCase):
    def test_closest_due_date_is_current_sprint(self):
        issues = [issue("SPO-1", "started", "2026-10-15"), issue("SPO-2", "unstarted", "2026-10-22"),
                  issue("SPO-3", "completed", "2026-10-08")]
        due, tickets = sprint.sprint_of(issues, NOW.date())
        self.assertEqual(str(due), "2026-10-15")
        self.assertEqual([i["identifier"] for i in tickets], ["SPO-1"])

    def test_canceled_does_not_define_a_sprint(self):
        due, _ = sprint.sprint_of([issue("SPO-1", "canceled", "2026-10-15")], NOW.date())
        self.assertIsNone(due)


class Health(unittest.TestCase):
    def test_all_good_is_ok_and_short(self):
        issues = [issue("SPO-1", "completed", "2026-10-15"), issue("SPO-2", "started", "2026-10-15")]
        r = sprint.health_report(issues, [], NOW)
        self.assertEqual(r["status"], "ok")
        self.assertIn("1/2 tickets", r["summary"])
        self.assertEqual(r["findings"], [])

    def test_overdue_is_urgent(self):
        r = sprint.health_report([issue("SPO-9", "started", "2026-10-08")], [], NOW)
        self.assertEqual(r["status"], "fail")
        self.assertIn("sprint ya cerrado", r["findings"][0]["title"])

    def test_wip_over_limit(self):
        issues = [issue(f"SPO-{n}", "started", "2026-10-15", who="Pache") for n in range(3)]
        r = sprint.health_report(issues, [], NOW)
        self.assertTrue(any("Pache tiene 3" in f["title"] for f in r["findings"]))

    def test_in_review_is_not_wip(self):
        issues = [issue("SPO-1", "started", "2026-10-15", who="Juan")] + \
                 [issue(f"SPO-{n}", "started", "2026-10-15", who="Juan", state_name="In Review",
                        updated="2026-10-01T10:00:00Z") for n in range(2, 5)]
        r = sprint.health_report(issues, [], NOW)
        titles = " ".join(f["title"] for f in r["findings"])
        self.assertNotIn("tickets en curso", titles)       # no es WIP
        self.assertNotIn("sin movimiento", titles)         # review viejo no es "trabado"
        self.assertIn("1 en curso · 3 en review", r["summary"])

    def test_stale_started_ticket(self):
        r = sprint.health_report([issue("SPO-1", "started", "2026-10-15",
                                        updated="2026-10-09T10:00:00Z")], [], NOW)
        self.assertEqual(r["status"], "warn")

    def test_pr_ages(self):
        prs = [pr(1, "2026-10-09T10:00:00Z"),                     # > 72 h  → urgent
               pr(2, "2026-10-11T10:00:00Z"),                     # 48–72 h → important
               pr(3, "2026-10-13T10:00:00Z"),                     # reciente
               pr(4, "2026-10-01T10:00:00Z", draft=True),         # draft: no cuenta
               pr(5, "2026-10-01T10:00:00Z", decision="APPROVED")]
        r = sprint.health_report([], prs, NOW)
        refs = {f["severity"]: f["ref"] for f in r["findings"]}
        self.assertEqual(refs, {"urgent": "#1", "important": "#2"})

    def test_linear_down_is_said_not_hidden(self):
        r = sprint.health_report(None, [], NOW, linear_error="HTTP 401")
        self.assertEqual(r["status"], "warn")
        self.assertIn("Sin datos de Linear", r["summary"])

    def test_no_sprint_is_said(self):
        r = sprint.health_report([], [], NOW)
        self.assertIn("no hay sprint que medir", r["summary"])


class Weekly(unittest.TestCase):
    def test_counts_only_last_7_days(self):
        issues = [issue("SPO-1", "completed", "2026-10-15", completed="2026-10-12T10:00:00Z", sp=3),
                  issue("SPO-2", "completed", "2026-10-01", completed="2026-09-30T10:00:00Z"),
                  issue("SPO-3", "started", "2026-10-08", sp=4)]
        merged = [dict(pr(1, "2026-10-10T10:00:00Z"), mergedAt="2026-10-12T10:00:00Z"),
                  dict(pr(2, "2026-09-10T10:00:00Z"), mergedAt="2026-09-20T10:00:00Z")]
        m = sprint.weekly_data(issues, [], merged, NOW)["metrics"]
        self.assertEqual((m["tickets_completados_7d"], m["sp_completados_7d"]), (1, 3))
        self.assertEqual(m["prs_mergeados_7d"], 1)
        self.assertEqual((m["arrastre_tickets"], m["arrastre_sp"]), (1, 4))



LONG_TICKET = (
    "**Referencia:** WBS 9.1.2 · Steering 2\n\n**Descripción**\n\nRelease a producción.\n\n"
    "**Pasos**\n\n" + "1. Un paso largo con muchos detalles de configuración.\n" * 60 +
    "\n**Criterios de aceptación**\n\n- [ ] `main` contiene todo lo de `dev`.\n"
    "- [ ] `/health` en 200.\n\n**Notas**\n\n* Rollback si falla.\n\n**Bloqueado por:** —")


def ticket(ident, state_type, desc, sp=1):
    t = issue(ident, state_type, sp=sp)
    t["description"] = desc
    return t


class Dor(unittest.TestCase):
    def test_ac_after_long_steps_is_found(self):
        # El bug del 11/10: con la descripción cortada a 1500 caracteres, el
        # modelo no veía los AC y marcaba "sin AC" a tickets que sí tenían.
        self.assertGreater(LONG_TICKET.index("Criterios de aceptación"), 1500)
        st = sprint.ticket_structure(LONG_TICKET)
        self.assertTrue(st["has_ac_section"])
        self.assertEqual(st["ac_items"], 2)
        self.assertNotIn("Rollback", st["acceptance_criteria"])   # corta en **Notas**
        self.assertTrue(st["has_rf_or_wbs"])

    def test_structure_flags(self):
        data = sprint.dor_data([
            ticket("SPO-1", "backlog", LONG_TICKET),
            ticket("SPO-2", "unstarted", "**Descripción**\n\nHacer algo."),
            ticket("SPO-3", "backlog", LONG_TICKET, sp=5),
            ticket("SPO-4", "backlog", LONG_TICKET, sp=None),
        ])
        flags = {d["id"]: d["flags"] for d in data}
        self.assertEqual(flags["SPO-1"], [])
        self.assertEqual(flags["SPO-2"], ["sin sección de criterios de aceptación", "sin referencia a RF ni WBS"])
        self.assertEqual(flags["SPO-3"], ["estimación 5 > 4: hay que partirlo"])
        self.assertEqual(flags["SPO-4"], ["sin estimación"])

    def test_finish_merges_and_recomputes(self):
        data = sprint.dor_data([ticket("SPO-1", "backlog", LONG_TICKET),
                                ticket("SPO-2", "unstarted", "**Referencia:** RF-01\n\nHacer algo.")])
        llm = {"agent": "dor-readiness", "title": "Definition of Ready", "status": "warn",
               "summary": "un resumen larguísimo del modelo", "findings": [
                   {"severity": "important", "title": "AC 2 vago", "ref": "SPO-1"}]}
        r = sprint.dor_finish(llm, data)
        self.assertEqual(r["status"], "fail")              # SPO-2 está en Todo sin AC
        self.assertEqual(r["findings"][0]["ref"], "SPO-2")
        self.assertEqual(r["summary"], "2 tickets de Backlog y Todo revisados, 2 con algo para corregir.")

    def test_all_ready_is_ok(self):
        data = sprint.dor_data([ticket("SPO-1", "backlog", LONG_TICKET)])
        r = sprint.dor_finish({"status": "ok", "summary": "x", "findings": []}, data)
        self.assertEqual((r["status"], r["findings"]), ("ok", []))
        self.assertIn("todos listos", r["summary"])

    def test_llm_down_still_reports_structure(self):
        data = sprint.dor_data([ticket("SPO-2", "unstarted", "nada")])
        r = sprint.dor_finish({"status": "unknown", "summary": "Formato inesperado.",
                               "sections": [{"title": "Respuesta cruda", "body": "lo que dijo"}]}, data)
        self.assertEqual(r["status"], "fail")
        self.assertFalse(r["ai"])
        self.assertEqual([x["title"] for x in r["sections"]], ["Aviso", "Respuesta cruda"])
        self.assertIn("Formato inesperado.", r["sections"][0]["body"])


class WeeklyFinish(unittest.TestCase):
    def test_everything_folded(self):
        data = sprint.weekly_data([], [], [], NOW)
        r = sprint.weekly_finish({"status": "warn", "summary": "x",
                                  "sections": [{"title": "Avance", "body": "mucho", "open": True}]}, data)
        self.assertEqual([s["open"] for s in r["sections"]], [False, False])
        self.assertTrue(r["sections"][0]["title"].startswith("Métricas"))


if __name__ == "__main__":
    unittest.main()
