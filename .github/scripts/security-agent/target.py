"""Cliente HTTP del blanco (el back levantado por `boot-server.js`).

Lo usan `baseline.py`, la herramienta `http` del agente y el replay. Es el único
lugar que sabe hablar con el blanco, y por eso es también el guardarraíl: solo
puede pegarle a 127.0.0.1, nunca a una URL que venga del modelo.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

PORT = int(os.environ.get("SEC_PORT", "3900"))
BASE = f"http://127.0.0.1:{PORT}"
USERS = ("A", "B", "C")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
TIMEOUT = 15
MAX_BODY = 4_000


def request(method: str, path: str, body=None, as_user: str | None = None) -> dict:
    """Un request al blanco. Nunca lanza: los errores vuelven como resultado."""
    method = (method or "").upper()
    if method not in METHODS:
        raise ValueError(f"método no permitido: {method!r}")
    if not path.startswith("/") or path.startswith("//") or "://" in path:
        raise ValueError(f"ruta inválida: {path!r} (tiene que empezar con /)")
    if path.startswith("/__sec"):
        raise ValueError("las rutas /__sec son del arnés, no del back")
    if as_user is not None and as_user not in USERS:
        raise ValueError(f"usuario inválido: {as_user!r} (A, B, C o null)")

    headers = {"accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["content-type"] = "application/json"
    if as_user:
        headers["x-sec-user"] = as_user

    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            status, raw = res.status, res.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except (urllib.error.URLError, TimeoutError) as e:
        status, raw = 0, str(e).encode()

    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text) if text else None
    except json.JSONDecodeError:
        parsed = text
    return {
        "request": {"method": method, "path": path, "as": as_user, "body": body},
        "status": status,
        "body": parsed,
    }


def render(res: dict) -> str:
    """Lo que ve el modelo: status + body recortado."""
    body = res["body"]
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    if text and len(text) > MAX_BODY:
        text = text[:MAX_BODY] + f"… [recortado, {len(text)} chars]"
    return f"HTTP {res['status']}\n{text or '(sin body)'}"


def reset() -> None:
    req = urllib.request.Request(BASE + "/__sec/reset", method="POST")
    with urllib.request.urlopen(req, timeout=120) as res:
        if res.status != 200:
            raise RuntimeError(f"reset falló: HTTP {res.status}")
