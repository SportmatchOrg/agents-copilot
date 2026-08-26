#!/usr/bin/env python3
"""Fase 7 — Reviewer.

Segunda y última llamada al modelo. Recibe todo: contexto del proyecto, la
skill de review, los criterios QA, la PR, el diff, los hechos determinísticos,
el ticket de Linear y lo que el Scout pidió inspeccionar. Produce `review.json`.

No habla con GitHub. Entre esta salida y GitHub hay un validador determinístico.

Uso:  run-reviewer.py --ctx qa-context --agents-repo <ruta> --target-repo <ruta>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm_client  # noqa: E402
import qa_diff  # noqa: E402
from qa_context import Context  # noqa: E402

MAX_FINDINGS = 5

INSTRUCTIONS = f"""\
Sos el QA PR Review Agent de SportMatch.

Preparás el borrador de una review que después edita y envía un QA humano. Vos
no aprobás, no pedís cambios, no mergeás y no modificás código: solo proponés.

Aplicá la SKILL DE PR REVIEW y los CRITERIOS DE QA que están más abajo. Los
criterios QA-01 … QA-10 son la fuente de verdad, incluidas sus listas de
"NO marcar": respetalas literalmente, están ahí porque cada una es un falso
positivo que ya nos pasó.

REGLAS DE CALIDAD (las más importantes)

1. Máximo {MAX_FINDINGS} findings. Cero es una respuesta válida y frecuente.
   No generes findings para llenar cupo.
2. Comentá SOLO cambios que introduce esta PR. Nunca código preexistente.
3. Evidencia antes que sospecha. Si un criterio pide haber buscado algo en el
   repo (QA-03, QA-06, QA-09), y no lo tenés en el contexto que pediste, no
   generes el finding.
4. UN finding por criterio. Si el mismo criterio aplica en varios lugares
   (dos console.log, tres márgenes, cuatro textos en inglés), generá UN SOLO
   finding: elegí la ocurrencia más representativa, y mencioná en el mensaje
   que el patrón se repite y dónde. Cinco findings del mismo criterio es la
   forma más rápida de que el QA descarte la review entera.
   Con el cupo que te queda libre, priorizá el problema de mayor impacto que
   todavía no comentaste, aunque sea de otro criterio.
5. Si hay findings BLOCKER o MAJOR, no agregues NITs.
6. Los hechos determinísticos ya están calculados: usalos tal cual. No cuentes
   líneas ni busques console.log a ojo.
7. QA-08 NO se revisa nunca: se resuelve con la config del repo.
8. Los mensajes van en español, breves (1–3 frases), concretos y
   constructivos. Los nombres de código quedan en su idioma real. Nada de
   mayúsculas de alarma ni sermones.
9. `positives` tiene que ser real y específico de esta PR. Si no encontrás nada
   genuino, dejá la lista vacía: no inventes elogios.

INLINE vs GLOBAL

- `inline`: el problema está en una línea concreta que la PR agregó. Requiere
  `path` y `line`.
- `global`: no hay una línea única (tamaño de PR, scope, dependencia,
  falta de evidencia visual, observación de arquitectura).

La línea de un finding inline TIENE que estar en la lista de LÍNEAS
COMENTABLES de abajo. Esa lista es exactamente lo que la PR agregó. Si el
problema que ves no cae en ninguna de esas líneas, convertilo en `global`.
NUNCA inventes ni estimes un número de línea: un finding inline en la línea
equivocada es peor que no comentarlo.

SALIDA

Respondé ÚNICAMENTE este objeto JSON, sin markdown ni backticks:

{{
  "version": 1,
  "summary": "2 o 3 frases sobre qué hace la PR.",
  "positives": ["algo concreto y real de esta PR"],
  "findings": [
    {{
      "criterion": "QA-04",
      "severity": "MINOR",
      "kind": "inline",
      "path": "frontend/app/create/page.tsx",
      "line": 83,
      "message": "Quedó un console.log de debugging."
    }},
    {{
      "criterion": "QA-01",
      "severity": "MAJOR",
      "kind": "global",
      "message": "El refactor del mapa no parece formar parte del alcance de SPM-42."
    }}
  ]
}}

