#!/usr/bin/env python3
"""Datos del sprint desde Linear y GitHub, para los agentes programados.

El team no usa cycles de Linear: un sprint es el conjunto de tickets que
comparten el mismo `dueDate` (el jueves que cierra la semana). Por eso los
agentes que antes filtraban por `cycle.isActive` no veían nunca nada.

  sprint.py health      --team SPO --out report.json     semáforo diario, SIN modelo
  sprint.py weekly-data --team SPO --out data.json       insumo del status semanal
  sprint.py weekly-finish --report report.json --data data.json
                                                         agrega las métricas calculadas
  sprint.py dor-data    --team SPO --out data.json       backlog para el DoR

Los números salen de acá, nunca del modelo: el modelo solo redacta.
Necesita LINEAR_API_KEY, GH_TOKEN y GITHUB_REPOSITORY.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import agent_report as ar  # noqa: E402

ART = timezone(timedelta(hours=-3))
CLOSED = ("completed", "canceled")
WIP_LIMIT = 2
STALE_DAYS = 3
PR_WARN_H, PR_FAIL_H = 48, 72
MAX_LIST = 12

ISSUE_FIELDS = ("identifier title url estimate dueDate updatedAt completedAt "
                "state { name type } assignee { name }")


# --------------------------------------------------------------------------
# Fuentes
# --------------------------------------------------------------------------

def linear(query: str, variables: dict) -> dict:
    key = os.environ.get("LINEAR_API_KEY", "").strip()
    if not key:
        raise RuntimeError("sin LINEAR_API_KEY")
    req = urllib.request.Request(
        "https://api.linear.app/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("errors"):
        raise RuntimeError(data["errors"][0].get("message", "error de Linear"))
    return data["data"]


# Los valores van como literales (json.dumps los escapa) y no como variables:
# así la query no depende del nombre exacto de los scalars del schema de Linear.

def team_issues(team: str, since: datetime) -> list[dict]:
    q = (f"{{ issues(first: 250, filter: {{team: {{key: {{eq: {json.dumps(team)}}}}}, "
         f"updatedAt: {{gt: {json.dumps(since.isoformat())}}}}}) {{ nodes {{ {ISSUE_FIELDS} }} }} }}")
    return linear(q, {})["issues"]["nodes"]


def backlog_issues(team: str) -> list[dict]:
    q = (f"{{ issues(first: 100, filter: {{team: {{key: {{eq: {json.dumps(team)}}}}}, "
         f"state: {{type: {{in: [\"backlog\", \"unstarted\"]}}}}}}) {{ nodes {{ {ISSUE_FIELDS} "
         f"description labels {{ nodes {{ name }} }} parent {{ identifier }} }} }} }}")
    return linear(q, {})["issues"]["nodes"]


def prs(state: str, limit: int = 100) -> list[dict]:
    out = subprocess.run(
        ["gh", "pr", "list", "--repo", os.environ["GITHUB_REPOSITORY"], "--state", state,
         "--limit", str(limit), "--json",
         "number,title,url,createdAt,mergedAt,isDraft,reviewDecision,baseRefName,author"],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out or "[]")


# --------------------------------------------------------------------------
# Lógica (pura, testeable)
# --------------------------------------------------------------------------

def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _type(i: dict) -> str:
    return (i.get("state") or {}).get("type", "")


def _who(i: dict) -> str:
    return (i.get("assignee") or {}).get("name") or "sin asignar"


def _sp(issues: list[dict]) -> int:
    return int(sum(i.get("estimate") or 0 for i in issues))


def _line(i: dict) -> str:
    return f"- [{i['identifier']}]({i['url']}) {i['title']} · {i['state']['name']} · {_who(i)}"


def _lines(items: list[str]) -> str:
    extra = len(items) - MAX_LIST
    return "\n".join(items[:MAX_LIST] + ([f"- … y {extra} más"] if extra > 0 else []))


def _refs(issues: list[dict]) -> str:
    ids = [i["identifier"] for i in issues]
    return ", ".join(ids[:4]) + (f" +{len(ids) - 4}" if len(ids) > 4 else "")


def sprint_of(issues: list[dict], today: date) -> tuple[date | None, list[dict]]:
    """El sprint en curso: el dueDate más cercano >= hoy, y sus tickets."""
    alive = [i for i in issues if _type(i) != "canceled" and _d(i.get("dueDate"))]
    upcoming = sorted({_d(i["dueDate"]) for i in alive if _d(i["dueDate"]) >= today})
    if not upcoming:
        return None, []
    due = upcoming[0]
    return due, [i for i in alive if _d(i["dueDate"]) == due]


def overdue(issues: list[dict], today: date) -> list[dict]:
    return [i for i in issues if _d(i.get("dueDate")) and _d(i["dueDate"]) < today
            and _type(i) not in CLOSED]


def health_report(issues: list[dict] | None, open_prs: list[dict], now: datetime,
                  linear_error: str = "") -> dict:
    today = now.astimezone(ART).date()
    findings: list[dict] = []
    sections: list[dict] = []
    issues = issues or []

    if linear_error:
        findings.append({"severity": "important", "title": "Linear no respondió: el estado de los tickets es desconocido",
                         "detail": f"`{linear_error}`. El semáforo se arma solo con las PRs."})

    late = overdue(issues, today)
    if late:
        findings.append({"severity": "urgent",
                         "title": f"{len(late)} ticket(s) de un sprint ya cerrado siguen abiertos",
                         "ref": _refs(late), "detail": _lines([_line(i) for i in late])})

    started = [i for i in issues if _type(i) == "started"]
    by_dev: dict[str, list[dict]] = {}
    for i in started:
        by_dev.setdefault(_who(i), []).append(i)
    for dev, mine in sorted(by_dev.items()):
        if len(mine) > WIP_LIMIT and dev != "sin asignar":
            findings.append({"severity": "important",
                             "title": f"{dev} tiene {len(mine)} tickets en curso (límite {WIP_LIMIT})",
                             "ref": _refs(mine), "detail": _lines([_line(i) for i in mine])})

    stale = [i for i in started if (now - _dt(i["updatedAt"])).days >= STALE_DAYS]
    if stale:
        findings.append({"severity": "important",
                         "title": f"{len(stale)} ticket(s) en curso sin movimiento hace {STALE_DAYS}+ días",
                         "ref": _refs(stale), "detail": _lines([_line(i) for i in stale])})

    waiting = [p for p in open_prs if not p.get("isDraft") and p.get("reviewDecision") != "APPROVED"]
    for limit, sev in ((PR_FAIL_H, "urgent"), (PR_WARN_H, "important")):
        hit = [p for p in waiting if (now - _dt(p["createdAt"])).total_seconds() / 3600 > limit]
        waiting = [p for p in waiting if p not in hit]
        if hit:
            findings.append({"severity": sev,
                             "title": f"{len(hit)} PR(s) esperando review hace más de {limit} h",
                             "ref": ", ".join(f"#{p['number']}" for p in hit),
                             "detail": _lines([f"- [#{p['number']}]({p['url']}) {p['title']}" for p in hit])})

    due, sprint = sprint_of(issues, today)
    open_count = len([p for p in open_prs if not p.get("isDraft")])
    if due:
        done = [i for i in sprint if _type(i) == "completed"]
        left = (due - today).days
        total_sp, done_sp = _sp(sprint), _sp(done)
        ratio = done_sp / total_sp if total_sp else len(done) / len(sprint)
        falta = "cierra hoy" if left == 0 else "falta 1 día" if left == 1 else f"faltan {left} días"
        if left <= 2 and ratio < 0.5:
            findings.append({"severity": "important",
                             "title": f"Sprint en riesgo: {round(ratio * 100)}% hecho y {falta}"})
        summary = (f"Sprint que cierra el {due:%d/%m} ({falta}): "
                   f"{len(done)}/{len(sprint)} tickets · {done_sp}/{total_sp} SP · "
                   f"{len(started)} en curso · {open_count} PRs abiertas")
        rows = ["| Ticket | Estado | Quién | SP |", "|---|---|---|---|"]
        rows += [f"| [{i['identifier']}]({i['url']}) {i['title']} | {i['state']['name']} | {_who(i)} | "
                 f"{i.get('estimate') or '—'} |" for i in sorted(sprint, key=lambda x: x["state"]["name"])]
        sections.append({"title": f"Tickets del sprint ({len(sprint)})", "body": "\n".join(rows)})
    elif linear_error:
        summary = f"Sin datos de Linear · {open_count} PRs abiertas"
    else:
        summary = f"No hay tickets con fecha de cierre de hoy en adelante: no hay sprint que medir · {open_count} PRs abiertas"

    sevs = {f["severity"] for f in findings}
    status = "fail" if "urgent" in sevs else "warn" if "important" in sevs else "ok"
    return ar.normalize({"status": status, "summary": summary, "ai": False,
                         "findings": findings, "sections": sections},
                        "sprint-health", f"Sprint Health · {today:%d/%m}")


def weekly_data(issues: list[dict], open_prs: list[dict], merged: list[dict], now: datetime) -> dict:
    today = now.astimezone(ART).date()
    since = now - timedelta(days=7)
    done = [i for i in issues if _type(i) == "completed" and _dt(i.get("completedAt"))
            and _dt(i["completedAt"]) >= since]
    merged = [p for p in merged if _dt(p.get("mergedAt")) and _dt(p["mergedAt"]) >= since]
    due, sprint = sprint_of(issues, today)
    late = overdue(issues, today)

    def slim(i: dict) -> dict:
        return {"id": i["identifier"], "title": i["title"], "state": i["state"]["name"],
                "who": _who(i), "sp": i.get("estimate"), "due": i.get("dueDate")}

    return {
        "today": today.isoformat(),
        "completed_last_7d": [slim(i) for i in done],
        "current_sprint": {"closes": due.isoformat() if due else None,
                           "issues": [slim(i) for i in sprint]},
        "carry_over": [slim(i) for i in late],
        "merged_prs_last_7d": [{"n": p["number"], "title": p["title"], "base": p["baseRefName"],
                                "url": p["url"]} for p in merged],
        "open_prs": [{"n": p["number"], "title": p["title"], "draft": p.get("isDraft")} for p in open_prs],
        "metrics": {
            "tickets_completados_7d": len(done),
            "sp_completados_7d": _sp(done),
            "prs_mergeados_7d": len(merged),
            "prs_a_main_7d": len([p for p in merged if p["baseRefName"] == "main"]),
            "arrastre_tickets": len(late),
            "arrastre_sp": _sp(late),
            "sprint_cierra": due.isoformat() if due else None,
            "sprint_hecho": f"{len([i for i in sprint if _type(i) == 'completed'])}/{len(sprint)}",
        },
    }


def metrics_section(data: dict) -> dict:
    m = data["metrics"]
    rows = ["| Métrica | Valor |", "|---|---|",
            f"| Tickets completados (7 días) | {m['tickets_completados_7d']} |",
            f"| SP completados (7 días) | {m['sp_completados_7d']} |",
            f"| PRs mergeadas (7 días) | {m['prs_mergeados_7d']} ({m['prs_a_main_7d']} a main) |",
            f"| Arrastre de sprints cerrados | {m['arrastre_tickets']} tickets · {m['arrastre_sp']} SP |",
            f"| Sprint en curso | {m['sprint_hecho']} tickets hechos"
            + (f" · cierra {date.fromisoformat(m['sprint_cierra']):%d/%m}" if m["sprint_cierra"] else "") + " |"]
    return {"title": "Métricas (calculadas de Linear y GitHub, no del modelo)", "body": "\n".join(rows), "open": True}


def dor_data(issues: list[dict]) -> list[dict]:
    out = []
    for i in issues:
        flags = []
        if i.get("estimate") is None:
            flags.append("sin estimación")
        elif i["estimate"] > 4:
            flags.append(f"estimación {i['estimate']} > 4: hay que partirlo")
        out.append({"id": i["identifier"], "title": i["title"], "state": i["state"]["name"],
                    "estimate": i.get("estimate"), "due": i.get("dueDate"),
                    "labels": [lb["name"] for lb in (i.get("labels") or {}).get("nodes", [])],
                    "parent": (i.get("parent") or {}).get("identifier"),
                    "flags": flags, "description": (i.get("description") or "")[:1500]})
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("health", "weekly-data", "dor-data"):
        p = sub.add_parser(name)
        p.add_argument("--team", required=True)
        p.add_argument("--out", required=True)
    p = sub.add_parser("weekly-finish")
    p.add_argument("--report", required=True)
    p.add_argument("--data", required=True)
    args = ap.parse_args(argv)
    now = datetime.now(timezone.utc)

    if args.cmd == "health":
        try:
            issues, err = team_issues(args.team, now - timedelta(days=60)), ""
        except Exception as e:  # noqa: BLE001 — sin Linear el semáforo sigue con las PRs
            issues, err = None, str(e)[:200]
        report = health_report(issues, prs("open"), now, err)
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{report['status']}: {report['summary']}")
    elif args.cmd == "weekly-data":
        try:
            issues, err = team_issues(args.team, now - timedelta(days=60)), ""
        except Exception as e:  # noqa: BLE001 — el informe sale igual, con las PRs, y lo dice
            issues, err = [], str(e)[:200]
            print(f"::warning title=Linear::{err}")
        data = weekly_data(issues, prs("open"), prs("merged"), now)
        if err:
            data["linear_error"] = f"Linear no respondió ({err}): no hay datos de tickets esta semana."
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(data["metrics"], ensure_ascii=False))
    elif args.cmd == "weekly-finish":
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        if report.get("status") != "unknown":
            data = json.loads(Path(args.data).read_text(encoding="utf-8"))
            report["sections"] = [metrics_section(data)] + list(report.get("sections") or [])
            Path(args.report).write_text(json.dumps(ar.normalize(report), ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    elif args.cmd == "dor-data":
        data = dor_data(backlog_issues(args.team))
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(data)} tickets en backlog/todo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
