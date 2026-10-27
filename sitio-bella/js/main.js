/* ==========================================================================
   Studio Bella · sitio web de venta
   Comportamiento compartido por todas las páginas.
   ========================================================================== */

/* Datos de contacto: cambialos acá y se actualizan en todo el sitio. */
const CONFIG = {
  whatsapp: '595982600740',            // número para wa.me, sin "+" ni espacios
  telefono: '+595 982 600 740',        // como se muestra en pantalla
  email: 'albamariafarinamoran@gmail.com',
  direccion: 'Asunción, Paraguay',
  // Odoo que guarda las solicitudes del formulario en el CRM (servicio "ventas" de docker-compose).
  // Al publicar el sitio, tiene que ser una dirección https accesible desde internet.
  odoo: 'http://localhost:8070',
  mensajeWhatsapp: 'Hola, quiero conocer Studio Bella para mi peluquería.',
  // Producto que se manda al CRM con cada solicitud (el mismo CRM recibe las de AutoFlow).
  producto: 'studio_bella',
};

/* Íconos (trazos de 24×24). Se insertan una sola vez como <symbol> y se usan con
   <svg class="ico"><use href="#i-nombre"></use></svg>. */
const ICONOS = {
  auto: '<path d="M5 17H3v-4.5c0-.6.4-1.1 1-1.3l1.6-.4L7.7 6.6A2 2 0 0 1 9.5 5.5h5a2 2 0 0 1 1.8 1.1l2.1 4.2 1.6.4c.6.2 1 .7 1 1.3V17h-2"/><circle cx="7.5" cy="17" r="2"/><circle cx="16.5" cy="17" r="2"/><path d="M9.5 17h5M6 11h12"/>',
  llave: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  calendario: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>',
  volante: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2"/><path d="M12 14v7M10 12H3.5M14 12h6.5"/>',
  caja: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
  factura: '<path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6M9 13h7M9 17h7M9 9h2"/>',
  grafico: '<path d="M3 21h18"/><rect x="5" y="11" width="3" height="7" rx="1"/><rect x="10.5" y="7" width="3" height="11" rx="1"/><rect x="16" y="3" width="3" height="15" rx="1"/>',
  escudo: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
  sobre: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  reloj: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  'check-circulo': '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  flecha: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  'flecha-izq': '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  'x-circulo': '<circle cx="12" cy="12" r="9"/><path d="m15 9-6 6M9 9l6 6"/>',
  whatsapp: '<path d="M20.5 11.7a8.5 8.5 0 0 1-12.6 7.5L3.5 20.5l1.3-4.2a8.5 8.5 0 1 1 15.7-4.6z"/><path d="M9 8.5c.2-.4.5-.5.8-.5h.6l1 2.2-.7.9c.5 1.1 1.4 2 2.5 2.5l.9-.7 2.2 1v.6c0 .3-.1.6-.5.8-.6.4-1.5.6-2.6.2a7 7 0 0 1-4.3-4.3c-.4-1.1-.2-2 .1-2.7z"/>',
  telefono: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>',
  ubicacion: '<path d="M12 22s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/>',
  usuarios: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/>',
  combustible: '<path d="M4 21V5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v16M3 21h13M4 10h11"/><path d="M15 8h2a2 2 0 0 1 2 2v6a1.5 1.5 0 0 0 3 0V8l-3-3"/>',
  lista: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 12l2 2 4-4"/>',
  firma: '<path d="M3 21c3 0 4-3 6-3s2 2 4 2 3-2 5-2"/><path d="M14.5 3.5a2.1 2.1 0 0 1 3 3L8 16l-4 1 1-4z"/>',
  ajustes: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  estrella: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3l-5.5 2.9 1-6.2L3 9.6l6.2-.9z"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  'chevron-izq': '<path d="m15 18-6-6 6-6"/>',
  'chevron-der': '<path d="m9 18 6-6-6-6"/>',
  play: '<path d="M7 4v16l13-8z"/>',
  rayo: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  candado: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  nube: '<path d="M7 18a5 5 0 1 1 1-9.9A6 6 0 0 1 19 10a4 4 0 0 1 0 8z"/>',
  soporte: '<path d="M4 14v-2a8 8 0 0 1 16 0v2"/><rect x="2" y="14" width="5" height="6" rx="2"/><rect x="17" y="14" width="5" height="6" rx="2"/><path d="M20 20c0 1-1 2-3 2h-3"/>',
  alerta: '<path d="M12 3 2 21h20z"/><path d="M12 10v5M12 18h.01"/>',
  planilla: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>',
  tienda: '<path d="m3 9 2-5h14l2 5M3 9v11h18V9M3 9h18"/><path d="M9 20v-6h6v6"/>',
  arriba: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  mas: '<path d="M12 5v14M5 12h14"/>',
  reiniciar: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  lupa: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  ampliar: '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',
  impresora: '<path d="M6 9V2h12v7"/><rect x="2" y="9" width="20" height="8" rx="2"/><path d="M6 14h12v8H6z"/>',
  dinero: '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 12h.01M18 12h.01"/>',
  telefono2: '<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/>',
  odometro: '<path d="M4.9 19a9 9 0 1 1 14.2 0"/><path d="m12 13 4-5"/><circle cx="12" cy="13" r="1.5"/>',
  mensaje: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  ojo: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  copiar: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/>',
  tijeras: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.12 15.88M14.47 14.48 20 20M8.12 8.12 12 12"/>',
  gota: '<path d="M12 2.7c3 3.6 6 7 6 10.3a6 6 0 0 1-12 0c0-3.3 3-6.7 6-10.3z"/>',
  chispas: '<path d="m12 3 1.8 4.7 4.7 1.8-4.7 1.8L12 16l-1.8-4.7-4.7-1.8 4.7-1.8z"/><path d="m19 15 .8 2.2 2.2.8-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  campana: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  corazon: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z"/>',
  camion: '<path d="M3 6h11v10H3zM14 9h4l3 3v4h-7"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
  libro: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/>',
};

