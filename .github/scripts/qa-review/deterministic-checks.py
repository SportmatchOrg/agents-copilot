#!/usr/bin/env python3
"""Fase 2 — Checks determinísticos del QA PR Review Agent.

Resuelve sin LLM la parte de los criterios QA que es puramente mecánica, para
que el modelo reciba hechos en vez de tener que buscarlos: cuántas líneas
revisables tiene la PR (QA-01), qué dependencias nuevas aparecieron (QA-03),
dónde quedó debugging (QA-04), qué márgenes se agregaron (QA-09), qué assets
pesados se versionaron (QA-07) y si el cambio es probablemente visual (QA-05).

Menos tokens, más consistencia, y reglas simples que no dependen del modelo.

Uso:
  deterministic-checks.py --patch diff.patch --repo <ruta> \
      --base-sha <sha> --head-sha <sha> --out deterministic-facts.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_diff  # noqa: E402

# Configurables por entorno: el plan (§QA-07) pide explícitamente no hardcodear el límite.
PR_SIZE_LIMIT = int(os.environ.get("QA_PR_SIZE_LIMIT", "1000"))
MAX_ASSET_BYTES = int(os.environ.get("QA_MAX_ASSET_BYTES", str(500 * 1024)))

# --- QA-04: debugging -------------------------------------------------------
# console.error/warn quedan afuera a propósito: son manejo de errores, no debugging.
DEBUG_RE = re.compile(
    r"\b(console\s*\.\s*(log|debug|dir|table|trace|time|timeEnd)|debugger)\b"
)
DEBUG_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"}

# --- QA-09: márgenes --------------------------------------------------------
# Tailwind: m-4, mt-2, mx-6, -mb-1, md:mt-4, hover:ml-2.
# mx-auto se excluye: es el idiom de centrado, no spacing.
TW_MARGIN_RE = re.compile(r"(?<![\w-])(-?m[trblxyse]?)-(\[[^\]]+\]|[\w.\/]+)")
CSS_MARGIN_RE = re.compile(r"(?<![\w-])margin(-(top|right|bottom|left|block|inline))?\s*:")
MARGIN_EXTS = {".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ".sass", ".less",
               ".html", ".vue", ".svelte"}
MARGIN_ALLOWED = {"mx-auto", "m-auto", "m-0", "mx-0", "my-0"}

# --- QA-05: cambio visual ---------------------------------------------------
VISUAL_EXTS = {".tsx", ".jsx", ".css", ".scss", ".sass", ".less", ".vue", ".svelte", ".html"}
VISUAL_DIR_RE = re.compile(
    r"(^|/)(components?|pages?|app|views?|screens?|layouts?|styles?|ui|public|assets)(/|$)", re.I
)

DEP_KINDS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")


def git(repo: Path, *args: str) -> str | None:
    """Corre git en el repo destino. Devuelve None si falla (no rompe el check)."""
    try:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def deps_at(repo: Path, sha: str, path: str) -> dict[str, str] | None:
    """Dependencias declaradas en un package.json, en un commit dado."""
    raw = git(repo, "show", f"{sha}:{path}")
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    out: dict[str, str] = {}
    for kind in DEP_KINDS:
        block = data.get(kind)
        if isinstance(block, dict):
            for name, version in block.items():
                out[name] = f"{kind}:{version}"
    return out


def check_dependencies(repo: Path, base_sha: str, head_sha: str,
                       files: dict[str, qa_diff.FileDiff]) -> tuple[list, list, list]:
    """QA-03. Compara el package.json de base contra el de head, en vez de
    adivinar desde el diff: un `"lodash": "^4"` agregado dentro de un bloque
    `overrides` o `resolutions` no es una dependencia nueva."""
    added, removed, warnings = [], [], []
    manifests = [p for p in files if p.split("/")[-1] == "package.json"
                 and not qa_diff.is_generated(p)]

    for manifest in manifests:
        fd = files[manifest]
        head = deps_at(repo, head_sha, manifest) if fd.status != "deleted" else {}
        base = deps_at(repo, base_sha, manifest) if fd.status != "added" else {}
        if head is None or base is None:
            warnings.append(
                f"No se pudo comparar {manifest} entre {base_sha[:7]} y {head_sha[:7]}; "
                "QA-03 queda sin evidencia para este manifest."
            )
            continue
        for name, meta in head.items():
            if name not in base:
                kind, _, version = meta.partition(":")
                added.append({"name": name, "version": version,
                              "kind": kind, "manifest": manifest})
        for name in base:
            if name not in head:
                removed.append({"name": name, "manifest": manifest})

    return added, removed, warnings


def check_debug(files: dict[str, qa_diff.FileDiff]) -> list[dict]:
    """QA-04. Solo líneas agregadas, solo código de producción."""
    out = []
    for path, fd in files.items():
        if fd.status == "deleted" or not fd.reviewable:
            continue
        if qa_diff.ext_of(path) not in DEBUG_EXTS or qa_diff.is_test_path(path):
            continue
        for line_no, content in fd.added_lines:
            if not qa_diff.strip_code_comment(content):
                continue  # la línea es un comentario: no es debugging activo
            m = DEBUG_RE.search(content)
            if m:
                out.append({
                    "path": path, "line": line_no,
                    "type": m.group(0).replace(" ", ""),
                    "snippet": content.strip()[:160],
                })
    return out


def check_margins(files: dict[str, qa_diff.FileDiff]) -> list[dict]:
    """QA-09 parte B. Solo márgenes agregados."""
    out = []
    for path, fd in files.items():
        if fd.status == "deleted" or not fd.reviewable:
            continue
        if qa_diff.ext_of(path) not in MARGIN_EXTS or qa_diff.is_test_path(path):
            continue
        for line_no, content in fd.added_lines:
            if not qa_diff.strip_code_comment(content):
                continue
            hits = {f"{m.group(1)}-{m.group(2)}" for m in TW_MARGIN_RE.finditer(content)}
            hits -= MARGIN_ALLOWED
            if CSS_MARGIN_RE.search(content):
                hits.add(CSS_MARGIN_RE.search(content).group(0).strip())
            for hit in sorted(hits):
                out.append({"path": path, "line": line_no, "match": hit,
                            "snippet": content.strip()[:160]})
    return out


def check_assets(repo: Path, files: dict[str, qa_diff.FileDiff]) -> list[dict]:
    """QA-07. Solo archivos NUEVOS: si ya estaba versionado, esta PR no lo introdujo."""
    out = []
    for path, fd in files.items():
        if fd.status not in ("added", "renamed"):
            continue
        full = repo / path
        try:
            size = full.stat().st_size
        except OSError:
            continue
        generated = qa_diff.is_generated(path) and not qa_diff.is_lockfile(path)
        if size > MAX_ASSET_BYTES or (qa_diff.is_binary(path) and size > MAX_ASSET_BYTES) or generated:
            out.append({
                "path": path,
                "bytes": size,
                "human": f"{size / 1024:.0f} KB" if size < 1024 * 1024 else f"{size / 1048576:.1f} MB",
                "reason": "generado o de build" if generated else "supera QA_MAX_ASSET_BYTES",
            })
    return out


def check_visual(files: dict[str, qa_diff.FileDiff]) -> tuple[bool, list[str]]:
    """QA-05. Heurística: ¿es probable que esta PR cambie algo que el usuario ve?"""
    reasons = []
    for path, fd in files.items():
        if fd.status == "deleted" or not fd.reviewable or qa_diff.is_test_path(path):
            continue
        ext = qa_diff.ext_of(path)
        if ext in VISUAL_EXTS:
            reasons.append(path)
        elif ext in {".ts", ".js"} and VISUAL_DIR_RE.search(path):
            reasons.append(path)
        elif qa_diff.is_binary(path) and VISUAL_DIR_RE.search(path):
            reasons.append(path)
    return bool(reasons), sorted(set(reasons))[:20]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--head-sha", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    patch_text = Path(args.patch).read_text(encoding="utf-8", errors="replace")
    files = qa_diff.parse_patch(patch_text)

    reviewable = qa_diff.reviewable_changed_lines(files)
    total = sum(f.additions + f.deletions for f in files.values())
    new_deps, removed_deps, dep_warnings = check_dependencies(
        repo, args.base_sha, args.head_sha, files)
    visual, visual_files = check_visual(files)

    facts = {
        "prSizeLimit": PR_SIZE_LIMIT,
        "maxAssetBytes": MAX_ASSET_BYTES,
        "totalChangedLines": total,
        "reviewableChangedLines": reviewable,
        "exceedsPrSizeLimit": reviewable > PR_SIZE_LIMIT,
        "excludedFromSize": sorted(
            ({"path": p, "lines": f.additions + f.deletions}
             for p, f in files.items() if not f.reviewable),
            key=lambda e: -e["lines"],
        )[:20],
        "changedFiles": [
            {"path": p, "status": f.status, "additions": f.additions,
             "deletions": f.deletions, "reviewable": f.reviewable}
            for p, f in sorted(files.items())
        ],
        "newDependencies": new_deps,
        "removedDependencies": removed_deps,
        "debugStatements": check_debug(files),
        "marginUsages": check_margins(files),
        "largeAssets": check_assets(repo, files),
        "visualChangeLikely": visual,
        "visualChangeFiles": visual_files,
        "warnings": dep_warnings,
        # Diff vacío: PR ya mergeada, rama sin cambios contra su base, o todo el
        # cambio es no revisable (lockfiles, generados). Llamar al modelo acá es
        # gastar cuota para que responda sobre la nada.
        "nothingToReview": reviewable == 0,
    }

    Path(args.out).write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    print(f"Archivos cambiados:   {len(files)}")
    print(f"Líneas revisables:    {reviewable} (total {total}, límite {PR_SIZE_LIMIT})")
    print(f"Dependencias nuevas:  {len(new_deps)}")
    print(f"Debugging:            {len(facts['debugStatements'])}")
    print(f"Márgenes:             {len(facts['marginUsages'])}")
    print(f"Assets pesados:       {len(facts['largeAssets'])}")
    print(f"Cambio visual:        {visual}")
    for w in dep_warnings:
        print(f"⚠️  {w}")

    if facts["nothingToReview"]:
        print("⏭️  No hay líneas revisables en esta PR (¿ya está mergeada, o el "
              "cambio es todo lockfiles/generados?). No se llama al modelo.")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"has_changes={'false' if facts['nothingToReview'] else 'true'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
