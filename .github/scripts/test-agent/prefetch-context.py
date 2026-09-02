#!/usr/bin/env python3
"""Precarga determinística de contexto (plan §5.3).

Con 5 iteraciones el agente NO puede gastar turnos descubriendo el repo: si usa
tres en `list_dir` y `read_file`, no le queda presupuesto para escribir, correr
y corregir — que es lo único que justifica tener un agente.

Entonces esto corre ANTES del loop, sin modelo de por medio, y le deja servido:
el módulo del RF completo, el schema de Prisma, el harness y el spec de ejemplo.

El mapeo RF → módulo es un dict estático a propósito: resolverlo con el modelo
costaría una llamada y agregaría una forma de fallar.

Uso:  prefetch-context.py --ctx <dir> --repo <ruta> --ticket SPM-42
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SERVICE_ROOT = os.environ.get("SERVICE_ROOT", "back").strip("/")

# Plan §3.7: agregar un módulo es una línea acá, no un cambio de código.
RF_MODULES = {
    "RF-02": f"{SERVICE_ROOT}/src/users",
    "RF-03": f"{SERVICE_ROOT}/src/partidos",
}
DEFAULT_RF = "RF-03"

HARNESS_FILES = [
    f"{SERVICE_ROOT}/test/setup-e2e.ts",
    f"{SERVICE_ROOT}/test/fixtures.ts",
]
EXAMPLE_SPEC = f"{SERVICE_ROOT}/test/partidos.example.e2e-spec.ts"
SCHEMA = f"{SERVICE_ROOT}/prisma/schema.prisma"

# Los tickets traen una guía de implementación numerada ANTES de los AC.
# Sin recortar a la sección, esa guía se cuela como si fueran criterios: en
# SPO-168 se comía los 12 lugares y no entraba un solo AC real.
AC_HEADING_RE = re.compile(
    r"^[ \t]*#*[ \t]*\**[ \t]*criterios de aceptaci[oó]n[ \t]*\**[ \t]*:?[ \t]*$",
    re.I | re.M)
# El `[ ]` del checkbox no es parte del criterio.
AC_LINE_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(?:\[[ xX]\]\s*)?(.{6,})$")


def read(repo: Path, rel: str, limit: int = 20_000) -> str | None:
    path = repo / rel
    if not path.is_file():
        return None
    return path.read_bytes()[:limit].decode("utf-8", "replace")


def module_block(repo: Path, module_rel: str) -> str:
    base = repo / module_rel
    if not base.is_dir():
        return f"=== MÓDULO {module_rel} ===\n(no existe)"
    parts = [f"=== MÓDULO {module_rel} (completo) ==="]
    for file in sorted(base.rglob("*.ts")):
        rel = file.relative_to(repo).as_posix()
        parts.append(f"\n--- {rel} ---\n{read(repo, rel)}")
    return "\n".join(parts)


def acceptance_criteria(description: str) -> list[str]:
    """Extrae los AC del ticket como lista numerada.

    Si el ticket los trae en prosa no hay nada que numerar: se devuelve vacío y
    el agente trabaja sobre la descripción cruda. Es una limitación conocida
    (plan §14.2), no un fallo silencioso: queda registrada en el contexto.
    """
    text = description or ""
    heading = AC_HEADING_RE.search(text)
    if heading:
        text = text[heading.end():]
    out = []
    for line in text.splitlines():
        match = AC_LINE_RE.match(line)
        if match:
            out.append(match.group(1).strip())
    return out[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ticket", required=True)
    ap.add_argument("--rf", default="")
    args = ap.parse_args()

    ctx_dir = Path(args.ctx)
    ctx_dir.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo).resolve()

    linear_path = ctx_dir / "linear.json"
    ticket_data = {}
    if linear_path.is_file():
        try:
            ticket_data = json.loads(linear_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            ticket_data = {}

    title = ticket_data.get("title") or "(sin título)"
    description = ticket_data.get("description") or ""
    criteria = acceptance_criteria(description)

    rf = (args.rf or "").upper()
    if rf not in RF_MODULES:
        found = re.search(r"RF-\d{2}", f"{title}\n{description}")
        rf = found.group(0) if found and found.group(0) in RF_MODULES else DEFAULT_RF
    module_rel = RF_MODULES[rf]
    print(f"[prefetch] ticket {args.ticket} · {rf} → {module_rel}", flush=True)

    ac_block = "\n".join(f"  AC-{i}: {c}" for i, c in enumerate(criteria, 1)) or \
        "  (el ticket no trae los AC como lista; usá la descripción de arriba y " \
        "numerá vos los casos como AC-1, AC-2, ...)"

    blocks = [
        f"=== TICKET {args.ticket} ===\nTítulo: {title}\n\n{description.strip()}",
        f"=== CRITERIOS DE ACEPTACIÓN (usá estos identificadores) ===\n{ac_block}",
        module_block(repo, module_rel),
        f"=== {SCHEMA} ===\n{read(repo, SCHEMA) or '(no encontrado)'}",
    ]
    for rel in HARNESS_FILES:
        content = read(repo, rel)
        if content:
            blocks.append(f"=== HARNESS (NO SE MODIFICA) — {rel} ===\n{content}")
    example = read(repo, EXAMPLE_SPEC)
    if example:
        blocks.append(
            f"=== SPEC DE EJEMPLO — {EXAMPLE_SPEC} ===\n"
            f"Referencia de estilo. Está verde. NO lo modifiques: escribí uno "
            f"nuevo con otro nombre.\n\n{example}")

    (ctx_dir / "context.json").write_text(
        json.dumps({"ticket": args.ticket, "rf": rf, "module": module_rel,
                    "title": title, "criteria": criteria, "blocks": blocks},
                   indent=2, ensure_ascii=False), encoding="utf-8")

    total = sum(len(b) for b in blocks)
    print(f"[prefetch] {len(blocks)} bloques, {total} caracteres, "
          f"{len(criteria)} AC detectados", flush=True)
    if not criteria:
        print("::warning title=AC sin numerar::El ticket no trae los criterios "
              "como lista; la cobertura va a ser menos precisa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
