#!/usr/bin/env python3
"""Mapa de endpoints del back, sacado de los controllers de Nest sin modelo.

Es la entrada de todo lo demás: `baseline.py` le pega a cada endpoint, y el
agente lo recibe precargado para no gastar turnos descubriendo rutas.

Se parsea con regex y no con un AST de TypeScript porque los controllers de
SportMatch siguen un molde fijo (AGENTS.md: controller + service + repository).
Si un controller se sale del molde, el endpoint aparece igual pero con menos
datos, y `baseline.py` lo trata como el caso más desconfiado.

Uso:  endpoints.py --repo <ruta> --out <archivo.json>
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

SERVICE_ROOT = os.environ.get("SERVICE_ROOT", "back").strip("/")

HTTP_RE = re.compile(r"^\s*@(Get|Post|Put|Patch|Delete)\(\s*(?:['\"`]([^'\"`]*)['\"`])?\s*\)", re.M)
CONTROLLER_RE = re.compile(r"@Controller\(\s*(?:['\"`]([^'\"`]*)['\"`])?\s*\)")
GUARDS_RE = re.compile(r"@UseGuards\(([^)]*)\)")
CLASS_RE = re.compile(r"^export\s+class\s+\w+", re.M)
METHOD_RE = re.compile(r"^\s*(?:async\s+)?([A-Za-z_]\w*)\s*\(", re.M)
BODY_RE = re.compile(r"@Body\(\s*\)\s*(\w+)\s*:\s*([\w<>\[\], ]+?)\s*[,)]")


def _join(prefix: str, sub: str) -> str:
    parts = [p for p in (prefix.strip("/"), sub.strip("/")) if p]
    return "/" + "/".join(parts)


def _guards(text: str) -> list[str]:
    out: list[str] = []
    for m in GUARDS_RE.finditer(text):
        out += [g.strip() for g in m.group(1).split(",") if g.strip()]
    return out


def parse_controller(path: Path, rel: str) -> list[dict]:
    src = path.read_text(encoding="utf-8")
    ctrl = CONTROLLER_RE.search(src)
    klass = CLASS_RE.search(src)
    if not ctrl or not klass:
        return []
    prefix = ctrl.group(1) or ""
    # Decoradores de clase: los que están antes de `export class`.
    class_guards = _guards(src[:klass.start()])

    body = src[klass.end():]
    offset = klass.end()
    hits = list(HTTP_RE.finditer(body))
    endpoints = []
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(body)
        block = body[m.start():end]
        # El nombre del método es la primera línea que parece una firma y no
        # un decorador.
        name = None
        for mm in METHOD_RE.finditer(block):
            if not block[:mm.start()].rstrip().endswith("@"):
                line = block[block.rfind("\n", 0, mm.start()) + 1:mm.end()]
                if "@" not in line:
                    name = mm.group(1)
                    break
        signature = block
        body_param = BODY_RE.search(signature)
        line_no = src.count("\n", 0, offset + m.start()) + 1
        endpoints.append({
            "method": m.group(1).upper(),
            "path": _join(prefix, m.group(2) or ""),
            "handler": name,
            "file": rel,
            "line": line_no,
            "guards": class_guards + _guards(block),
            "body": ({"param": body_param.group(1), "type": body_param.group(2).strip()}
                     if body_param else None),
        })
    return endpoints


def collect(repo: Path) -> list[dict]:
    src = repo / SERVICE_ROOT / "src"
    out: list[dict] = []
    for path in sorted(src.rglob("*.controller.ts")):
        if "generated" in path.parts:
            continue
        out += parse_controller(path, str(path.relative_to(repo)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    endpoints = collect(Path(args.repo))
    Path(args.out).write_text(json.dumps(endpoints, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    print(f"{len(endpoints)} endpoints en {len({e['file'] for e in endpoints})} controllers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