`criterion` ∈ QA-01, QA-02, QA-03, QA-04, QA-05, QA-06, QA-07, QA-09, QA-10.
`severity` ∈ BLOCKER, MAJOR, MINOR, NIT.
`kind` ∈ inline, global.
"""


def _ranges(numbers: list[int]) -> str:
    """Compacta [1,2,3,7,8] en '1-3, 7-8' para no gastar contexto."""
    if not numbers:
        return ""
    out, start, prev = [], numbers[0], numbers[0]
    for n in numbers[1:]:
        if n == prev + 1:
            prev = n
            continue
        out.append(f"{start}" if start == prev else f"{start}-{prev}")
        start = prev = n
    out.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ", ".join(out)


def commentable_block(ctx_dir: Path) -> str:
    """Las líneas donde GitHub acepta un comentario inline: las que la PR agregó.

    Dárselas explícitamente al modelo es lo que evita la mayor parte de los
    findings inline inválidos, que el validador tendría que degradar a global.
    """
    patch = (ctx_dir / "diff.patch").read_text(encoding="utf-8", errors="replace")
    files = qa_diff.parse_patch(patch)
    lines = []
    for path, fd in sorted(files.items()):
        if fd.status == "deleted" or not fd.reviewable or fd.is_binary_patch:
            continue
        added = sorted(n for n, _ in fd.added_lines)
        if added:
            lines.append(f"  {path}: {_ranges(added)}")
    return ("=== LÍNEAS COMENTABLES (lado RIGHT) ===\n"
            "Son las líneas que esta PR agregó. Un finding inline solo puede apuntar\n"
            "a una de estas. Cualquier otra línea se rechaza.\n\n"
            + ("\n".join(lines) or "  (ninguna: la PR no agrega líneas revisables)"))


def agent_context_block(ctx_dir: Path) -> str:
    base = ctx_dir / "agent-context"
    try:
        files = json.loads((base / "files.json").read_text(encoding="utf-8"))
        searches = json.loads((base / "searches.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "=== CONTEXTO INSPECCIONADO ===\n(no se inspeccionó nada del repo)"

    parts = ["=== ARCHIVOS DEL REPO QUE PEDISTE ==="]
    if not files:
        parts.append("(ninguno)")
    for f in files:
        if f.get("ok"):
            parts.append(f"\n--- {f['path']} ---\n{f['content']}")
        else:
            parts.append(f"\n--- {f['path']} ---\n[NO DISPONIBLE: {f.get('error')}]")

    parts.append("\n=== RESULTADOS DE LAS BÚSQUEDAS ===")
    if not searches:
        parts.append("(ninguna)")
    for s in searches:
        header = f"\n--- {s['term']!r} ---"
        if not s.get("ok"):
            parts.append(f"{header}\n[falló: {s.get('error')}]")
        elif not s.get("matches"):
            parts.append(f"{header}\nSin coincidencias en el repo.")
        else:
            extra = " (recortado)" if s.get("truncated") else ""
            parts.append(f"{header} {s.get('total')} coincidencias{extra}\n"
                         + "\n".join(s["matches"]))
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--agents-repo", required=True)
    ap.add_argument("--target-repo", required=True)
    args = ap.parse_args()

    ctx_dir = Path(args.ctx)
    ctx = Context(ctx_dir, args.agents_repo, args.target_repo)

    prompt = "\n\n".join([
        INSTRUCTIONS,
        ctx.project_block(),
        ctx.review_block(),
        ctx.pr_block(),
        ctx.facts_block(),
        ctx.linear_block(),
        ctx.diff_block(),
        commentable_block(ctx_dir),
        agent_context_block(ctx_dir),
        f"Recordá: solo el JSON, máximo {MAX_FINDINGS} findings, en español, "
        "y ningún finding inline fuera de las líneas comentables.",
    ])

    (ctx_dir / "reviewer-prompt.txt").write_text(prompt, encoding="utf-8")
    print(f"[reviewer] prompt: {len(prompt)} caracteres", flush=True)

    # temperature=0: dos corridas sobre el mismo HEAD deberían dar la misma
    # review. No lo garantiza (los proveedores de OpenRouter batchean y rutean
    # a distintos backends), pero reduce mucho la variación entre corridas, que
    # en la práctica se manifiesta como findings válidos que se pierden.
    review = llm_client.call_json(prompt, label="reviewer", temperature=0.0)
    (ctx_dir / "review.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    findings = review.get("findings") or []
    print(f"[reviewer] {len(findings)} findings, "
          f"{len(review.get('positives') or [])} positivos")
    for f in findings if isinstance(findings, list) else []:
        if isinstance(f, dict):
            loc = f" {f.get('path')}:{f.get('line')}" if f.get("kind") == "inline" else ""
            print(f"          {f.get('criterion')} · {f.get('severity')} · "
                  f"{f.get('kind')}{loc}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except llm_client.LLMError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
