#!/usr/bin/env python3
"""Fase 8 — Validador de `review.json`.

Capa determinística entre el modelo y GitHub. Nada de lo que el modelo produce
llega a la API sin pasar por acá.

Dos políticas distintas según el tipo de problema:

- **Rechazo del job**: JSON con forma inválida, findings de más, criterio o
  severidad inexistente, workspace modificado, head SHA cambiado. Son señales
  de que algo se rompió, y el plan (§29) pide no rescatar salidas ambiguas.
- **Degradación del finding**: una línea que no pertenece al diff no invalida
  la review entera; ese finding pasa a `global` (plan §15 y §29: "nunca
  adivinar posiciones del diff"). Si tampoco puede ser global, se descarta.

Salida: `validated-review.json`.

Uso:
  validate-review.py --ctx qa-context --target-repo <ruta> --head-sha <sha>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_diff  # noqa: E402

MAX_FINDINGS = 5
MAX_MESSAGE_CHARS = 1200
MAX_SUMMARY_CHARS = 2000
# QA-08 queda deliberadamente afuera: se resuelve con "auto-delete head branches".
VALID_CRITERIA = {"QA-01", "QA-02", "QA-03", "QA-04", "QA-05",
                  "QA-06", "QA-07", "QA-09", "QA-10"}
VALID_SEVERITIES = {"BLOCKER", "MAJOR", "MINOR", "NIT"}
SEVERITY_ORDER = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2, "NIT": 3}


class Rejected(Exception):
    """La review no se publica."""


def check_workspace_clean(repo: Path) -> None:
    """El agente es de solo lectura: si el workspace cambió, algo se salió del carril."""
    r = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise Rejected(f"no se pudo verificar el estado del workspace: {r.stderr.strip()}")
    if r.stdout.strip():
        raise Rejected(
            "el workspace del repo revisado quedó modificado. El agente es de solo "
            f"lectura y no debería tocar archivos:\n{r.stdout.strip()}"
        )


def check_head_sha(repo: Path, expected: str) -> None:
    """El checkout tiene que ser exactamente el head del PR.

    Por defecto `actions/checkout` deja el merge commit (`refs/pull/N/merge`), no
    el head: si eso pasara, el diff y las líneas comentables no se corresponderían
    con lo que GitHub muestra. El workflow pasa `ref: head.sha` justamente para
    evitarlo, y esto lo verifica.

    Que el PR haya recibido commits nuevos DURANTE el análisis se chequea aparte,
    en `create-pending-review.py`, contra la API viva: acá el checkout local nunca
    cambia por sí solo.
    """
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    actual = r.stdout.strip()
    if r.returncode == 0 and actual and actual != expected:
        raise Rejected(
            f"el checkout no está en el head del PR ({expected[:8]} esperado, "
            f"{actual[:8]} encontrado). El diff no sería confiable."
        )


def as_text(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def validate(review: dict, files: dict[str, qa_diff.FileDiff]) -> tuple[dict, list[str]]:
    notes: list[str] = []

    if not isinstance(review, dict):
        raise Rejected("review.json no es un objeto JSON.")

    raw_findings = review.get("findings")
    if raw_findings is None:
        raw_findings = []
    if not isinstance(raw_findings, list):
        raise Rejected("`findings` no es una lista.")
    if len(raw_findings) > MAX_FINDINGS:
        raise Rejected(
            f"el modelo devolvió {len(raw_findings)} findings y el máximo es "
            f"{MAX_FINDINGS}. No se recorta: es señal de que ignoró las reglas."
        )

    summary = as_text(review.get("summary"), MAX_SUMMARY_CHARS)
    if not summary:
        raise Rejected("`summary` vacío: la review no diría nada.")

    positives = [as_text(p, 400) for p in (review.get("positives") or [])
                 if isinstance(p, str) and as_text(p, 400)][:5]

    # Índice de líneas comentables: solo lo que la PR AGREGÓ, del lado RIGHT.
    commentable = {
        path: {n for n, _ in fd.added_lines}
        for path, fd in files.items()
        if fd.status != "deleted" and fd.reviewable and not fd.is_binary_patch
    }

    clean: list[dict] = []
    seen: set[tuple] = set()

    for idx, f in enumerate(raw_findings, start=1):
        where = f"finding #{idx}"
        if not isinstance(f, dict):
            raise Rejected(f"{where} no es un objeto.")

        criterion = str(f.get("criterion") or "").strip().upper()
        if criterion == "QA-08":
            raise Rejected("QA-08 no lo revisa el agente (se resuelve con la "
                           "config del repo). El modelo ignoró la regla.")
        if criterion not in VALID_CRITERIA:
            raise Rejected(f"{where}: criterio desconocido {criterion!r}. "
                           f"Válidos: {', '.join(sorted(VALID_CRITERIA))}.")

        severity = str(f.get("severity") or "").strip().upper()
        if severity not in VALID_SEVERITIES:
            raise Rejected(f"{where}: severidad desconocida {severity!r}.")
        if criterion == "QA-05" and severity in ("BLOCKER", "MAJOR"):
            severity = "NIT"
            notes.append("QA-05 se bajó a NIT: es una recomendación, nunca bloqueante.")

        message = as_text(f.get("message"), MAX_MESSAGE_CHARS)
        if not message:
            raise Rejected(f"{where}: mensaje vacío.")

        kind = str(f.get("kind") or "global").strip().lower()
        path = str(f.get("path") or "").strip().lstrip("/")
        line = f.get("line")

        if kind == "inline":
            reason = None
            if path not in files:
                reason = f"`{path}` no forma parte de esta PR"
            elif path not in commentable:
                reason = f"`{path}` no admite comentarios inline (binario, borrado o no revisable)"
            elif not isinstance(line, int) or isinstance(line, bool):
                reason = f"la línea {line!r} no es un entero"
            elif line not in commentable[path]:
                reason = f"la línea {line} de `{path}` no es una línea agregada por la PR"

            if reason:
                # No se adivina la línea correcta: pasa a global con el contexto adentro.
                notes.append(f"{criterion}: se degradó a global porque {reason}.")
                kind, line = "global", None
                if path:
                    message = f"En `{path}`: {message}"
                path = ""

        if kind != "inline":
            kind, path, line = "global", "", None

        key = (criterion, kind, path, line, message.lower()[:120])
        if key in seen:
            notes.append(f"{criterion}: se descartó un finding duplicado.")
            continue
        seen.add(key)

        entry = {"id": len(clean) + 1, "criterion": criterion, "severity": severity,
                 "kind": kind, "message": message}
        if kind == "inline":
            entry["path"] = path
            entry["line"] = line
        clean.append(entry)

    clean.sort(key=lambda e: (SEVERITY_ORDER[e["severity"]], e["criterion"]))
    for i, e in enumerate(clean, start=1):
        e["id"] = i

    return {"version": 1, "summary": summary, "positives": positives,
            "findings": clean}, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--target-repo", required=True)
    ap.add_argument("--head-sha", required=True)
    ap.add_argument("--skip-workspace-check", action="store_true",
                    help="solo para pruebas locales")
    args = ap.parse_args()

    ctx = Path(args.ctx)
    repo = Path(args.target_repo).resolve()

    try:
        if not args.skip_workspace_check:
            check_workspace_clean(repo)
            check_head_sha(repo, args.head_sha)

        try:
            review = json.loads((ctx / "review.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise Rejected(f"no se pudo leer review.json: {e}") from None

        files = qa_diff.parse_patch(
            (ctx / "diff.patch").read_text(encoding="utf-8", errors="replace"))
        validated, notes = validate(review, files)

    except Rejected as e:
        print(f"❌ Review rechazada: {e}", file=sys.stderr)
        return 1

    (ctx / "validated-review.json").write_text(
        json.dumps(validated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    inline = sum(1 for f in validated["findings"] if f["kind"] == "inline")
    print(f"✅ Review válida: {len(validated['findings'])} findings "
          f"({inline} inline, {len(validated['findings']) - inline} globales), "
          f"{len(validated['positives'])} positivos.")
    for n in notes:
        print(f"   ⚠️  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
