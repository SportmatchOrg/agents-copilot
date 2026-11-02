#!/usr/bin/env node
/**
 * Sincroniza el team SPO de Linear con la WBS v5. Ver docs/planning/plan-linear.md.
 *
 *   node --env-file=.env.local scripts/sync-linear.mjs           revisa, reporta y actualiza el repo
 *   node --env-file=.env.local scripts/sync-linear.mjs --push     además escribe en Linear
 *   node --env-file=.env.local scripts/sync-linear.mjs --corte    Todo, In Progress e In Review cuentan como Done
 *                                                                  (sólo en el repo, para el corte semanal)
 *
 * Entradas
 *   docs/planning/linear-wbs-map.csv          issue -> paquete de la WBS (a mano)
 *   docs/planning/WBS-SportMatch-v5.md        los 131 paquetes válidos
 *
 * Salidas
 *   docs/planning/linear-issues.csv           estado, puntos y fechas reales (lo lee generate-v4.py)
 *   leadership/gantt.html                     bloque LINEAR entre marcadores
 *   docs/planning/linear-wbs-map.csv          se le agregan los issues nuevos, sin paquete
 *
 * Con --push, y sólo eso: crea los milestones que falten, suma al proyecto los issues sueltos
 * y le pone milestone a los que no tienen. Nunca pisa un milestone ya puesto a mano (decisión 5).
 */
import { readFileSync, writeFileSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const MAP_CSV = new URL('docs/planning/linear-wbs-map.csv', root);
const ISSUES_CSV = new URL('docs/planning/linear-issues.csv', root);
const GANTT = new URL('leadership/gantt.html', root);
const WBS_MD = new URL('docs/planning/WBS-SportMatch-v5.md', root);

const TEAM = 'SPO';
const PROJECT_NAME = 'SportMatch';
const PUSH = process.argv.includes('--push');
const CORTE = process.argv.includes('--corte');

// Épica -> nombre y fecha objetivo del milestone. Las épicas 1 y 2 no llevan (decisión 4).
const MILESTONES = {
  3: ['Capacitación y Setup', '2026-09-03'],
  4: ['Autenticación', '2026-09-17'],
  5: ['Perfil de Usuario', '2026-10-15'],
  6: ['Gestión de Partidos', '2026-10-29'],
  7: ['Sistema de Matchmaking', '2026-10-15'],
  8: ['QA Manual y Validación', '2026-11-05'],
  9: ['Deployment', '2026-09-03'],
  10: ['Documentación Final', '2026-10-29'],
  11: ['Notificaciones', '2026-10-29'],
  12: ['Moderación y Reportes', '2026-11-05'],
  13: ['Challenge', '2026-10-14'],
};
const msName = (epic) => `${epic} · ${MILESTONES[epic][0]}`;

const DESCRIPTION =
  'App para encontrar partidos de fútbol, básquet y tenis cerca tuyo, sumarte con un swipe y organizar los tuyos.';
const CONTENT = `SportMatch conecta jugadores con partidos abiertos cerca suyo. El jugador descubre partidos por mapa o por swipe, pide sumarse, y el organizador arma y gestiona el suyo. Después del partido, las calificaciones y el registro de faltas mantienen la comunidad sana.

Proyecto de la materia Dirección de Proyectos (Equipo 11 · Austral). El desarrollo va de agosto a noviembre de 2026, con tres devs a 6 h por semana cada uno, en sprints de jueves a jueves. Cada milestone es una épica de la WBS v4; el detalle de paquetes, cronograma y camino crítico está en las vistas de leadership.`;

/* ─────────────────────────── API ─────────────────────────── */

const KEY = process.env.LINEAR_API_KEY;
if (!KEY) {
  console.error('Falta LINEAR_API_KEY. Corré con: node --env-file=.env.local scripts/sync-linear.mjs');
  process.exit(1);
}

async function gql(query, variables = {}) {
  const res = await fetch('https://api.linear.app/graphql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: KEY },
    body: JSON.stringify({ query, variables }),
  });
  const body = await res.json();
  if (body.errors) throw new Error(body.errors.map((e) => e.message).join(' · '));
  return body.data;
}

const ISSUE_FIELDS = `
  identifier title url estimate startedAt completedAt
  state { name type }
  assignee { displayName }
  parent { identifier }
  project { id name }
  projectMilestone { id name }`;

async function fetchIssues() {
  const out = [];
  let cursor = null;
  do {
    const data = await gql(
      `query($c:String){ issues(first:250, after:$c, filter:{team:{key:{eq:"${TEAM}"}}}) {
         pageInfo { hasNextPage endCursor } nodes { ${ISSUE_FIELDS} } } }`,
      { c: cursor },
    );
    out.push(...data.issues.nodes);
    cursor = data.issues.pageInfo.hasNextPage ? data.issues.pageInfo.endCursor : null;
  } while (cursor);
  return out.sort((a, b) => num(a.identifier) - num(b.identifier));
}

