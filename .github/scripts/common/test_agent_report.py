"""Tests del formato común (agent_report.py). Corren en CI: ver ci.yml."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import agent_report as ar  # noqa: E402


def sample(**over):
    base = {
        "status": "fail",
        "summary": "NO CUMPLE — faltan dos criterios.",
        "findings": [
            {"severity": "minor", "title": "Typo en el README"},
            {"severity": "urgent", "title": "AC 2 sin implementar", "ref": "SPO-200",
             "detail": "El endpoint no valida el cupo."},
            {"severity": "important", "title": "Falta doc del endpoint"},
        ],
        "sections": [{"title": "Tabla DoD", "body": "| a | b |"},
                     {"title": "Qué probar", "body": "1. algo", "open": True}],
    }
    base.update(over)
    return ar.normalize(base, "dod-checker", "Definition of Done")


class Normalize(unittest.TestCase):
    def test_orders_findings_by_severity(self):
        sevs = [f["severity"] for f in sample()["findings"]]
        self.assertEqual(sevs, ["urgent", "important", "minor"])

    def test_bad_values_are_corrected_not_fatal(self):
        r = ar.normalize({"status": "GREEN", "findings": [{"severity": "huge", "title": "x"},
                                                          {"title": ""}, "basura"]})
        self.assertEqual(r["status"], "unknown")
        self.assertEqual(r["findings"], [{"severity": "minor", "title": "x", "ref": "", "detail": ""}])

    def test_clips_runaway_text(self):
        r = ar.normalize({"status": "warn", "summary": "s" * 900, "findings": [
            {"title": "t" * 900, "ref": "Sprint cierra 2026-10-15; metrics.sprint_hecho=4/15; prs_mergeados_7d=0"}]})
        self.assertLessEqual(len(r["summary"]), ar.MAX_SUMMARY)
        self.assertLessEqual(len(r["findings"][0]["title"]), ar.MAX_TITLE)
        self.assertLessEqual(len(r["findings"][0]["ref"]), ar.MAX_REF)
        self.assertTrue(r["findings"][0]["ref"].endswith("…"))

    def test_caps_findings(self):
        r = ar.normalize({"status": "warn",
                          "findings": [{"title": f"f{i}"} for i in range(40)]})
        self.assertEqual(len(r["findings"]), ar.MAX_FINDINGS)


class FromLlm(unittest.TestCase):
    def test_json_inside_fences(self):
        text = '```json\n{"status": "ok", "summary": "todo bien", "findings": []}\n```'
        r = ar.from_llm(text, "a", "A")
        self.assertEqual((r["status"], r["summary"]), ("ok", "todo bien"))

    def test_json_with_chatter_around(self):
        r = ar.from_llm('Acá va:\n{"status": "warn", "summary": "ojo"}\nSaludos', "a", "A")
        self.assertEqual(r["status"], "warn")

    def test_think_block_with_braces_before_json(self):
        text = '<think>el formato es {status, summary}… pienso {a}</think>\n{"status": "ok", "summary": "bien"}'
        self.assertEqual(ar.from_llm(text, "a", "A")["status"], "ok")

    def test_prose_with_braces_after_json(self):
        text = 'Listo:\n{"status": "warn", "summary": "ojo"}\nNota: usé {llaves} en el texto.'
        self.assertEqual(ar.from_llm(text, "a", "A")["status"], "warn")

    def test_bare_findings_list_infers_status(self):
        text = '[{"severity": "important", "title": "AC vago", "ref": "SPO-1"}]'
        r = ar.from_llm(text, "a", "A")
        self.assertEqual((r["status"], r["findings"][0]["ref"]), ("warn", "SPO-1"))

    def test_missing_status_without_findings_is_ok(self):
        self.assertEqual(ar.from_llm('{"summary": "nada para marcar", "findings": []}', "a", "A")["status"], "ok")

    def test_llm_unavailable_is_unknown(self):
        r = ar.from_llm("LLM_UNAVAILABLE: todos los modelos fallaron; HTTP 429", "a", "A")
        self.assertEqual(r["status"], "unknown")
        self.assertIn("429", r["summary"])

    def test_garbage_is_unknown_and_keeps_raw(self):
        r = ar.from_llm("no soy json", "a", "A")
        self.assertEqual(r["status"], "unknown")
        self.assertEqual(r["sections"][0]["title"], "Respuesta cruda")


class Ask(unittest.TestCase):
    def run_ask(self, answers):
        calls = []
        def call():
            calls.append(1)
            return answers[len(calls) - 1]
        report, _ = ar.ask("prompt.txt", "a", "A", tries=3, call=call)
        return report, len(calls)

    def test_retries_when_a_guard_model_answers(self):
        r, n = self.run_ask(["User Safety: safe", '{"status": "ok", "summary": "bien"}'])
        self.assertEqual((r["status"], n), ("ok", 2))

    def test_gives_up_after_tries(self):
        r, n = self.run_ask(["basura"] * 3)
        self.assertEqual((r["status"], n), ("unknown", 3))

    def test_no_retry_when_chain_is_exhausted(self):
        r, n = self.run_ask(["LLM_UNAVAILABLE: HTTP 429", "{}", "{}"])
        self.assertEqual((r["status"], n), ("unknown", 1))

    def test_first_answer_good(self):
        self.assertEqual(self.run_ask(['{"status": "warn", "summary": "x"}'])[1], 1)


class RenderGithub(unittest.TestCase):
    def test_header_and_marker(self):
        md = ar.render_github(sample())
        self.assertTrue(md.startswith("<!-- agente:dod-checker status=fail -->\n### 🔴 Definition of Done"))
        self.assertIn("**NO CUMPLE — faltan dos criterios.**", md)

    def test_only_urgent_and_important_are_visible(self):
        md = ar.render_github(sample())
        before_first_fold = md.split("<details>")[0]
        self.assertIn("AC 2 sin implementar", before_first_fold)
        self.assertIn("Falta doc del endpoint", before_first_fold)
        self.assertNotIn("Typo en el README", before_first_fold)
        self.assertIn("<details><summary>Menores (1)</summary>", md)

    def test_detail_and_closed_sections_are_folded_open_ones_are_not(self):
        md = ar.render_github(sample())
        self.assertIn("<details><summary>Detalle de los hallazgos</summary>", md)
        self.assertIn("<details><summary>Tabla DoD</summary>", md)
        self.assertNotIn("<summary>Qué probar</summary>", md)
        self.assertIn("**Qué probar**", md)

    def test_ok_report_is_short(self):
        md = ar.render_github(ar.normalize({"status": "ok", "summary": "Listo."}, "x", "X"))
        self.assertLessEqual(len(md.splitlines()), 6)

    def test_summary_variant_has_no_marker(self):
        self.assertNotIn("<!--", ar.render_github(sample(), with_marker=False))


class RenderDiscord(unittest.TestCase):
    def test_compact(self):
        r = sample(context="PR #12 · login", link="https://x/pr/12")
        msg = ar.render_discord(r)
        self.assertEqual(msg.splitlines()[0], "🔴 **Definition of Done** · PR #12 · login")
        self.assertNotIn("Typo", msg)          # los menores no van a Discord
        self.assertNotIn("| a | b |", msg)     # las sections tampoco
        self.assertTrue(msg.endswith("→ https://x/pr/12"))

    def test_caps_findings_and_length(self):
        r = ar.normalize({"status": "fail", "summary": "x" * 5000,
                          "findings": [{"severity": "urgent", "title": f"f{i}"} for i in range(9)]},
                         "a", "A")
        msg = ar.render_discord(r)
        self.assertIn("… y 6 más", msg)
        self.assertLessEqual(len(msg), ar.DISCORD_LIMIT)


class Marker(unittest.TestCase):
    def test_roundtrip(self):
        body = ar.render_github(sample())
        self.assertEqual(ar.parse_marker(body, "dod-checker"), (True, "fail"))

    def test_old_marker_without_status(self):
        self.assertEqual(ar.parse_marker("<!-- agente:dod-checker -->\nhola", "dod-checker"), (True, None))

    def test_other_agent_is_not_mine(self):
        self.assertEqual(ar.parse_marker("<!-- agente:dod-checker-x status=ok -->", "dod-checker")[0], False)


class Policies(unittest.TestCase):
    def test_matrix(self):
        cases = [
            # policy, status, previous, expected
            ("never", "fail", None, False),
            ("always", "ok", "ok", True),
            ("always", "unknown", None, True),
            ("not-ok", "ok", None, False),
            ("not-ok", "warn", "warn", True),
            ("not-ok", "unknown", None, False),
            ("changed", "ok", None, False),      # primera vez y todo bien: silencio
            ("changed", "fail", None, True),     # primera vez con problemas: aviso
            ("changed", "fail", "fail", False),  # mismo estado en otro push: silencio
            ("changed", "ok", "fail", True),     # se arregló: aviso
            ("changed", "unknown", "fail", False),
            ("first", "warn", None, True),       # primera vez con algo: aviso
            ("first", "ok", None, False),
            ("first", "fail", "warn", False),    # el modelo cambió de opinión: silencio
            ("first", "ok", "fail", False),
        ]
        for policy, status, prev, expected in cases:
            with self.subTest(policy=policy, status=status, prev=prev):
                self.assertEqual(ar.should_send(policy, status, prev), expected)


class Cli(unittest.TestCase):
    def test_contract_is_valid_guidance(self):
        self.assertIn('"severity": "urgent" | "important" | "minor"', ar.CONTRACT)

    def test_from_llm_roundtrip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            inp, out = Path(d, "r.txt"), Path(d, "r.json")
            inp.write_text('{"status": "ok", "summary": "bien"}', encoding="utf-8")
            ar.main(["from-llm", "--agent", "a", "--title", "A", "--in", str(inp), "--out", str(out)])
            self.assertEqual(json.loads(out.read_text())["status"], "ok")


if __name__ == "__main__":
    unittest.main()
