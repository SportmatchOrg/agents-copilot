#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera los datos v4 de las vistas de leadership (WBS, PERT y Gantt) y las tablas
del calendario semana a semana del Cronograma v4.

Entradas
  docs/planning/WBS-SportMatch-v4.md        118 paquetes: título, dependencias, horas PERT
  docs/planning/linear-wbs-map.csv          issue de Linear -> paquete de la WBS (a mano)
  docs/planning/linear-issues.csv           estado y fechas reales por ticket (lo refresca sync-linear.mjs)

Salidas (intermedias; se pegan a mano en los HTML y en el doc, no se commitean)
  scripts/_v4_wbs.js          bloque V4_ADD para leadership/wbs.html
  scripts/_v4_pert.js         tasks / deps / groups para leadership/pert.html (118 paquetes)
  scripts/_v4_gantt.js        tasks para leadership/gantt.html (78 paquetes de desarrollo)
  scripts/_v4_calendario.md   tablas para Cronograma-y-PERT-v4.md (§4 con fechas y §9 semanal)

Calendario: semanas de jueves a jueves, cierre a las 18 h. La semana 1 abre el 06/08.
S1 = semanas 1–6 (cierra 17/09) · S2 = 7–10 (15/10) · S3 = 11–13 (05/11) · semana 14 = reserva.
"""
import csv, io, json, re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WBS = ROOT / 'docs' / 'planning' / 'WBS-SportMatch-v4.md'
MAP = ROOT / 'docs' / 'planning' / 'linear-wbs-map.csv'
ISSUES = ROOT / 'docs' / 'planning' / 'linear-issues.csv'
OUT = ROOT / 'scripts'

# ───────────────────────── calendario ─────────────────────────
WEEK1 = date(2026, 8, 6)                  # jueves que abre la semana 1
N_WEEKS = 14
RESERVE_WEEK = 14                         # 05/11 → 12/11: sin trabajo planificado
SPRINT_WEEKS = {'S1': (1, 6), 'S2': (7, 10), 'S3': (11, 13)}
CAP_PER_DEV = 6.0                         # h por dev y semana
MIN_CHUNK = 3.0                           # h mínimas libres en la semana en que arranca una tarea
TAIL = 0.5                                # cola máxima que una semana absorbe por encima de las 6 h
DEVS = (1, 2, 3)                          # 1 Front (Pache) · 2 Back (Rudolph) · 3 Infra (Siaba)

def wstart(n): return WEEK1 + timedelta(days=7 * (n - 1))
def wend(n):   return WEEK1 + timedelta(days=7 * n)
def week_of(ts_utc):
    """Semana a la que pertenece un instante de Linear: cierra el jueves a las 18 h (ART)."""
    t = ts_utc - timedelta(hours=3)
    for n in range(1, N_WEEKS + 1):
        if t <= datetime.combine(wend(n), datetime.min.time()).replace(hour=18):
            return n
    raise ValueError(ts_utc)
def sprint_of_week(n):
    for s, (a, b) in SPRINT_WEEKS.items():
        if a <= n <= b: return s
    return 'reserva'

# ───────────────────────── WBS v4 ─────────────────────────
txt = io.open(WBS, encoding='utf-8').read()
PKG_RE = re.compile(r'^\*\*(\d+\.\d+\.\d+)\*\*([^\n]*?)— ([^\n:]+?)[:.] [^\n]*\n<br>\*Dependencias:\* ([^·]+)· \*Estimación:\* ([0-9.]+) h', re.M)
TASKS = {}
for m in PKG_RE.finditer(txt):
    tid, mark, title, deps, est = m.groups()
    deps = [] if deps.strip().startswith('—') else [d.strip() for d in deps.split(',') if d.strip()]
    TASKS[tid] = {'title': title.strip(), 'deps': deps, 'dur': float(est), 'new_v4': '✳️' in mark}
assert len(TASKS) == 118, len(TASKS)

MODULES = dict(re.findall(r'^## (\d+)\.0 ([^\n]+?)(?: — \*\*NUEVO\*\*)?$', txt, re.M))          # '4' -> 'Autenticación'
SUBS = dict(re.findall(r'^### (\d+\.\d+) ([^\n]+?)(?: — \*\*NUEVO\*\*)?$', txt, re.M))          # '4.1' -> 'Backend de autenticación'
MOD_NAME = {k: f'{k}.0 {v}' for k, v in MODULES.items()}
key = lambda s: tuple(int(p) for p in s.split('.'))
l2 = lambda s: '.'.join(s.split('.')[:2])

# Dependencias blandas que conserva el modelo de desarrollo (mismas que en v2 y en pert_v4.py).
SOFT = {'3.2.1': ['3.1.3'], '4.1.1': ['3.1.2']}
for k, v in SOFT.items():
    TASKS[k]['deps'] = sorted(set(TASKS[k]['deps'] + v), key=key)

# ───────────────────────── CPM ─────────────────────────
def cpm(scope):
    """scope: dict id -> {'deps','dur'}; deps fuera del scope se ignoran. Devuelve ES/EF/LS/LF/H."""
    deps = {k: [d for d in v['deps'] if d in scope] for k, v in scope.items()}
    order, seen = [], {}
    def visit(n):
        if seen.get(n) == 2: return
        assert seen.get(n) != 1, 'ciclo en ' + n
        seen[n] = 1
        for d in deps[n]: visit(d)
        seen[n] = 2; order.append(n)
    for n in scope: visit(n)
    r = {}
    for n in order:
        es = max([r[d]['EF'] for d in deps[n]] or [0.0])
        r[n] = {'ES': es, 'EF': es + scope[n]['dur']}
    T = max(v['EF'] for v in r.values())
    succ = defaultdict(list)
    for n, ds in deps.items():
        for d in ds: succ[d].append(n)
    for n in reversed(order):
        lf = min([r[s]['LS'] for s in succ[n]] or [T])
        r[n]['LF'] = lf; r[n]['LS'] = lf - scope[n]['dur']
        r[n]['H'] = round(r[n]['LS'] - r[n]['ES'], 2)
    return r, deps, T

FULL, FULL_DEPS, T_FULL = cpm(TASKS)
DEV_SCOPE = {'3', '4', '5', '6', '7', '9', '10', '11', '12', '13'}
DEV = {k: v for k, v in TASKS.items() if k.split('.')[0] in DEV_SCOPE}
DEVCPM, DEV_DEPS, T_DEV = cpm(DEV)
assert len(DEV) == 78, len(DEV)
crit_full = sorted([n for n in FULL if abs(FULL[n]['H']) < 1e-6], key=lambda n: FULL[n]['ES'])
crit_dev  = sorted([n for n in DEVCPM if abs(DEVCPM[n]['H']) < 1e-6], key=lambda n: DEVCPM[n]['ES'])

# ───────────────────────── Linear ─────────────────────────
DONE_STATUSES = {'Done'}
ASSIGNEE_DEV = {'ipacheco': 1, 'jrudolph': 2, 'jfsiaba': 3}
TICKETS = {}
with io.open(ISSUES, encoding='utf-8') as f:
    for r in csv.DictReader(f):
        n = int(r['issue'].split('-')[1])
        P = lambda s: datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S') if s else None
        TICKETS[n] = {'status': r['status'], 'started': P(r['started']), 'completed': P(r['completed']),
                      'dev': ASSIGNEE_DEV.get(r['assignee']), 'type': r['type'], 'pts': float(r['estimate'] or 0)}

# Paquete -> tickets que fijan su ventana de fechas, desde docs/planning/linear-wbs-map.csv.
# Sólo las filas con fechas='si': los hotfix y los arreglos posteriores al cierre del paquete van
# con 'no' porque no son alcance del paquete y estiraban su ventana. Ver docs/planning/plan-linear.md.
PKG_TICKETS = defaultdict(list)
with io.open(MAP, encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r['fechas'] == 'si':
            PKG_TICKETS[r['wbs_id']].append(int(r['issue'].split('-')[1]))
# Paquetes hechos sin ticket propio: semana (inicio, fin) fijada a mano.
MANUAL_WEEK = {
 '3.1.1': (1, 1, 3),   # stack definido en el kick-off (Infra)
 '3.1.3': (1, 1, 3),   # convenciones de ramas/PR/Linear escritas en AGENTS.md la semana del kick-off
 '10.2.1': (2, 2, 3),  # README con instalación y ejecución local, junto con la base del repo (SPO-143)
}
# 13.0 Challenge: ventana fijada por el equipo, 01/10 → 14/10 (semanas 9 y 10). No pasa por el planificador ni le
# saca capacidad: el ADR le asigna 6 h a Lab2 (3 h por paquete, re-estimado el 12/10) sin mover fechas (docs/challenge/ADR.md). 13.1.1 cerró en la semana 9;
# 13.1.2 queda abierto hasta el cierre de la épica.
FIXED_WEEK = {'13.1.1': (9, 9, 2), '13.1.2': (9, 10, 2)}
# Estado según Cronograma-y-PERT-v4.md §4/§5: 43 ✅ (S1), 5 🟡 (parciales, cierran en S2).
# 6.4.2 cierra en el S1: SPO-215 y SPO-218 pasaron a Done el 15/09 y el 16/09 (export del 17/09).
DONE = {'3.1.1','3.1.2','3.1.3','3.2.1','3.2.2','3.2.3','4.1.1','4.1.2','4.1.3','4.1.4','4.2.1','4.2.2',
        '4.2.3','4.2.4','4.2.5','5.1.2','5.1.3','5.1.5','5.2.1','5.2.4','5.2.5','6.1.1','6.1.2','6.1.3',
        '6.1.5','6.2.1','6.2.2','6.2.3','6.2.4','6.3.1','6.3.2','6.3.3','6.3.4','6.3.5','6.4.1','7.2.1',
        '6.4.2','7.2.2','9.1.1','9.1.2','9.1.3','9.1.4','10.2.1'}
WIP = {'5.1.1', '5.1.4', '5.2.3', '7.1.1', '10.1.2'}
SPRINT_OF = {}
for k in DONE: SPRINT_OF[k] = 'S1'
for k in ['5.1.1','5.1.4','5.2.2','5.2.3','6.1.4','6.2.5','6.2.6','6.4.3','7.1.1','7.1.2','7.1.3',
          '7.3.1','7.3.2','7.3.3','10.1.2','11.1.1','11.1.2','11.1.3','11.2.1','11.2.2','11.2.3','13.1.1','13.1.2']: SPRINT_OF[k] = 'S2'
for k in ['6.5.1','6.5.2','6.5.3','10.1.1','10.2.2','11.1.4','12.1.1','12.1.2','12.1.3','12.2.1','12.2.2','12.2.3']: SPRINT_OF[k] = 'S3'
assert set(SPRINT_OF) == set(DEV), set(DEV) ^ set(SPRINT_OF)
assert len(DONE) == 43 and len([k for k, s in SPRINT_OF.items() if s == 'S2']) == 23

# Dev preferido para lo pendiente, por naturaleza del paquete. El scheduler puede dárselo a otro
# dev si así termina antes: Siaba (3) tomó tickets de front en los sprints 4 y 5.
DEV_PREF = {}
for k in SPRINT_OF:
    if k in DONE: continue
    mod, sub = k.split('.')[0], l2(k)
    if k in ('7.3.1', '10.1.1', '10.1.2', '10.2.2', '11.1.2'): DEV_PREF[k] = 3
    elif sub in ('5.2', '6.2', '7.2', '7.3', '11.2') or k in ('7.1.2', '6.4.2', '6.5.1', '12.1.3', '12.2.1'): DEV_PREF[k] = 1
    else: DEV_PREF[k] = 2

# ───────────────────────── fechas de lo hecho ─────────────────────────
sched = {}   # id -> {'sw','ew','dev','status'}
for k in DEV:
    if k in FIXED_WEEK:
        sw, ew, dev = FIXED_WEEK[k]; sched[k] = {'sw': sw, 'ew': ew, 'dev': dev, 'psw': sw, 'status': 'wip'}
        continue
    # Sólo los tickets ya cerrados fijan la ventana. Si al paquete no le cerró ninguno todavía,
    # queda para el planificador de más abajo.
    ts = [TICKETS[n] for n in PKG_TICKETS.get(k, []) if TICKETS[n]['status'] in DONE_STATUSES]
    if ts:
        starts = [week_of(t['started']) if t['started'] else 6 for t in ts]
        ends = [week_of(t['completed']) if t['completed'] else 6 for t in ts]
        devs = [t['dev'] for t in ts if t['dev']]
        dev = max(set(devs), key=devs.count) if devs else 3
        sched[k] = {'sw': min(starts), 'ew': max(ends), 'dev': dev}
    elif k in MANUAL_WEEK:
        sw, ew, dev = MANUAL_WEEK[k]; sched[k] = {'sw': sw, 'ew': ew, 'dev': dev}
    if k in DONE:
        assert k in sched, k
        assert sched[k]['ew'] <= 6, (k, sched[k])
        sched[k]['status'] = 'done'

# ───────────────────────── planificación de lo pendiente ─────────────────────────
cap = {d: {w: CAP_PER_DEV for w in range(1, N_WEEKS + 1)} for d in DEVS}
pending = [k for k in DEV if k not in DONE and k not in FIXED_WEEK]
# Prioridad: sprint, después la cadena más larga que queda por delante dentro del mismo sprint
# (para que un dev tome el bloque completo y no se pierda una semana en cada cambio de manos), después id.
SUCC = defaultdict(list)
for k, ds in DEV_DEPS.items():
    for d in ds: SUCC[d].append(k)
_rank = {}
def rank(k):
    if k not in _rank:
        _rank[k] = DEV[k]['dur'] + max([rank(s) for s in SUCC[k] if SPRINT_OF[s] == SPRINT_OF[k]] or [0.0])
    return _rank[k]
# Las tareas del camino crítico del PERT, y las que las preceden, van primero dentro de su sprint.
_urg = {}
def urgent(k):
    if k not in _urg:
        _urg[k] = DEVCPM[k]['H'] < 1e-6 or any(urgent(s) for s in SUCC[k])
    return _urg[k]
prio = lambda k: (SPRINT_WEEKS[SPRINT_OF[k]][0], not urgent(k), -rank(k), key(k))
overflow = []
placed = set(DONE)
while pending:
    ready = [k for k in pending if all(d in placed or d not in DEV for d in DEV_DEPS[k])]
    assert ready, pending
    t = min(ready, key=prio); pending.remove(t); placed.add(t)
    s_a, s_b = SPRINT_WEEKS[SPRINT_OF[t]]
    # Un mismo dev puede encadenar una dependencia dentro de la semana (la ordena el plan de sprint);
    # entre devs distintos, el sucesor arranca la semana siguiente.
    # Una tarea arranca en una semana donde el dev tiene lugar para al menos MIN_CHUNK h (o la tarea
    # entera si es más corta): así una tarea de 1,5 h no queda regada en migajas de varias semanas.
    # Fuera de su área un dev paga penalidad: Siaba (3) es flexible y toma front o back si eso
    # ahorra una semana; Pache y Rudolph sólo cruzan de área si ahorra dos.
    best = None
    for dv in DEVS:
        w = max([sched[d]['ew'] + (0 if sched[d]['dev'] == dv else 1) for d in DEV_DEPS[t] if d in sched] + [s_a])
        need = min(DEV[t]['dur'], MIN_CHUNK)
        while w <= N_WEEKS and cap[dv][w] < need - 1e-9: w += 1
        rem, sw, ew = DEV[t]['dur'], w, w
        while rem > 1e-9 and ew <= N_WEEKS:
            take = min(rem, cap[dv][ew]); rem -= take
            if rem <= TAIL: rem = 0          # una cola de hasta TAIL h se absorbe en la misma semana
            if rem > 1e-9: ew += 1
        pen = 0 if dv == DEV_PREF[t] else (0.5 if dv == 3 else 1.5)
        cand = (ew > s_b, ew + pen, sw, dv)  # desbordar el sprint es el peor costo posible
        if best is None or cand < best[0]: best = (cand, sw, ew, dv)
    _, sw, ew, dv = best
    rem = DEV[t]['dur']
    for w in range(sw, ew + 1):
        take = min(rem, cap[dv][w]) if w < ew else rem
        cap[dv][w] -= take; rem -= take
    if ew > s_b: overflow.append((t, SPRINT_OF[t], sw, ew))
    st = sched.setdefault(t, {'sw': sw})
    st['sw'] = min(st['sw'], sw); st['ew'] = ew; st['dev'] = dv; st['psw'] = sw   # psw: semana en que se planifican las horas
    st['status'] = 'wip' if t in WIP else 'todo'

# ───────────────────────── checks ─────────────────────────
print(f'paquetes: {len(TASKS)} · desarrollo: {len(DEV)} ({sum(v["dur"] for v in DEV.values()):.2f} h)')
print(f'CPM completo: {T_FULL:.2f} h · crítico: {" → ".join(crit_full)}')
print(f'CPM desarrollo: {T_DEV:.2f} h · crítico: {" → ".join(crit_dev)}')
if overflow: print('!! DESBORDE DE SPRINT:', overflow)
assert all(v['ew'] < RESERVE_WEEK for v in sched.values()), 'hay trabajo en la semana de reserva'
# Sólo puede haber violaciones donde hay fechas reales: sucesor hecho o parcial, o dependencia hecha.
viol = sorted(f'{t}<{d}' for t in DEV for d in DEV_DEPS[t] if sched[t]['sw'] < sched[d]['ew'] and (t in DONE or t in WIP or d in DONE))
print('violaciones de dependencia por fechas reales:', viol)
for s, (a, b) in SPRINT_WEEKS.items():
    hs = sum(DEV[k]['dur'] for k, v in SPRINT_OF.items() if v == s)
    print(f'{s}: {sum(1 for v in SPRINT_OF.values() if v == s)} paquetes · {hs:.2f} h / {(b - a + 1) * 18} h')
for w in range(7, N_WEEKS + 1):
    load = {d: round(CAP_PER_DEV - cap[d][w], 2) for d in DEVS}
    print(f'  sem {w:2d} ({wstart(w):%d/%m}→{wend(w):%d/%m}) ' + '  '.join(f'D{d} {load[d]:4.1f}h' for d in DEVS))

# ───────────────────────── salidas JS ─────────────────────────
J = lambda s: json.dumps(s, ensure_ascii=False)

# WBS: altas v2 -> v4 (lo que la WBS v4 tiene y la vista v2 no), agrupadas por sub-paquete.
V2_IDS = set('''1.1.1 1.1.2 1.1.3 1.2.1 1.2.2 1.2.3 1.2.4 1.3.1 1.3.2 1.3.3 1.4.1 1.4.2 2.1.1 2.1.2 2.2.1 2.2.2 2.2.3 2.2.4
2.2.5 2.2.6 2.2.7 2.2.8 2.3.1 2.3.2 3.1.1 3.1.2 3.1.3 3.2.1 3.2.2 3.2.3 4.1.1 4.1.2 4.1.3 4.2.1 5.1.1 5.1.2 5.1.3 5.1.4 5.2.1
5.2.2 5.2.3 5.2.4 6.1.1 6.1.2 6.1.3 6.1.4 6.2.1 6.2.2 6.2.3 6.2.5 6.2.6 6.3.1 6.3.2 6.3.3 6.3.4 6.4.1 6.4.2 6.4.3 6.5.1 6.5.2
6.5.3 7.1.1 7.1.2 7.1.3 7.2.1 7.2.2 7.3.1 7.3.2 7.3.3 8.1.1 8.1.2 8.1.3 8.1.4 8.1.5 8.1.6 8.1.7 8.1.8 8.1.9 8.1.10 8.2.1 8.2.2
8.2.3 8.2.4 9.1.1 9.1.2 9.1.3 10.1.1 10.1.2 10.2.1 10.2.2 11.1.1 11.1.2 11.1.3 11.1.4 11.2.1 11.2.2 11.2.3 12.1.1 12.1.2 12.1.3'''.split())
assert len(V2_IDS) == 100
adds = defaultdict(list)
for k in sorted(TASKS, key=key):
    if k not in V2_IDS: adds[l2(k)].append(f'{k} {TASKS[k]["title"]}')
lines = ['const V4_ADD = [']
for sub, items in adds.items():
    lines.append(f' [{J(MOD_NAME[sub.split(".")[0]])}, {J(sub + " " + SUBS[sub])},')
    lines.append('   [' + ', '.join(J(i) for i in items) + ']],')
lines.append('];')
(OUT / '_v4_wbs.js').write_text('\n'.join(lines) + '\n', encoding='utf-8')

# PERT: 118 paquetes con CPM completo.
GROUPS = {
 '1.1':'Planificación técnica','1.2':'Gestión del proyecto','1.3':'Comunicación','1.4':'Cierre del proyecto',
 '2.1':'Identidad y perfiles','2.2':'Diseño de pantallas','2.3':'Modelo de datos',
 '3.1':'Configuración técnica','3.2':'Setup del entorno','4.1':'Autenticación backend','4.2':'Auth frontend',
 '5.1':'Backend de perfil','5.2':'Frontend de perfil','6.1':'Backend de partidos','6.2':'Frontend de partidos',
 '6.3':'Solicitudes','6.4':'Calificación','6.5':'Invitación a partido','7.1':'Motor de búsqueda',
 '7.2':'Experiencia swipe','7.3':'Visualización en mapa','8.1':'QA manual','8.2':'Pruebas con usuarios',
 '8.3':'QA automatizado','9.1':'Despliegue','10.1':'Docs de usuario','10.2':'Docs técnicas',
 '11.1':'Notificaciones backend','11.2':'Notificaciones frontend','12.1':'Reportar usuario','12.2':'Panel de moderación',
 '13.1':'Reporte de KPIs',
}
assert {l2(k) for k in TASKS} <= set(GROUPS)
f2 = lambda x: f'{x:.2f}'
lines = ['    tasks: {']
for k in sorted(TASKS, key=key):
    r = FULL[k]
    lines.append(f"      '{k}':{{ dur:{f2(TASKS[k]['dur'])}, es:{f2(r['ES'])}, ef:{f2(r['EF'])}, ls:{f2(r['LS'])}, lf:{f2(r['LF'])}, tf:{f2(abs(r['H']))} }},")
lines += ['    },', '    deps: {']
for k in sorted(TASKS, key=key):
    lines.append(f"      '{k}': {json.dumps(sorted(TASKS[k]['deps'], key=key))},")
lines += ['    },', '    groups: {']
for g in sorted(GROUPS, key=key):
    lines.append(f"      '{g}':{J(GROUPS[g])},")
lines += ['    },', f"    newIds: {json.dumps(sorted([k for k in TASKS if k not in V2_IDS], key=key))},"]
(OUT / '_v4_pert.js').write_text('\n'.join(lines) + '\n', encoding='utf-8')

# Gantt: 78 paquetes de desarrollo con fechas jueves a jueves.
lines = ['    tasks: [']
for k in sorted(DEV, key=key):
    s = sched[k]
    lines.append(f'    {{ id:"{k}", mod:{J(MOD_NAME[k.split(".")[0]])}, name:{J(DEV[k]["title"])}, dev:{s["dev"]}, '
                 f'start:"{wstart(s["sw"])}", end:"{wend(s["ew"])}", hours:{DEV[k]["dur"]:.2f}, status:"{s["status"]}", '
                 f'deps:{json.dumps(DEV_DEPS[k])} }},')
lines += ['    ],', '    devs: {1:"Pache", 2:"Rudolph", 3:"Siaba"},', f'    critical: {json.dumps(crit_dev)},',
          f"    newIds: {json.dumps(sorted([k for k in DEV if k not in V2_IDS], key=key))},",
          f'    knownDepViolations: {json.dumps(viol)},']
(OUT / '_v4_gantt.js').write_text('\n'.join(lines) + '\n', encoding='utf-8')

# Y lo mismo, pegado en la página: es lo único que cambia cada vez que se sincroniza Linear,
# así que dejarlo a mano garantiza que tarde o temprano el Gantt muestre fechas viejas.
gantt_html = ROOT / 'leadership' / 'gantt.html'
html = gantt_html.read_text(encoding='utf-8')
a, b = html.index('    // gen-begin'), html.index('    // gen-end')
head = html[a:html.index('\n', a) + 1]
gantt_html.write_text(html[:a] + head + '\n'.join(lines) + '\n' + html[b:], encoding='utf-8')

# ───────────────────────── salidas markdown ─────────────────────────
ST = {'done': '✅', 'wip': '🟡', 'todo': '⬜'}
DNAME = {1: 'Pache', 2: 'Rudolph', 3: 'Siaba'}
md = []
for s in ('S1', 'S2', 'S3'):
    ids = sorted([k for k, v in SPRINT_OF.items() if v == s], key=key)
    md += [f'### {s} — {sum(DEV[k]["dur"] for k in ids):.2f} h', '',
           '| ID | Paquete | Dur (h) | Holgura | Dev | Inicio | Fin | Estado |', '|---|---|---:|---:|---|---|---|:---:|']
    for k in ids:
        x = sched[k]
        md.append(f'| {k} | {DEV[k]["title"]} | {DEV[k]["dur"]:.2f} | {DEVCPM[k]["H"]:.2f} | {DNAME[x["dev"]]} | '
                  f'{wstart(x["sw"]):%d/%m} | {wend(x["ew"]):%d/%m} | {ST[x["status"]]} |')
    md.append('')
md += ['## Calendario semana a semana', '',
       '| Sem | Ventana | Sprint | Pache (Front) | Rudolph (Back) | Siaba (Infra) | Carga |', '|---|---|---|---|---|---|---:|']
for w in range(7, N_WEEKS + 1):
    cells = []
    for d in DEVS:
        items = [k for k in sorted(DEV, key=key) if sched[k]['dev'] == d and sched[k]['status'] != 'done' and sched[k]['psw'] <= w <= sched[k]['ew']]
        cells.append('<br>'.join(f'{k} {DEV[k]["title"]}' for k in items) or '—')
    load = sum(CAP_PER_DEV - cap[d][w] for d in DEVS)
    md.append(f'| {w} | {wstart(w):%d/%m} → {wend(w):%d/%m} | {sprint_of_week(w)} | ' + ' | '.join(cells) + f' | {load:.1f} / 18 h |')
md += ['', '### PERT completo (118 paquetes)', '',
       f'Duración del camino crítico: {T_FULL:.2f} h · {len(crit_full)} paquetes: ' + ' → '.join(crit_full), '']
(OUT / '_v4_calendario.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
print('->', ', '.join(p.name for p in (OUT / '_v4_wbs.js', OUT / '_v4_pert.js', OUT / '_v4_gantt.js', OUT / '_v4_calendario.md')))

# ───────────────────────── actividades clave (tablero semanal del steering) ─────────────────────────
# docs/planning/actividades-clave.csv (a mano): actividad -> prefijos de la WBS y fin de línea base
# y, si el número calculado no refleja la realidad, avance y estado pisados a mano.
# Avance: puntos de los issues en Done sobre los puntos de todos los issues de la actividad (cada issue una
# sola vez, sólo filas con fechas='si', sin cancelados). Sin issues, 0 %.
# Cada fila lleva su lista de issues para que el steering muestre cómo sale el número.
# Cada corrida guarda un snapshot en leadership/steering.html bajo el jueves del corte; correrla dos veces en la
# misma semana pisa el snapshot.
ACT_CSV = ROOT / 'docs' / 'planning' / 'actividades-clave.csv'
D = lambda s: datetime.strptime(s, '%d/%m/%y').date()
F = lambda d: f'{d:%d/%m/%y}' if d else ''
art = lambda ts: (ts - timedelta(hours=3)).date()
this_week = week_of(datetime.utcnow())
cut = date.today() + timedelta(days=(3 - date.today().weekday()) % 7)   # jueves del corte: el de hoy o el próximo, el que cierra la semana en curso
# Títulos de los issues: los trae sync-linear.mjs al bloque LINEAR del Gantt (linear-issues.csv no guarda texto).
_lin = (ROOT / 'leadership' / 'gantt.html').read_text(encoding='utf-8')
_i = _lin.index('\n  issues: ', _lin.index('// linear-begin')) + len('\n  issues: ')
TITLE = {k: v['t'] for k, v in json.loads(_lin[_i:_lin.index('\n', _i)].rstrip(',')).items()}
rows = []
with io.open(ACT_CSV, encoding='utf-8') as f:
    for r in csv.DictReader(f):
        pre = r['wbs'].split()
        pkgs = [k for k in TASKS if any(k == p or k.startswith(p + '.') for p in pre)]
        assert pkgs, f'actividad sin paquetes: {r["actividad"]} ({r["wbs"]})'
        ns = sorted({n for k in pkgs for n in PKG_TICKETS.get(k, []) if TICKETS[n]['type'] != 'canceled'})
        ts = [TICKETS[n] for n in ns]
        tot, hechos = sum(x['pts'] for x in ts), sum(x['pts'] for x in ts if x['type'] == 'completed')
        calc = round(100 * hechos / tot) if tot else 0
        detalle = [[f'SPO-{n}', TITLE.get(f'SPO-{n}', ''), TICKETS[n]['status'], TICKETS[n]['type'], TICKETS[n]['pts']] for n in ns]
        avance = int(r['avance']) if r['avance'] else calc
        estado = r['estado'] or ('Finaliz.' if avance == 100 else 'En curso' if avance or any(x['started'] for x in ts) else 'Pend.')
        base = D(r['fin_base'])
        real = None
        if estado == 'Finaliz.':
            real = max([art(x['completed']) for x in ts if x['completed']] or [wend(sched[k]['ew']) for k in pkgs if k in sched] or [None])
        # Lo pendiente termina cuando lo ubica el planificador, nunca antes del cierre de esta semana.
        # Sin paquetes de desarrollo (8.2, 8.3) no hay planificador: queda la línea base.
        planned = [wend(sched[k]['ew']) for k in pkgs if k in sched]
        est = real or (max(planned + [wend(this_week)]) if planned else base)
        rows.append({'actividad': r['actividad'], 'wbs': r['wbs'], 'estado': estado, 'avance': avance, 'base': F(base),
                     'estimado': F(est), 'real': F(real), 'desvio': (base - real).days if real else None,
                     'calc': calc, 'detalle': detalle})

steer = ROOT / 'leadership' / 'steering.html'
html = steer.read_text(encoding='utf-8')
a, b = html.index('// actividades-begin'), html.index('// actividades-end')
a = html.index('\n', a) + 1
old = html[a:b].strip()
hist = json.loads(old[len('const ACTIVIDADES = '):-1]) if old else {}
hist[f'{cut}'] = rows
out = ['const ACTIVIDADES = {']
for i, (k, rs) in enumerate(sorted(hist.items())):
    out += [f'{J(k)}: [', ',\n'.join(' ' + J(x) for x in rs), ']' + (',' if i < len(hist) - 1 else '')]
out.append('};')
steer.write_text(html[:a] + '\n'.join(out) + '\n' + html[b:], encoding='utf-8')
print(f'actividades clave: snapshot {cut:%d/%m} · ' + ' · '.join(f'{x["actividad"]} {x["avance"]} %' for x in rows))
