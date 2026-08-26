#!/usr/bin/env python3
"""Fase 5 — Scout.

Primera de las dos llamadas al modelo. El Scout NO revisa: solo decide qué
necesita mirar del repositorio para poder revisar bien. Existe porque varios
criterios (QA-03, QA-06, QA-09) exigen evidencia del repo, y mandarle el repo
entero al modelo no es viable ni barato.

El modelo no toca el filesystem: solo pide, y `resolve-context.py` lee.

Uso:  run-scout.py --ctx qa-context --agents-repo <ruta> --target-repo <ruta>
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

MAX_FILES = 12
MAX_SEARCHES = 10

INSTRUCTIONS = f"""\
Sos el paso de RECONOCIMIENTO del QA PR Review Agent de SportMatch.

NO estás revisando la PR todavía. Tu única tarea es responder:
¿qué necesito leer del repositorio para poder revisar bien esta PR?

Otro proceso va a leer los archivos que pidas y ejecutar las búsquedas que
indiques, y recién después se hace la review. No tenés acceso al filesystem.

Pedí solo lo que realmente te falta para aplicar los criterios QA. En
particular, pedí evidencia cuando un criterio la exige:

- QA-03: si `newDependencies` no está vacío, buscá TODOS los usos de cada
  dependencia nueva. Sin ver los usos no se puede afirmar que sea innecesaria.
- QA-09: si la PR crea un componente nuevo, buscá componentes existentes que
  puedan cubrir el mismo caso (mirá la estructura del repo). Sin encontrar el
  componente equivalente no se puede sugerir reutilizar nada.
- QA-06: si ves un valor que parece de configuración, buscá si el repo ya lo
  centraliza en alguna constante o variable de entorno.
- QA-10: si dudás de si un término en español es convención del equipo, buscalo
  para ver si ya aparece en el resto del repo.

Reglas:
- Como máximo {MAX_FILES} archivos y {MAX_SEARCHES} búsquedas. Menos es mejor.
- Los archivos van con su ruta exacta tal como aparece en la estructura del
  repositorio. No inventes rutas.
- NO pidas archivos que ya están completos en el diff: ya los tenés enteros y
  pedirlos no agrega nada. Abajo está la lista exacta de cuáles son. Si pedís
  uno de esos, se descarta.
- Un archivo MODIFICADO sí puede valer la pena: del diff solo ves los hunks, no
  el archivo entero.
- Las búsquedas son de texto plano o regex simple (se ejecutan con ripgrep):
  un identificador, un nombre de componente, un import. No frases.
- Si el diff se explica solo y no necesitás nada, devolvé listas vacías. Es una
  respuesta válida.

Respondé ÚNICAMENTE este objeto JSON, sin markdown ni backticks:

{{
  "reasoning": "una o dos frases sobre qué estás tratando de verificar",
  "filesToRead": ["ruta/exacta/desde/la/raiz.tsx"],
  "searches": ["Button", "NEXT_PUBLIC_API_URL"]
}}
"""


def fully_in_diff(ctx_dir: Path) -> set[str]:
    """Archivos NUEVOS: el diff ya trae su contenido completo.

    Pedirlos gasta contexto sin aportar nada, y en la práctica los modelos lo
    hacen igual aunque el prompt lo prohíba. Por eso se filtra en código.
    """
    patch = (ctx_dir / "diff.patch").read_text(encoding="utf-8", errors="replace")
    return {path for path, fd in qa_diff.parse_patch(patch).items()
            if fd.status == "added" and not fd.is_binary_patch}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--agents-repo", required=True)
    ap.add_argument("--target-repo", required=True)
    args = ap.parse_args()

    ctx_dir = Path(args.ctx)
    ctx = Context(args.ctx, args.agents_repo, args.target_repo)
    already = fully_in_diff(ctx_dir)
    already_block = (
        "=== ARCHIVOS QUE YA TENÉS COMPLETOS EN EL DIFF ===\n"
        "Son nuevos, así que el diff trae todo su contenido. Pedirlos se descarta.\n\n"
        + ("\n".join(f"  {p}" for p in sorted(already)) or "  (ninguno)"))

    prompt = "\n\n".join([
        INSTRUCTIONS,
        ctx.pr_block(),
        already_block,
        ctx.facts_block(),
        ctx.linear_block(),
        ctx.tree_block(),
        ctx.diff_block(),
        "Recordá: respondé solo el JSON con reasoning, filesToRead y searches.",
    ])

    Path(args.ctx, "scout-prompt.txt").write_text(prompt, encoding="utf-8")
    print(f"[scout] prompt: {len(prompt)} caracteres", flush=True)

    raw = llm_client.call_json(prompt, label="scout")

    def clean(key: str, limit: int) -> list[str]:
        value = raw.get(key) or []
        if not isinstance(value, list):
            return []
        out, seen = [], set()
        for item in value:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out[:limit]

    requested = clean("filesToRead", MAX_FILES)
    dropped = [f for f in requested if f.lstrip("/") in already]
    scout = {
        "reasoning": str(raw.get("reasoning") or "")[:500],
        "filesToRead": [f for f in requested if f.lstrip("/") not in already],
        "searches": clean("searches", MAX_SEARCHES),
    }
    for f in dropped:
        print(f"[scout] ↩︎  descarto {f}: ya viene completo en el diff")

    Path(args.ctx, "scout.json").write_text(
        json.dumps(scout, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"[scout] {scout['reasoning']}")
    print(f"[scout] pide {len(scout['filesToRead'])} archivos y "
          f"{len(scout['searches'])} búsquedas")
    for f in scout["filesToRead"]:
        print(f"          archivo: {f}")
    for s in scout["searches"]:
        print(f"          búsqueda: {s}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except llm_client.LLMError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
