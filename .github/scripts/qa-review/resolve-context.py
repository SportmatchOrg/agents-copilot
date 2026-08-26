#!/usr/bin/env python3
"""Fase 6 — Context resolver.

Ejecuta lo que pidió el Scout: lee archivos y corre búsquedas sobre el repo
revisado. Es la única superficie por la que el modelo "toca" el repositorio, y
es deliberadamente de solo lectura: no hay write, edit, commit, push ni delete.

Todo lo que llega en `scout.json` viene de un LLM, así que se trata como input
no confiable: las rutas se resuelven contra la raíz del repo y se rechaza
cualquiera que se escape (`..`, rutas absolutas, symlinks que salgan del repo),
y las búsquedas se pasan como argumento a ripgrep sin shell de por medio.

Uso:  resolve-context.py --ctx qa-context --target-repo <ruta>
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

MAX_FILE_BYTES = 40_000        # por archivo pedido
MAX_MATCHES_PER_SEARCH = 40
SEARCH_TIMEOUT = 30

EXCLUDE_GLOBS = [
    "!node_modules/**", "!dist/**", "!build/**", "!.next/**", "!out/**",
    "!coverage/**", "!vendor/**", "!.git/**", "!*.lock", "!package-lock.json",
    "!pnpm-lock.yaml", "!yarn.lock",
]


def safe_resolve(repo: Path, rel: str) -> Path | None:
    """Resuelve `rel` dentro de `repo`, o None si se escapa o no es un archivo."""
    rel = rel.strip().lstrip("/")
    if not rel or "\x00" in rel:
        return None
    try:
        target = (repo / rel).resolve()
        target.relative_to(repo)          # falla si quedó fuera del repo
    except (ValueError, OSError):
        return None
    return target if target.is_file() else None


def read_files(repo: Path, wanted: list[str], out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for rel in wanted:
        target = safe_resolve(repo, rel)
        if target is None:
            results.append({"path": rel, "ok": False,
                            "error": "no existe, no es un archivo, o queda fuera del repo"})
            print(f"[resolve] ✗ {rel} — no disponible")
            continue
        raw = target.read_bytes()[:MAX_FILE_BYTES]
        text = raw.decode("utf-8", "replace")
        truncated = target.stat().st_size > MAX_FILE_BYTES
        if truncated:
            text += f"\n\n[… truncado a {MAX_FILE_BYTES} bytes]"
        # Se guarda plano, con la ruta en el nombre, para poder inspeccionarlo
        # desde los artifacts del job cuando algo sale mal.
        (out_dir / rel.replace("/", "__")).write_text(text, encoding="utf-8")
        results.append({"path": rel, "ok": True, "bytes": len(raw),
                        "truncated": truncated, "content": text})
        print(f"[resolve] ✓ {rel} ({len(raw)} bytes)")
    return results


def run_search(repo: Path, term: str, engine: str) -> dict:
    if engine == "rg":
        cmd = ["rg", "--no-heading", "--line-number", "--color", "never",
               "--max-count", "5", "--max-columns", "200",
               "-e", term, "."]
        for g in EXCLUDE_GLOBS:
            cmd[len(cmd) - 1:len(cmd) - 1] = ["--glob", g]
    else:
        cmd = ["grep", "-rnI", "--max-count=5",
               "--exclude-dir=node_modules", "--exclude-dir=dist",
               "--exclude-dir=build", "--exclude-dir=.next", "--exclude-dir=out",
               "--exclude-dir=coverage", "--exclude-dir=vendor", "--exclude-dir=.git",
               "-e", term, "."]
    try:
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True,
                           timeout=SEARCH_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as e:
        return {"term": term, "ok": False, "error": str(e)[:200], "matches": []}

    lines = [ln[2:] if ln.startswith("./") else ln
             for ln in r.stdout.splitlines() if ln.strip()]
    truncated = len(lines) > MAX_MATCHES_PER_SEARCH
    print(f"[resolve] 🔍 {term!r}: {len(lines)} coincidencias")
    return {"term": term, "ok": True, "total": len(lines), "truncated": truncated,
            "matches": lines[:MAX_MATCHES_PER_SEARCH]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--target-repo", required=True)
    args = ap.parse_args()

    ctx = Path(args.ctx)
    repo = Path(args.target_repo).resolve()
    scout = json.loads((ctx / "scout.json").read_text(encoding="utf-8"))

    agent_ctx = ctx / "agent-context"
    files = read_files(repo, scout.get("filesToRead", []), agent_ctx / "files")

    engine = "rg" if shutil.which("rg") else "grep"
    if engine == "grep":
        print("[resolve] ripgrep no está disponible; uso grep.")
    searches = [run_search(repo, t, engine) for t in scout.get("searches", [])]

    (agent_ctx / "files.json").write_text(
        json.dumps(files, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (agent_ctx / "searches.json").write_text(
        json.dumps(searches, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ok = sum(1 for f in files if f["ok"])
    print(f"[resolve] {ok}/{len(files)} archivos leídos, {len(searches)} búsquedas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
