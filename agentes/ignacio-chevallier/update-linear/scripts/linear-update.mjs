#!/usr/bin/env node
/**
 * Datos del update semanal del proyecto en Linear. Ver roles/pm/skills/update-linear/SKILL.md.
 *
 *   node scripts/linear-update.mjs                                               imprime los datos
 *   node --env-file=.env.local scripts/linear-update.mjs --post update.md --health atRisk   publica
 *
 * Lee lo que dejó /sincronizar-linear: docs/planning/linear-issues.csv y el último snapshot de
 * actividades clave de leadership/steering.html. No llama a Linear salvo con --post.
 */
import { readFileSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');
const HEALTH = ['onTrack', 'atRisk', 'offTrack'];
const arg = (name) => process.argv[process.argv.indexOf(name) + 1];

if (process.argv.includes('--post')) {
  const health = arg('--health');
  if (!HEALTH.includes(health)) throw new Error(`--health tiene que ser ${HEALTH.join(' | ')}`);
  if (!process.env.LINEAR_API_KEY) throw new Error('Falta LINEAR_API_KEY: correr con --env-file=.env.local');
  const gql = async (query, variables) => {
    const res = await fetch('https://api.linear.app/graphql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: process.env.LINEAR_API_KEY },
      body: JSON.stringify({ query, variables }),
    });
    const body = await res.json();
    if (body.errors) throw new Error(body.errors.map((e) => e.message).join(' · '));
    return body.data;
  };
  const { projects } = await gql(`{ projects(filter:{name:{eq:"SportMatch"}}) { nodes { id } } }`);
  const { projectUpdateCreate } = await gql(
    `mutation($i:ProjectUpdateCreateInput!){ projectUpdateCreate(input:$i){ projectUpdate { url } } }`,
    { i: { projectId: projects.nodes[0].id, body: readFileSync(arg('--post'), 'utf8'), health } },
  );
  console.log(projectUpdateCreate.projectUpdate.url);
  process.exit(0);
}

const [head, ...lines] = read('docs/planning/linear-issues.csv').trim().split('\n');
const cols = head.split(',');
const issues = lines
  .map((line) => Object.fromEntries(line.split(',').map((v, i) => [cols[i], v])))
  .filter((i) => i.type !== 'canceled' && i.status !== 'Duplicate');
const pts = (list) => list.reduce((sum, i) => sum + Number(i.estimate || 0), 0);
const done = issues.filter((i) => i.type === 'completed');

const html = read('leadership/steering.html');
const block = html.slice(html.indexOf('actividades-begin'), html.indexOf('actividades-end'));
const snapshots = JSON.parse(block.slice(block.indexOf('{'), block.lastIndexOf('}') + 1));
const [prevDate, curDate] = Object.keys(snapshots).sort().slice(-2);
const prev = new Map((snapshots[prevDate] ?? []).map((a) => [a.actividad, a]));
const week = done.filter((i) => i.completed >= prevDate);

console.log(`Snapshot ${curDate} (anterior ${prevDate ?? '—'})`);
console.log(`Alcance: ${pts(done)}/${pts(issues)} pts (${Math.round((100 * pts(done)) / pts(issues))} %) · ${done.length}/${issues.length} issues`);
console.log(`Cerrados en la semana: ${week.length} issues, ${pts(week)} pts`);
console.log('\nactividad | estado | avance (sem. ant.) | base | estimado/real | desvío  (debajo, sus issues abiertos)');
for (const a of snapshots[curDate]) {
  const before = prev.get(a.actividad);
  const open = a.detalle
    .filter(([, , , type]) => type !== 'completed' && type !== 'canceled')
    .map(([id, title, status]) => `${id} [${status}] ${title}`);
  const closedNow = a.estado === 'Finaliz.' && before?.estado !== 'Finaliz.' ? ' · CERRÓ ESTA SEMANA' : '';
  console.log(
    `${a.actividad} | ${a.estado}${closedNow} | ${a.avance} % (${before?.avance ?? '—'}) | ${a.base} | ${a.real || a.estimado} | ${a.desvio ?? '—'}`,
  );
  for (const o of open) console.log(`    ${o}`);
}