(function insertarIconos() {
  const simbolos = Object.entries(ICONOS)
    .map(([nombre, trazo]) => `<symbol id="i-${nombre}" viewBox="0 0 24 24">${trazo}</symbol>`)
    .join('');
  const contenedor = document.createElement('div');
  contenedor.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true">${simbolos}</svg>`;
  document.body.prepend(contenedor.firstChild);
})();

const formatoGs = new Intl.NumberFormat('es-PY', { maximumFractionDigits: 0 });
const gs = (n) => formatoGs.format(Math.round(n));
const icono = (nombre) => `<svg class="ico" aria-hidden="true"><use href="#i-${nombre}"></use></svg>`;

/* ---------- Avisos emergentes ---------- */

function aviso(tipo, titulo, texto = '', duracion = 4200) {
  let pila = document.querySelector('.avisos');
  if (!pila) {
    pila = document.createElement('div');
    pila.className = 'avisos';
    pila.setAttribute('role', 'status');
    pila.setAttribute('aria-live', 'polite');
    document.body.append(pila);
  }
  const iconoTipo = { exito: 'check-circulo', error: 'alerta', info: 'mensaje' }[tipo] || 'mensaje';
  const el = document.createElement('div');
  el.className = `aviso aviso--${tipo}`;
  el.innerHTML = `${icono(iconoTipo)}<div><b></b><span></span></div>`;
  el.querySelector('b').textContent = titulo;
  el.querySelector('span').textContent = texto;
  pila.append(el);
  setTimeout(() => {
    el.classList.add('saliendo');
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }, duracion);
}

window.StudioBella = { aviso, gs, icono, CONFIG, enlaceWhatsapp };

/* ---------- Datos de contacto en enlaces y textos ---------- */

function enlaceWhatsapp(texto) {
  return `https://wa.me/${CONFIG.whatsapp}?text=${encodeURIComponent(texto || CONFIG.mensajeWhatsapp)}`;
}

const enlaceLlamada = `tel:${CONFIG.telefono.replace(/[^\d+]/g, '')}`;
const esCelular = window.matchMedia('(pointer: coarse)').matches;

