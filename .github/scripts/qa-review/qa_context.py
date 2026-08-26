"""Carga y renderiza el contexto que comparten el Scout y el Reviewer.

Las cuatro capas del plan §21:
  1. proyecto  — AGENTS.md
  2. review    — pr-review/SKILL.md + references/qa-criteria.md
  3. PR        — meta, diff, archivos, hechos determinísticos
  4. negocio   — issue de Linear
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Topes de contexto. Con minimax-m3 (1M) sobra, pero el modelo es una variable:
# si mañana se cambia por uno de 128k, esto evita que el job explote.
MAX_DIFF_CHARS = int(os.environ.get("QA_MAX_DIFF_CHARS", "120000"))
MAX_TREE_LINES = int(os.environ.get("QA_MAX_TREE_LINES", "1200"))
MAX_AGENTS_CHARS = 12000
MAX_BODY_CHARS = 4000


def _read(path: Path, limit: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if limit and len(text) > limit:
        return text[:limit] + f"\n\n[… truncado, {len(text) - limit} caracteres más]"
    return text


class Context:
    def __init__(self, ctx_dir: str | Path, agents_repo: str | Path,
                 target_repo: str | Path):
        self.dir = Path(ctx_dir)
        self.agents_repo = Path(agents_repo)
        self.target_repo = Path(target_repo)

        self.meta = json.loads(_read(self.dir / "meta.json") or "{}")
        self.facts = json.loads(_read(self.dir / "deterministic-facts.json") or "{}")
        self.linear = json.loads(_read(self.dir / "linear-issue.json") or "{}")
        self.files = json.loads(_read(self.dir / "files.json") or "[]")

    # --- capa 1: proyecto ---------------------------------------------------
    def project_block(self) -> str:
        agents = _read(self.target_repo / "AGENTS.md", MAX_AGENTS_CHARS) \
            or _read(self.agents_repo / "AGENTS.md", MAX_AGENTS_CHARS)
        return f"=== CONTEXTO DEL PROYECTO (AGENTS.md) ===\n{agents}"

    # --- capa 2: review -----------------------------------------------------
    def review_block(self) -> str:
        base = self.agents_repo / "github" / "skills" / "pr-review"
        skill = _read(base / "SKILL.md")
        criteria = _read(base / "references" / "qa-criteria.md")
        if not skill or not criteria:
            raise SystemExit(
                f"No encuentro la skill de review en {base}. "
                "¿Se hizo checkout de agents-copilot?"
            )
        return (f"=== SKILL DE PR REVIEW ===\n{skill}\n\n"
                f"=== CRITERIOS DE QA (QA-01 … QA-10) ===\n{criteria}")

    # --- capa 3: PR ---------------------------------------------------------
    def pr_block(self) -> str:
        m = self.meta
        body = (m.get("body") or "(sin descripción)")[:MAX_BODY_CHARS]
        files = "\n".join(
            f"  {f['status']:9} +{f['additions']:<5} -{f['deletions']:<5} "
            f"{f['path']}{'' if f.get('reviewable', True) else '   [no revisable]'}"
            for f in self.facts.get("changedFiles", [])
        ) or "(sin archivos)"
        return (
            "=== PULL REQUEST ===\n"
            f"#{m.get('number')} — {m.get('title')}\n"
            f"Rama:  {m.get('headRefName')} → {m.get('baseRefName')}\n"
            f"Head:  {m.get('headRefOid')}\n"
            f"Autor: {(m.get('author') or {}).get('login', '?')}\n\n"
            f"Descripción:\n{body}\n\n"
            f"Archivos cambiados:\n{files}"
        )

    def facts_block(self) -> str:
        return ("=== HECHOS DETERMINÍSTICOS ===\n"
                "Calculados por código, no por vos. Son evidencia verificada: usalos tal cual\n"
                "y no recalcules líneas ni busques console.log a ojo en el diff.\n\n"
                + json.dumps(self.facts, indent=2, ensure_ascii=False))

    def diff_block(self) -> str:
        return ("=== DIFF DE LA PR (merge-base → head) ===\n"
                + _read(self.dir / "diff.patch", MAX_DIFF_CHARS))

    def tree_block(self) -> str:
        lines = _read(self.dir / "repo-tree.txt").splitlines()
        shown = lines[:MAX_TREE_LINES]
        extra = f"\n[… {len(lines) - len(shown)} archivos más]" if len(lines) > len(shown) else ""
        return ("=== ESTRUCTURA DEL REPOSITORIO (archivos versionados) ===\n"
                + "\n".join(shown) + extra)

    # --- capa 4: negocio ----------------------------------------------------
    def linear_block(self) -> str:
        if not self.linear.get("id"):
            return (
                "=== TICKET DE LINEAR ===\n"
                "No disponible (la rama no referencia ningún ticket, o no se pudo "
                "consultar Linear).\n\n"
                "Consecuencias:\n"
                "- QA-05 (evidencia visual): NO lo evalúes. Sin poder mirar el ticket, "
                "que falte una captura es desconocido, no falso.\n"
                "- QA-01 (scope): solo podés compararlo contra el TÍTULO y la "
                "DESCRIPCIÓN de la PR. Si lo hacés, el mensaje tiene que decir "
                "explícitamente que la base es el título de la PR y no el ticket "
                "(ej. \"el título anuncia X pero la PR también trae Y\").\n"
                "- Nunca inventes el contenido del ticket ni cites un identificador "
                "como si lo hubieras leído.")
        i = self.linear
        comments = "\n".join(
            f"  - {(c.get('user') or {}).get('name', '?')}: {(c.get('body') or '')[:400]}"
            for c in (i.get("comments") or {}).get("nodes", [])[:15]
        ) or "  (sin comentarios)"
        attachments = "\n".join(
            f"  - {a.get('title') or ''} {a.get('url') or ''}"
            for a in (i.get("attachments") or {}).get("nodes", [])[:15]
        ) or "  (sin attachments)"
        return (
            "=== TICKET DE LINEAR ===\n"
            f"{i.get('identifier')} — {i.get('title')}\n"
            f"Estado: {(i.get('state') or {}).get('name', '?')}\n"
            f"Tiene evidencia visual (screenshots/videos): {i.get('hasVisualEvidence')}\n\n"
            f"Descripción:\n{(i.get('description') or '(vacía)')[:6000]}\n\n"
            f"Comentarios:\n{comments}\n\n"
            f"Attachments:\n{attachments}"
        )

    def base_blocks(self) -> list[str]:
        return [self.project_block(), self.review_block(), self.pr_block(),
                self.facts_block(), self.linear_block(), self.diff_block()]