const num = (id) => Number(id.split('-')[1]);

async function fetchProject() {
  const { projects } = await gql(
    `{ projects(filter:{name:{eq:"${PROJECT_NAME}"}}) { nodes {
         id name description content projectMilestones { nodes { id name targetDate } } } } }`,
  );
  const p = projects.nodes[0];
  if (!p) throw new Error(`No existe el proyecto "${PROJECT_NAME}"`);
  return p;
}

/* ─────────────────────────── CSV ─────────────────────────── */

/** CSV mínimo: ninguna de las dos tablas guarda texto libre, así que no hay comas que escapar. */
function readCsv(url) {
  let text;
  try {
    text = readFileSync(url, 'utf8');
  } catch {
    return [];
  }
  const [head, ...lines] = text.trim().split(/\r?\n/);
  const cols = head.split(',');
  return lines.filter(Boolean).map((l) => Object.fromEntries(l.split(',').map((v, i) => [cols[i], v])));
}

function writeCsv(url, cols, rows) {
  const body = rows.map((r) => cols.map((c) => r[c] ?? '').join(',')).join('\n');
  writeFileSync(url, `${cols.join(',')}\n${body}\n`);
}

/* ─────────────────────────── datos ─────────────────────────── */

const wbsIds = new Set([...readFileSync(WBS_MD, 'utf8').matchAll(/^\*\*(\d+\.\d+\.\d+)\*\*/gm)].map((m) => m[1]));
const epicOf = (wbsId) => Number(wbsId.split('.')[0]);

const issues = await fetchIssues();
if (CORTE) {
  const now = new Date().toISOString();
  for (const i of issues.filter((i) => ['Todo', 'In Progress', 'In Review'].includes(i.state.name))) {
    i.state = { name: 'Done', type: 'completed' };
    i.startedAt ??= now;
    i.completedAt ??= now;
  }
}
const project = await fetchProject();
const byId = new Map(issues.map((i) => [i.identifier, i]));

// Mapa issue -> paquetes. Un sub-issue sin fila propia hereda las del padre.
const map = readCsv(MAP_CSV);
const rowsOf = new Map();
for (const r of map) {
  if (!rowsOf.has(r.issue)) rowsOf.set(r.issue, []);
  rowsOf.get(r.issue).push(r);
}
const packagesOf = (id) => {
  const own = rowsOf.get(id);
  if (own?.length) return own;
  const parent = byId.get(id)?.parent?.identifier;
  return parent ? rowsOf.get(parent) ?? [] : [];
};

/* ─────────────────────────── reporte ─────────────────────────── */

const problems = [];
const add = (label, list) => list.length && problems.push([label, list]);

add('sin paquete en el CSV', issues.filter((i) => packagesOf(i.identifier).length === 0).map((i) => i.identifier));
add('wbs_id que no existe en la WBS v5', map.filter((r) => r.wbs_id && !wbsIds.has(r.wbs_id)).map((r) => `${r.issue}→${r.wbs_id}`));
add('en el CSV pero ya no en Linear', [...rowsOf.keys()].filter((id) => !byId.has(id)));
add('sin proyecto', issues.filter((i) => !i.project).map((i) => i.identifier));
add('sin estimate', issues.filter((i) => i.estimate == null && i.state.type !== 'canceled').map((i) => i.identifier));
// Los paquetes de las épicas 1 y 2 no llevan milestone a propósito (decisión 4): no es un aviso.

// Milestone puesto a mano que no coincide con el CSV: se reporta y no se toca (decisión 5).
const mismatched = [];
for (const i of issues) {
  const pkg = packagesOf(i.identifier)[0];
  if (!pkg?.wbs_id || !i.projectMilestone) continue;
  const want = MILESTONES[epicOf(pkg.wbs_id)] && msName(epicOf(pkg.wbs_id));
  if (want && i.projectMilestone.name !== want) mismatched.push(`${i.identifier}: ${i.projectMilestone.name} ≠ ${want}`);
}
add('milestone distinto al del CSV (no se toca)', mismatched);

for (const [label, list] of problems) console.log(`⚠ ${list.length} ${label}:\n   ${list.join(', ')}`);
if (!problems.length) console.log('✓ Linear y el CSV coinciden');

/* ─────────────────────────── escribir en Linear ─────────────────────────── */