document.querySelectorAll('[data-contacto]').forEach((el) => {
  const tipo = el.dataset.contacto;
  if (tipo === 'whatsapp') {
    el.href = enlaceWhatsapp(el.dataset.mensaje);
    el.target = '_blank';
    el.rel = 'noopener';
  } else if (tipo === 'email') {
    el.href = `mailto:${CONFIG.email}?subject=${encodeURIComponent('Consulta sobre Studio Bella')}`;
  } else if (tipo === 'telefono') {
    // En el celular abre el marcador. En la computadora "tel:" no suele hacer nada,
    // así que lleva a la página llamar/ con el número para copiarlo o escribir por WhatsApp.
    el.href = esCelular ? enlaceLlamada : 'llamar/index.html';
  } else if (tipo === 'llamada') {
    el.href = enlaceLlamada;
  }
});

document.querySelectorAll('[data-copiar]').forEach((boton) => {
  boton.addEventListener('click', async () => {
    const texto = CONFIG[boton.dataset.copiar];
    try {
      await navigator.clipboard.writeText(texto);
    } catch {
      // Sin acceso al portapapeles (por ejemplo, abierto con doble clic): se copia a la antigua.
      const area = Object.assign(document.createElement('textarea'), { value: texto });
      document.body.append(area);
      area.select();
      document.execCommand('copy');
      area.remove();
    }
    aviso('exito', 'Número copiado', `${texto} ya está listo para pegar.`);
  });
});
document.querySelectorAll('[data-texto]').forEach((el) => {
  const valor = CONFIG[el.dataset.texto];
  if (valor) el.textContent = valor;
});
document.querySelectorAll('[data-anio]').forEach((el) => { el.textContent = new Date().getFullYear(); });

/* ---------- Cabecera y menú del celular ---------- */

const cabecera = document.querySelector('.cabecera');
const menu = document.getElementById('menu');
const hamburguesa = document.querySelector('.hamburguesa');
const botonArriba = document.querySelector('.boton-redondo--arriba');

function alHacerScroll() {
  const y = window.scrollY;
  cabecera?.classList.toggle('cabecera--fija', y > 10);
  botonArriba?.classList.toggle('visible', y > 700);
}
window.addEventListener('scroll', alHacerScroll, { passive: true });
alHacerScroll();

function cerrarMenu() {
  if (!menu) return;
  menu.classList.remove('menu--abierto');
  cabecera.classList.remove('cabecera--menu-abierto');
  hamburguesa?.setAttribute('aria-expanded', 'false');
  hamburguesa?.setAttribute('aria-label', 'Abrir menú');
}

hamburguesa?.addEventListener('click', () => {
  const abrir = !menu.classList.contains('menu--abierto');
  menu.classList.toggle('menu--abierto', abrir);
  cabecera.classList.toggle('cabecera--menu-abierto', abrir);
  hamburguesa.setAttribute('aria-expanded', String(abrir));
  hamburguesa.setAttribute('aria-label', abrir ? 'Cerrar menú' : 'Abrir menú');
});
menu?.querySelectorAll('a').forEach((a) => a.addEventListener('click', cerrarMenu));
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') cerrarMenu(); });
document.addEventListener('click', (e) => {
  if (menu?.classList.contains('menu--abierto') && !cabecera.contains(e.target)) cerrarMenu();
});
window.addEventListener('resize', () => { if (window.innerWidth > 900) cerrarMenu(); });

botonArriba?.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

/* ---------- Animación al aparecer y contadores ---------- */

function animarContador(el) {
  const fin = Number(el.dataset.contar);
  const sufijo = el.dataset.sufijo || '';
  const duracion = 1400;
  const inicio = performance.now();
  const paso = (ahora) => {
    const t = Math.min(1, (ahora - inicio) / duracion);
    const suave = 1 - Math.pow(1 - t, 3);
    el.textContent = gs(fin * suave) + sufijo;
    if (t < 1) requestAnimationFrame(paso);
  };
  requestAnimationFrame(paso);
}

