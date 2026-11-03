// Chequeos de layout para correr dentro de la página (page.evaluate o la consola del navegador).
// Uso: page.evaluate(chequeosLayout, { minControl: 44 })
// Devuelve un JSON con los problemas medibles del viewport actual. No modifica la página.

function chequeosLayout({ minControl = 44, maxItems = 30 } = {}) {
  const vw = document.documentElement.clientWidth;
  const vh = window.innerHeight;

  const visible = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  const describir = (el) => {
    const r = el.getBoundingClientRect();
    const clases = typeof el.className === 'string' ? el.className.trim().split(/\s+/).slice(0, 6).join(' ') : '';
    return {
      tag: el.tagName.toLowerCase(),
      id: el.id || undefined,
      clases: clases || undefined,
      texto: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 60) || undefined,
      caja: { x: Math.round(r.left), y: Math.round(r.top + window.scrollY), w: Math.round(r.width), h: Math.round(r.height) },
    };
  };

  // Un elemento cuenta si su padre no lo recorta (overflow) a propósito.
  const recortadoPorAncestro = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (/(hidden|auto|scroll|clip)/.test(s.overflowX)) return true;
    }
    return false;
  };

  const todos = Array.from(document.body.querySelectorAll('*')).filter(visible);
  const interactivos = todos.filter((el) =>
    el.matches('a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link], [tabindex]:not([tabindex="-1"])'),
  );

  const overflowPx = document.documentElement.scrollWidth - vw;

  const fueraDePantalla = todos
    .filter((el) => {
      const r = el.getBoundingClientRect();
      return (r.right > vw + 1 || r.left < -1) && !recortadoPorAncestro(el);
    })
    // quedarse con los elementos más externos para no repetir hijos
    .filter((el, _, arr) => !arr.some((otro) => otro !== el && otro.contains(el)))
    .slice(0, maxItems)
    .map(describir);

  const controlesChicos = interactivos
    .filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width < minControl || r.height < minControl;
    })
    .slice(0, maxItems)
    .map((el) => ({ ...describir(el), minimo: minControl }));

  const textoCortado = todos
    .filter((el) => {
      if (!el.childNodes.length || !Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim())) return false;
      const s = getComputedStyle(el);
      const recorta = /(hidden|clip)/.test(s.overflow + s.overflowX + s.overflowY);
      return recorta && (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1);
    })
    .slice(0, maxItems)
    .map((el) => ({ ...describir(el), conElipsis: getComputedStyle(el).textOverflow === 'ellipsis' }));

  const superpuestos = [];
  for (let i = 0; i < interactivos.length && superpuestos.length < maxItems; i++) {
    const a = interactivos[i].getBoundingClientRect();
    for (let j = i + 1; j < interactivos.length; j++) {
      if (interactivos[i].contains(interactivos[j]) || interactivos[j].contains(interactivos[i])) continue;
      const b = interactivos[j].getBoundingClientRect();
      const ancho = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const alto = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ancho > 4 && alto > 4) {
        superpuestos.push({ a: describir(interactivos[i]), b: describir(interactivos[j]) });
        break;
      }
    }
  }

  const fijosQueTapan = todos
    .filter((el) => {
      const pos = getComputedStyle(el).position;
      if (pos !== 'fixed' && pos !== 'sticky') return false;
      const r = el.getBoundingClientRect();
      const altoVisible = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
      return altoVisible / vh > 0.25 && r.width / vw > 0.5;
    })
    .slice(0, maxItems)
    .map((el) => ({ ...describir(el), porcentajeAlto: Math.round((el.getBoundingClientRect().height / vh) * 100) }));

  return {
    viewport: { ancho: vw, alto: vh },
    url: location.pathname,
    overflowX: { hay: overflowPx > 1, sobranPx: Math.max(0, overflowPx) },
    fueraDePantalla,
    controlesChicos,
    textoCortado,
    superpuestos,
    fijosQueTapan,
  };
}

if (typeof module !== 'undefined') module.exports = { chequeosLayout };