if (PUSH) {
  const have = new Map(project.projectMilestones.nodes.map((m) => [m.name, m]));
  for (const epic of Object.keys(MILESTONES).map(Number)) {
    if (have.has(msName(epic))) continue;
    const { projectMilestoneCreate } = await gql(
      `mutation($i:ProjectMilestoneCreateInput!){ projectMilestoneCreate(input:$i){ projectMilestone { id name } } }`,
      { i: { name: msName(epic), targetDate: MILESTONES[epic][1], projectId: project.id, sortOrder: epic } },
    );
    have.set(msName(epic), projectMilestoneCreate.projectMilestone);
    console.log(`+ milestone ${msName(epic)}`);
  }

  if (!project.description && !project.content) {
    await gql(`mutation($id:String!,$i:ProjectUpdateInput!){ projectUpdate(id:$id, input:$i){ success } }`, {
      id: project.id,
      i: { description: DESCRIPTION, content: CONTENT },
    });
    console.log('+ descripción del proyecto');
  }

  for (const i of issues) {
    const pkg = packagesOf(i.identifier)[0];
    const epic = pkg?.wbs_id ? epicOf(pkg.wbs_id) : null;
    const milestone = epic && MILESTONES[epic] ? have.get(msName(epic)) : null;
    const input = {};
    if (!i.project) input.projectId = project.id;
    if (milestone && !i.projectMilestone) input.projectMilestoneId = milestone.id;
    if (!Object.keys(input).length) continue;
    await gql(`mutation($id:String!,$i:IssueUpdateInput!){ issueUpdate(id:$id, input:$i){ success } }`, {
      id: i.identifier,
      i: input,
    });
    console.log(`· ${i.identifier}${input.projectId ? ' → proyecto' : ''}${input.projectMilestoneId ? ` → ${msName(epic)}` : ''}`);
  }
}

/* ─────────────────────────── escribir en el repo ─────────────────────────── */

const iso = (t) => (t ? t.slice(0, 19) : '');
writeCsv(
  ISSUES_CSV,
  ['issue', 'status', 'type', 'estimate', 'started', 'completed', 'assignee'],
  issues.map((i) => ({
    issue: i.identifier,
    status: i.state.name,
    type: i.state.type,
    estimate: i.estimate ?? '',
    started: iso(i.startedAt),
    completed: iso(i.completedAt),
    assignee: i.assignee?.displayName ?? '',
  })),
);

// Los issues nuevos entran al mapa sin paquete, para que se completen a mano.
const nuevos = issues.filter((i) => !rowsOf.has(i.identifier) && !i.parent);
if (nuevos.length) {
  writeCsv(
    MAP_CSV,
    ['issue', 'wbs_id', 'fechas', 'url'],
    // Ordena por issue y nada más: el orden de las filas de un mismo issue es a mano,
    // porque la primera es su paquete principal, del que sale el milestone.
    [...map, ...nuevos.map((i) => ({ issue: i.identifier, wbs_id: '', fechas: 'si', url: i.url }))].sort(
      (a, b) => num(a.issue) - num(b.issue),
    ),
  );
  console.log(`+ ${nuevos.length} issues nuevos en el mapa, sin paquete`);
}

// Bloque para el Gantt: sólo lo que el panel muestra.
const byPkg = {};
const shown = {};
for (const i of issues) {
  if (i.state.type === 'canceled') continue;
  for (const r of packagesOf(i.identifier)) {
    if (!r.wbs_id) continue;
    (byPkg[r.wbs_id] ??= []).push(i.identifier);
    shown[i.identifier] = {
      t: i.title,
      s: i.state.name,
      k: i.state.type,
      e: i.estimate ?? 0,
      u: i.url,
      a: i.assignee?.displayName ?? '',
    };
  }
}
const block = `// linear-begin — generado por scripts/sync-linear.mjs el ${new Date().toISOString().slice(0, 10)}
const LINEAR = {
  syncedAt: ${JSON.stringify(new Date().toISOString())},
  milestones: ${JSON.stringify(Object.fromEntries(Object.keys(MILESTONES).map((e) => [e, msName(Number(e))])))},
  issues: ${JSON.stringify(shown)},
  byPkg: ${JSON.stringify(byPkg)}
};
// linear-end`;
const html = readFileSync(GANTT, 'utf8');
const start = html.indexOf('// linear-begin');
const end = html.indexOf('// linear-end');
if (start === -1 || end === -1) throw new Error('Faltan los marcadores linear-begin/linear-end en gantt.html');
writeFileSync(GANTT, html.slice(0, start) + block + html.slice(end + '// linear-end'.length));

console.log(
  `✓ ${issues.length} issues · ${Object.keys(byPkg).length} paquetes con tickets · linear-issues.csv y gantt.html actualizados`,
);