const aRevelar = document.querySelectorAll('[data-revelar], [data-contar]');
document.querySelectorAll('[data-retraso]').forEach((el) => el.style.setProperty('--retraso', `${el.dataset.retraso}ms`));

if ('IntersectionObserver' in window) {
  const observador = new IntersectionObserver((entradas) => {
    entradas.forEach((entrada) => {
      if (!entrada.isIntersecting) return;
      const el = entrada.target;
      el.classList.add('visible');
      if (el.dataset.contar) animarContador(el);
      observador.unobserve(el);
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
  aRevelar.forEach((el) => observador.observe(el));
} else {
  aRevelar.forEach((el) => {
    el.classList.add('visible');
    if (el.dataset.contar) el.textContent = gs(Number(el.dataset.contar)) + (el.dataset.sufijo || '');
  });
}

/* ---------- Pestañas (galería y "cómo funciona") ---------- */

document.querySelectorAll('[data-pestanas]').forEach((grupo) => {
  const botones = [...grupo.querySelectorAll('[role="tab"]')];
  const progreso = grupo.hasAttribute('data-progreso');

  function seleccionar(indice, enfocar = false) {
    indice = (indice + botones.length) % botones.length;
    botones.forEach((b, i) => {
      const activo = i === indice;
      b.setAttribute('aria-selected', String(activo));
      b.tabIndex = activo ? 0 : -1;
      if (progreso) b.classList.toggle('paso--hecho', i < indice);
      const panel = document.getElementById(b.getAttribute('aria-controls'));
      if (panel) panel.hidden = !activo;
    });
    if (enfocar) botones[indice].focus();
    botones[indice].scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  botones.forEach((b, i) => {
    b.addEventListener('click', () => seleccionar(i));
    b.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') { e.preventDefault(); seleccionar(i + 1, true); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); seleccionar(i - 1, true); }
    });
  });
  grupo.querySelectorAll('[data-ir]').forEach((b) => {
    b.addEventListener('click', () => {
      const actual = botones.findIndex((x) => x.getAttribute('aria-selected') === 'true');
      seleccionar(actual + Number(b.dataset.ir));
    });
  });
});

/* ---------- Visor de capturas ---------- */

const disparadoresVisor = [...document.querySelectorAll('[data-visor]')];
if (disparadoresVisor.length) {
  const visor = document.createElement('div');
  visor.className = 'visor';
  visor.setAttribute('role', 'dialog');
  visor.setAttribute('aria-modal', 'true');
  visor.setAttribute('aria-label', 'Captura del sistema');
  visor.innerHTML = `
    <div class="visor__cabeza">
      <span class="visor__titulo"><span data-v="titulo"></span><span class="visor__contador" data-v="contador"></span></span>
      <button type="button" data-v="cerrar" aria-label="Cerrar">${icono('x')}</button>
    </div>
    <div class="visor__cuerpo"><img alt="" data-v="img"></div>
    <div class="visor__pie">
      <button type="button" data-v="anterior" aria-label="Anterior">${icono('chevron-izq')}</button>
      <button type="button" data-v="siguiente" aria-label="Siguiente">${icono('chevron-der')}</button>
    </div>`;
  document.body.append(visor);
  const v = (nombre) => visor.querySelector(`[data-v="${nombre}"]`);
  let lista = [];
  let actual = 0;
  let anteriorFoco = null;

  function mostrar(i) {
    actual = (i + lista.length) % lista.length;
    const el = lista[actual];
    const img = v('img');
    img.src = el.dataset.visor;
    img.alt = el.dataset.titulo || '';
    img.classList.toggle('alta', el.hasAttribute('data-alta'));
    visor.querySelector('.visor__cuerpo').scrollTop = 0;
    v('titulo').textContent = el.dataset.titulo || '';
    v('contador').textContent = lista.length > 1 ? `${actual + 1} / ${lista.length}` : '';
    v('anterior').hidden = v('siguiente').hidden = lista.length < 2;
  }
  function abrir(el) {
    const grupo = el.dataset.grupo || 'general';
    lista = disparadoresVisor.filter((x) => (x.dataset.grupo || 'general') === grupo);
    anteriorFoco = document.activeElement;
    mostrar(lista.indexOf(el));
    visor.classList.add('abierto');
    document.body.style.overflow = 'hidden';
    v('cerrar').focus();
  }
  function cerrar() {
    visor.classList.remove('abierto');
    document.body.style.overflow = '';
    anteriorFoco?.focus();
  }

  disparadoresVisor.forEach((el) => el.addEventListener('click', () => abrir(el)));
  v('cerrar').addEventListener('click', cerrar);
  v('anterior').addEventListener('click', () => mostrar(actual - 1));
  v('siguiente').addEventListener('click', () => mostrar(actual + 1));
  visor.addEventListener('click', (e) => { if (e.target === visor || e.target.classList.contains('visor__cuerpo')) cerrar(); });
  document.addEventListener('keydown', (e) => {
    if (!visor.classList.contains('abierto')) return;
    if (e.key === 'Escape') cerrar();
    if (e.key === 'ArrowRight') mostrar(actual + 1);
    if (e.key === 'ArrowLeft') mostrar(actual - 1);
    if (e.key === 'Tab') {  // el foco no sale del visor
      const focoables = [...visor.querySelectorAll('button:not([hidden])')];
      const i = focoables.indexOf(document.activeElement);
      e.preventDefault();
      focoables[(i + (e.shiftKey ? -1 : 1) + focoables.length) % focoables.length].focus();
    }
  });
  let toqueX = null;
  visor.addEventListener('touchstart', (e) => { toqueX = e.touches[0].clientX; }, { passive: true });
  visor.addEventListener('touchend', (e) => {
    if (toqueX === null) return;
    const dx = e.changedTouches[0].clientX - toqueX;
    if (Math.abs(dx) > 60 && lista.length > 1) mostrar(actual + (dx < 0 ? 1 : -1));
    toqueX = null;
  });
}

/* ---------- Barras deslizantes con relleno ---------- */

function pintarRango(r) {
  const pct = ((r.value - r.min) / (r.max - r.min)) * 100;
  r.style.setProperty('--relleno', `${pct}%`);
}
document.querySelectorAll('input[type="range"]').forEach((r) => {
  pintarRango(r);
  r.addEventListener('input', () => pintarRango(r));
});

/* ---------- Calculadora de ahorro ---------- */

const calculadora = document.querySelector('[data-calculadora]');
if (calculadora) {
  const campo = (n) => calculadora.querySelector(`[name="${n}"]`);
  const salida = (n) => calculadora.querySelectorAll(`[data-salida="${n}"]`);
  const poner = (n, texto) => salida(n).forEach((el) => { el.textContent = texto; });

  function calcular() {
    const citas = Number(campo('citas').value);
    const faltan = Number(campo('faltan').value);
    const ticket = Number(campo('ticket').value);
    const evitadas = Number(campo('evitadas').value);
    const faltasMes = citas * faltan / 100;
    const recuperadas = faltasMes * evitadas / 100;

    poner('citas', gs(citas));
    poner('faltan', `${faltan} %`);
    poner('ticket', `Gs. ${gs(ticket)}`);
    poner('evitadas', `${evitadas} %`);
    poner('faltas', gs(faltasMes));
    poner('recuperadas', gs(recuperadas));
    poner('mes', `Gs. ${gs(recuperadas * ticket)}`);
    poner('anio', `Gs. ${gs(recuperadas * ticket * 12)}`);
  }
  calculadora.addEventListener('input', calcular);
  calcular();
}

/* ---------- Precios: mensual / anual ---------- */

const selectorPeriodo = document.querySelector('[data-periodo]');
if (selectorPeriodo) {
  const botones = selectorPeriodo.querySelectorAll('button');
  function aplicar(periodo) {
    botones.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.valor === periodo)));
    document.querySelectorAll('[data-precio-mensual]').forEach((plan) => {
      const mensual = Number(plan.dataset.precioMensual);
      const monto = plan.querySelector('.plan__monto');
      const nota = plan.querySelector('.plan__nota');
      if (periodo === 'anual') {
        const anual = mensual * 10;  // 12 meses por el precio de 10
        monto.textContent = gs(anual / 12);
        nota.textContent = `Gs. ${gs(anual)} por año · ahorrás Gs. ${gs(mensual * 2)}`;
      } else {
        monto.textContent = gs(mensual);
        nota.textContent = 'Sin permanencia: cancelás cuando quieras';
      }
    });
  }
  botones.forEach((b) => b.addEventListener('click', () => aplicar(b.dataset.valor)));
  aplicar('mensual');
}

