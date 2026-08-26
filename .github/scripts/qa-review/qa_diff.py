"""Parser de diff unificado compartido por los scripts de qa-review.

Existe para que los checks determinísticos y el validador de la review usen
exactamente el mismo criterio sobre qué línea "pertenece a la PR". Si cada uno
parseara el diff a su manera, el validador podría rechazar un finding que el
check acaba de generar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Archivos que cuentan en el diff pero NO cuentan como "código revisable" (QA-01),
# ni se inspeccionan por debugging/márgenes/idioma.
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "poetry.lock", "Pipfile.lock", "Gemfile.lock", "composer.lock", "Cargo.lock",
    "go.sum", "bun.lockb",
}

GENERATED_DIR_PARTS = {
    "node_modules", "dist", "build", ".next", "out", "coverage", "vendor",
    ".turbo", ".cache", "__snapshots__", "generated", ".venv",
}

GENERATED_NAME_RE = re.compile(
    r"(\.min\.(js|css)|\.generated\.[^.]+|\.snap|\.map|\.d\.ts)$", re.I
)

BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".ico", ".bmp", ".tiff",
    ".mp4", ".webm", ".mov", ".avi", ".mp3", ".wav", ".ogg",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".psd", ".ai", ".sketch", ".fig", ".lockb", ".db", ".sqlite", ".dump",
}

CODE_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".css", ".scss",
    ".sass", ".less", ".html", ".vue", ".svelte", ".json", ".yml", ".yaml",
    ".sql", ".prisma", ".sh", ".md",
}

TEST_PATH_RE = re.compile(
    r"(^|/)(__tests__|__mocks__|tests?|e2e|cypress|fixtures|mocks|seeds?)(/|$)"
    r"|\.(spec|test|stories|e2e|cy)\.[jt]sx?$"
    r"|(^|/)(seed|jest\.setup|vitest\.setup)\.[jt]s$",
    re.I,
)


def _parts(path: str) -> list[str]:
    return path.split("/")


def is_lockfile(path: str) -> bool:
    return _parts(path)[-1] in LOCKFILES


def is_generated(path: str) -> bool:
    if any(p in GENERATED_DIR_PARTS for p in _parts(path)):
        return True
    if GENERATED_NAME_RE.search(path):
        return True
    # Las migraciones de Prisma las genera la CLI: se versionan, pero no se revisan a mano.
    return "/migrations/" in f"/{path}" and "prisma" in path.lower()


def ext_of(path: str) -> str:
    name = _parts(path)[-1]
    return name[name.rindex("."):].lower() if "." in name[1:] else ""


def is_binary(path: str) -> bool:
    return ext_of(path) in BINARY_EXTS


def is_test_path(path: str) -> bool:
    return bool(TEST_PATH_RE.search(path))


def is_reviewable(path: str) -> bool:
    """¿Las líneas de este archivo cuentan para el límite de 1000 de QA-01?"""
    return not (is_lockfile(path) or is_generated(path) or is_binary(path))


@dataclass
class FileDiff:
    path: str                       # ruta nueva (la del lado RIGHT)
    old_path: str | None = None
    status: str = "modified"        # added | modified | deleted | renamed
    is_binary_patch: bool = False
    additions: int = 0
    deletions: int = 0
    # (línea del lado RIGHT, contenido sin el '+')
    added_lines: list[tuple[int, str]] = field(default_factory=list)
    # (línea del lado LEFT, contenido sin el '-')
    removed_lines: list[tuple[int, str]] = field(default_factory=list)
    # Todas las líneas del lado RIGHT que aparecen dentro de un hunk (agregadas + contexto).
    # GitHub acepta comentarios inline en cualquiera de ellas.
    hunk_right_lines: set[int] = field(default_factory=set)

    @property
    def reviewable(self) -> bool:
        return is_reviewable(self.path)


_DIFF_GIT_RE = re.compile(r'^diff --git (?:"?a/(.+?)"?) (?:"?b/(.+?)"?)$')
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_patch(text: str) -> dict[str, FileDiff]:
    """Parsea un diff unificado de git y devuelve {ruta_nueva: FileDiff}."""
    files: dict[str, FileDiff] = {}
    current: FileDiff | None = None
    right_no = 0

    for raw in text.splitlines():
        m = _DIFF_GIT_RE.match(raw)
        if m:
            a, b = m.group(1), m.group(2)
            current = FileDiff(path=b, old_path=a)
            if a != b:
                current.status = "renamed"
            files[b] = current
            right_no = 0
            continue

        if current is None:
            continue

        if raw.startswith("new file mode"):
            current.status = "added"
            continue
        if raw.startswith("deleted file mode"):
            current.status = "deleted"
            continue
        if raw.startswith("Binary files ") or raw.startswith("GIT binary patch"):
            current.is_binary_patch = True
            continue
        if raw.startswith("rename to "):
            current.status = "renamed"
            continue
        if raw.startswith(("--- ", "+++ ", "index ", "similarity index",
                           "rename from ", "old mode", "new mode")):
            continue

        h = _HUNK_RE.match(raw)
        if h:
            right_no = int(h.group(1))
            continue

        if raw.startswith("+"):
            current.additions += 1
            current.added_lines.append((right_no, raw[1:]))
            current.hunk_right_lines.add(right_no)
            right_no += 1
        elif raw.startswith("-"):
            current.deletions += 1
            current.removed_lines.append((right_no, raw[1:]))
        elif raw.startswith(" "):
            current.hunk_right_lines.add(right_no)
            right_no += 1
        elif raw.startswith("\\"):
            pass  # "\ No newline at end of file"

    return files


def reviewable_changed_lines(files: dict[str, FileDiff]) -> int:
    """QA-01: additions + deletions, excluyendo lo no revisable."""
    return sum(f.additions + f.deletions for f in files.values() if f.reviewable)


def strip_code_comment(line: str) -> str:
    """Devuelve '' si la línea es solo un comentario de una línea.

    Deliberadamente conservador: solo detecta el caso obvio de una línea que
    arranca con un marcador de comentario. No intenta parsear bloques ni
    strings, porque un falso negativo acá solo significa un check menos.
    """
    s = line.strip()
    if s.startswith(("//", "#", "*", "/*", "<!--")):
        return ""
    return s