/* ---------- Formulario de contacto ---------- */

const formulario = document.querySelector('[data-form-contacto]');
if (formulario) {
  const exito = document.querySelector('[data-exito]');
  const params = new URLSearchParams(location.search);
  const plan = params.get('plan');
  if (plan && formulario.plan.querySelector(`option[value="${plan}"]`)) formulario.plan.value = plan;
  if (params.get('origen') === 'demo') {
    formulario.mensaje.value = 'Probé la demo interactiva y quiero ver Studio Bella con los datos de mi peluquería.';
  }

  const reglas = {
    nombre: (v) => v.trim().length >= 3 || 'Escribí tu nombre y apellido.',
    empresa: (v) => v.trim().length >= 2 || 'Contanos el nombre de tu negocio.',
    telefono: (v) => v.replace(/\D/g, '').length >= 7 || 'Ingresá un teléfono válido (ej.: 0981 123 456).',
    email: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim()) || 'Ingresá un correo válido.',
    tipo: (v) => Boolean(v) || 'Elegí el tipo de negocio.',
    acepto: (_, el) => el.checked || 'Necesitamos tu permiso para contactarte.',
  };

  function validarCampo(nombre) {
    const el = formulario.elements[nombre];
    const valor = el instanceof RadioNodeList ? el.value : el.value;
    const control = el instanceof RadioNodeList ? el[0] : el;
    const resultado = reglas[nombre](valor, control);
    const contenedor = control.closest('.campo');
    const error = contenedor.querySelector('.campo__error');
    const ok = resultado === true;
    contenedor.classList.toggle('campo--error', !ok);
    error.textContent = ok ? '' : resultado;
    (el instanceof RadioNodeList ? [...el] : [el]).forEach((c) => c.setAttribute('aria-invalid', String(!ok)));
    return ok;
  }

  Object.keys(reglas).forEach((nombre) => {
    const el = formulario.elements[nombre];
    const controles = el instanceof RadioNodeList ? [...el] : [el];
    controles.forEach((c) => {
      c.addEventListener('change', () => validarCampo(nombre));
      if (c.type === 'radio' || c.type === 'checkbox') return;
      c.addEventListener('blur', () => {
        if (c.closest('.campo').classList.contains('campo--error') || c.value) validarCampo(nombre);
      });
      c.addEventListener('input', () => {
        if (c.closest('.campo').classList.contains('campo--error')) validarCampo(nombre);
      });
    });
  });

  // Guarda la solicitud como oportunidad en el CRM de Odoo (módulo autoflow_sitio_web, que atiende
  // los dos sitios: el campo "producto" dice de cuál viene).
  // Se manda como formulario común para que el navegador no haga una consulta previa (CORS).
  async function guardarEnCrm(datos) {
    if (!CONFIG.odoo) return false;
    try {
      const cuerpo = new URLSearchParams(datos);
      cuerpo.set('producto', CONFIG.producto);
      const respuesta = await fetch(`${CONFIG.odoo}/autoflow/solicitud`, {
        method: 'POST',
        body: cuerpo,
        signal: AbortSignal.timeout(10000),
      });
      return respuesta.ok && (await respuesta.json()).ok === true;
    } catch {
      return false;  // Odoo apagado o inaccesible: el cliente la envía por WhatsApp o correo.
    }
  }

  formulario.addEventListener('submit', async (e) => {
    e.preventDefault();
    const botonEnviar = formulario.querySelector('[type="submit"]');
    if (botonEnviar.disabled) return;
    const invalidos = Object.keys(reglas).filter((n) => !validarCampo(n));
    if (invalidos.length) {
      const primero = formulario.elements[invalidos[0]];
      (primero instanceof RadioNodeList ? primero[0] : primero).focus();
      aviso('error', 'Revisá el formulario', `Hay ${invalidos.length} ${invalidos.length === 1 ? 'dato' : 'datos'} por completar.`);
      return;
    }

    const datos = new FormData(formulario);
    const etiquetaPlan = formulario.plan.selectedOptions[0].textContent;
    const etiquetaTipo = formulario.querySelector(`label[for="tipo-${datos.get('tipo')}"]`).textContent.trim();
    const resumen = [
      'Hola, quiero solicitar una demostración de Studio Bella.',
      '',
      `Nombre: ${datos.get('nombre').trim()}`,
      `Negocio: ${datos.get('empresa').trim()}`,
      `Teléfono: ${datos.get('telefono').trim()}`,
      `Correo: ${datos.get('email').trim()}`,
      `Tipo: ${etiquetaTipo}`,
      `Estilistas: ${datos.get('usuarios')}`,
      `Plan de interés: ${etiquetaPlan}`,
      datos.get('mensaje').trim() ? `Mensaje: ${datos.get('mensaje').trim()}` : '',
    ].filter((linea, i, arr) => linea !== '' || arr[i - 1] !== '').join('\n').trim();

    const textoBoton = botonEnviar.innerHTML;
    botonEnviar.disabled = true;
    botonEnviar.textContent = 'Enviando…';
    const guardada = await guardarEnCrm(datos);
    botonEnviar.disabled = false;
    botonEnviar.innerHTML = textoBoton;

    // "crm": ya llegó a Odoo (y el aviso por correo). "manual": el cliente la envía con un toque.
    const modo = guardada ? 'crm' : 'manual';
    exito.querySelectorAll('[data-modo]').forEach((el) => { el.hidden = el.dataset.modo !== modo; });
    exito.querySelectorAll('[data-nombre]').forEach((el) => { el.textContent = datos.get('nombre').trim().split(' ')[0]; });
    exito.querySelector('.resumen').textContent = resumen;
    exito.querySelector('[data-enviar="whatsapp"]').href = enlaceWhatsapp(resumen);
    exito.querySelector('[data-enviar="email"]').href =
      `mailto:${CONFIG.email}?subject=${encodeURIComponent(`Solicitud de demo · ${datos.get('empresa').trim()}`)}&body=${encodeURIComponent(resumen)}`;

    document.querySelectorAll('.aviso--error').forEach((el) => el.remove());
    formulario.hidden = true;
    exito.hidden = false;
    exito.scrollIntoView({ behavior: 'smooth', block: 'start' });
    exito.querySelector('h2').focus();
  });

  exito?.querySelector('[data-otra]').addEventListener('click', () => {
    formulario.reset();
    formulario.querySelectorAll('.campo--error').forEach((c) => c.classList.remove('campo--error'));
    exito.hidden = true;
    formulario.hidden = false;
    formulario.elements.nombre.focus();
  });
}

/* ---------- Submenú de la página de funciones ---------- */

const subnav = document.querySelector('.subnav');
if (subnav && 'IntersectionObserver' in window) {
  const enlaces = [...subnav.querySelectorAll('a[href^="#"]')];
  const lista = subnav.querySelector('.subnav__lista');
  const marcar = (id) => {
    enlaces.forEach((a) => {
      const activo = a.getAttribute('href') === `#${id}`;
      a.classList.toggle('activo', activo);
      if (activo) lista.scrollTo({ left: a.offsetLeft - lista.clientWidth / 2 + a.clientWidth / 2, behavior: 'smooth' });
    });
  };
  const observador = new IntersectionObserver((entradas) => {
    entradas.forEach((en) => { if (en.isIntersecting) marcar(en.target.id); });
  }, { rootMargin: '-45% 0px -50% 0px' });
  enlaces.forEach((a) => {
    const destino = document.querySelector(a.getAttribute('href'));
    if (destino) observador.observe(destino);
  });
}
