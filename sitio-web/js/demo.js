/* ==========================================================================
   AutoFlow · demo interactiva del taller
   Simula en el navegador lo que hace el módulo en Odoo: recepción, etapas,
   aviso al cliente, controles de cierre, stock, kilometraje y factura.
   ========================================================================== */

(function () {
  const { aviso, gs, icono } = window.AutoFlow;

  const ETAPAS = [
    { id: 'recibido', nombre: 'Recibido', boton: 'Diagnosticar', color: '#1E9E57' },
    { id: 'diagnostico', nombre: 'En diagnóstico', boton: 'Pedir repuestos', color: '#F2A20C' },
    { id: 'repuestos', nombre: 'Esperando repuestos', boton: 'Reparar', color: '#F2A20C' },
    { id: 'reparacion', nombre: 'En reparación', boton: 'Terminar', color: '#7C5CC4' },
    { id: 'listo', nombre: 'Listo para entrega', boton: 'Entregar', color: '#1E9E57' },
    { id: 'finalizado', nombre: 'Finalizado', boton: '', color: '#2B78D6' },
  ];
  const indiceEtapa = (id) => ETAPAS.findIndex((e) => e.id === id);
  const nombreEtapa = (id) => ETAPAS[indiceEtapa(id)].nombre;

  const VEHICULOS_BASE = [
    { id: 'sportage21', nombre: 'Kia Sportage 2021 (AARS118)', cliente: 'Diego Fernández', km: 76500, estado: 'Vendido' },
    { id: 'hilux23', nombre: 'Toyota Hilux 2023 (AAKX123)', cliente: 'Ana Martínez', km: 40020, estado: 'Vendido' },
    { id: 'tucson22', nombre: 'Hyundai Tucson 2022 (AAXT904)', cliente: 'Carmen Duarte', km: 52300, estado: 'Vendido' },
    { id: 'frontier22', nombre: 'Nissan Frontier 2022 (AAVN552)', cliente: 'Pedro Gómez', km: 61800, estado: 'Vendido' },
    { id: 'onix23', nombre: 'Chevrolet Onix 2023 (ABZK777)', cliente: 'María Benítez', km: 25300, estado: 'Vendido' },
    { id: 'corolla20', nombre: 'Toyota Corolla 2020 (AAKM556)', cliente: 'Ana Martínez', km: 87400, estado: 'Vendido' },
    { id: 'hilux21', nombre: 'Toyota Hilux 2021 (AAPB321)', cliente: 'Jorge Ramírez', km: 98500, estado: 'Vendido' },
    { id: 'onix22', nombre: 'Chevrolet Onix 2022 (ABCD456)', cliente: 'Luis Ortiz', km: 61450, estado: 'Vendido' },
    { id: 'tucson26', nombre: 'Hyundai Tucson 2026', cliente: 'AutoFlow Concesionaria', km: 12, estado: 'Disponible' },
  ];

  const ORDENES_BASE = [
    { numero: 'OS/2026/0010', vehiculo: 'tucson26', tipo: 'Preventivo', mecanico: '', etapa: 'recibido', total: 0 },
    { numero: 'OS/2026/0011', vehiculo: 'onix23', tipo: 'Correctivo', mecanico: 'Carlos Benítez', etapa: 'diagnostico', total: 0 },
    { numero: 'OS/2026/0012', vehiculo: 'corolla20', tipo: 'Correctivo', mecanico: 'Hugo Martínez', etapa: 'repuestos', total: 2000000, faltaRepuesto: true },
    { numero: 'OS/2026/0013', vehiculo: 'hilux21', tipo: 'Correctivo', mecanico: 'Rodrigo Giménez', etapa: 'reparacion', total: 990000, urgente: true },
    { numero: 'OS/2026/0014', vehiculo: 'onix22', tipo: 'Preventivo', mecanico: 'Hugo Martínez', etapa: 'listo', total: 385000 },
    { numero: 'OS/2026/0009', vehiculo: 'hilux21', tipo: 'Preventivo', mecanico: 'Hugo Martínez', etapa: 'finalizado', total: 700000, facturada: true },
  ];

  // Trabajo que se "carga" solo en la demo cuando la orden llega a "Esperando repuestos".
  // Precios del catálogo de repuestos del módulo; mano de obra a 100.000 Gs. la hora.
  const TRABAJOS = {
    Preventivo: { detalle: 'aceite 5W-30 (7 L), filtro de aceite y 1:30 h de mano de obra', total: 615000 },
    Correctivo: { detalle: 'pastillas y disco de freno delanteros y 2:00 h de mano de obra', total: 900000 },
    Garantía: { detalle: 'bomba de agua y 2:30 h de mano de obra', total: 730000 },
  };

  const CHECKLIST = ['Frenos', 'Neumáticos y presión', 'Luces', 'Batería', 'Fluidos (aceite, refrigerante, frenos)', 'Limpiaparabrisas', 'Pintura y carrocería'];

  let vehiculos;
  let ordenes;
  let siguienteNumero;
  let facturado;
  let resaltar = null;

  const $ = (sel, raiz = document) => raiz.querySelector(sel);
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const vehiculoDe = (orden) => vehiculos.find((v) => v.id === orden.vehiculo);
  const iniciales = (nombre) => (nombre ? nombre[0] : '');

  const tablero = $('[data-tablero]');
  const registro = $('[data-registro]');
  const formRecepcion = $('[data-recepcion]');
  const modalCierre = $('[data-modal-cierre]');
  const modalCorreo = $('[data-modal-correo]');

  /* ---------- Registro de acciones automáticas ---------- */

  function registrar(nombreIcono, color, html, accion) {
    $('.registro__vacio', registro)?.remove();
    const li = document.createElement('li');
    li.className = 'registro__item';
    const hora = new Date().toLocaleTimeString('es-PY', { hour: '2-digit', minute: '2-digit' });
    li.innerHTML = `<span class="tarjeta__icono ${color}">${icono(nombreIcono)}</span><div><span>${html}</span><time>${hora}</time></div>`;
    if (accion) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = accion.texto;
      b.addEventListener('click', accion.fn);
      li.querySelector('div').append(b);
    }
    registro.prepend(li);
    registro.scrollTop = 0;
  }

  function registroVacio() {
    registro.innerHTML = '<li class="registro__vacio">Todavía no pasó nada. Recibí un vehículo o mové una tarjeta del tablero.</li>';
  }

  function actualizarResumen() {
    $('[data-resumen="abiertas"]').textContent = ordenes.filter((o) => o.etapa !== 'finalizado').length;
    $('[data-resumen="facturado"]').textContent = `Gs. ${gs(facturado)}`;
  }

  /* ---------- Tablero ---------- */

  function tarjetaHTML(o) {
    const v = vehiculoDe(o);
    const i = indiceEtapa(o.etapa);
    const cerrada = o.etapa === 'finalizado';
    const siguiente = ETAPAS[i + 1];
    let acciones = '';
    if (!cerrada) {
      acciones = '<div class="orden__acciones">';
      if (i > 0) acciones += `<button type="button" data-accion="atras" aria-label="Volver a ${esc(ETAPAS[i - 1].nombre)}" title="Volver a ${esc(ETAPAS[i - 1].nombre)}">${icono('flecha-izq')}</button>`;
      if (o.faltaRepuesto) acciones += '<button type="button" class="avanzar" data-accion="repuestos">Recibir repuestos</button>';
      else acciones += `<button type="button" class="avanzar${siguiente.id === 'finalizado' ? ' avanzar--fin' : ''}" data-accion="avanzar" title="Pasar a ${esc(siguiente.nombre)}">${esc(ETAPAS[i].boton)} ${icono(siguiente.id === 'finalizado' ? 'check' : 'flecha')}</button>`;
      acciones += '</div>';
    }
    return `
      <article class="orden${resaltar === o.numero ? ' orden--nueva' : ''}" data-id="${esc(o.numero)}" draggable="${!cerrada}" aria-label="Orden ${esc(o.numero)}, ${esc(v.nombre)}">
        <div class="orden__num"><span>${esc(o.numero)}</span><svg class="ico${o.urgente ? ' urgente' : ''}" aria-label="${o.urgente ? 'Urgente' : 'Prioridad normal'}"><use href="#i-estrella"></use></svg></div>
        <div class="orden__veh">${esc(v.nombre)}</div>
        <div class="orden__cli">${esc(v.cliente)}</div>
        <div class="orden__insignias">
          <span class="insignia insignia--${esc(o.tipo)}">${esc(o.tipo)}</span>
          ${o.faltaRepuesto ? `<span class="insignia insignia--rojo">${icono('alerta')} Faltan repuestos</span>` : ''}
          ${o.facturada ? `<span class="insignia insignia--factura">${icono('factura')} Factura en borrador</span>` : ''}
          ${cerrada && o.tipo === 'Garantía' ? '<span class="insignia insignia--Garantía">Sin cargo</span>' : ''}
        </div>
        <div class="orden__pie">
          ${o.mecanico
            ? `<span class="avatar avatar--${esc(iniciales(o.mecanico))}" title="${esc(o.mecanico)}">${esc(iniciales(o.mecanico))}</span>`
            : `<span class="avatar avatar--vacio" title="Sin mecánico">${icono('usuarios')}</span>`}
          <span class="orden__total">${o.total ? `${gs(o.total)} ₲` : ''}</span>
        </div>
        ${acciones}
      </article>`;
  }

  function render() {
    tablero.innerHTML = ETAPAS.map((e) => {
      const lista = ordenes.filter((o) => o.etapa === e.id);
      return `
        <section class="columna" data-etapa="${e.id}" aria-label="${esc(e.nombre)}">
          <div class="columna__cabeza"><h3>${esc(e.nombre)}</h3><span class="columna__cuenta">${lista.length}</span></div>
          <div class="columna__barra"><i style="background:${e.color}"></i></div>
          <div class="columna__tarjetas">
            ${lista.length ? lista.map(tarjetaHTML).join('') : '<div class="columna__vacia">Sin órdenes</div>'}
          </div>
        </section>`;
    }).join('');
    actualizarResumen();
    actualizarOpcionesVehiculo();
  }

  function enfocarTarjeta(numero) {
    const tarjeta = tablero.querySelector(`[data-id="${CSS.escape(numero)}"]`);
    if (!tarjeta) return;
    // Si la columna quedó fuera de la vista (celular), el tablero se desliza hasta ella.
    const columna = tarjeta.closest('.columna');
    const visible = columna.offsetLeft >= tablero.scrollLeft &&
      columna.offsetLeft + columna.offsetWidth <= tablero.scrollLeft + tablero.clientWidth;
    if (!visible) {
      tablero.scrollTo({ left: columna.offsetLeft - parseFloat(getComputedStyle(tablero).paddingLeft), behavior: 'smooth' });
    }
    (tarjeta.querySelector('.avanzar, [data-accion]') || tarjeta).focus({ preventScroll: true });
  }

  /* ---------- Reglas de negocio ---------- */

  function cargarTrabajo(o) {
    const t = TRABAJOS[o.tipo];
    o.total = t.total;
    registrar('caja', 'c-violeta', `Se cargaron ${esc(t.detalle)} en <b>${esc(o.numero)}</b>. Total calculado: <b>Gs. ${gs(t.total)}</b>.`);
  }

  function avisarCliente(o) {
    const v = vehiculoDe(o);
    registrar('sobre', 'c-verde', `Correo “Su vehículo está listo” enviado a <b>${esc(v.cliente)}</b>.`, { texto: 'Ver correo', fn: () => verCorreo(o) });
    registrar('calendario', 'c-ambar', `Tarea “Coordinar la entrega del vehículo” creada para el asesor de servicio.`);
    aviso('exito', 'Cliente avisado por correo', `${v.cliente} ya sabe que su ${v.nombre} está listo.`);
  }

  function mover(o, destino) {
    if (!o || o.etapa === destino) return;
    if (o.etapa === 'finalizado') {
      aviso('info', 'Orden cerrada', 'Las órdenes finalizadas no se pueden mover.');
      return;
    }
    if (o.faltaRepuesto && indiceEtapa(destino) > indiceEtapa('repuestos')) {
      aviso('error', 'Faltan repuestos', `${o.numero} no puede avanzar hasta que lleguen los repuestos al depósito.`);
      return;
    }
    if (destino === 'finalizado') {
      abrirCierre(o);
      return;
    }
    o.etapa = destino;
    registrar('flecha', 'c-azul', `<b>${esc(o.numero)}</b> pasó a “${esc(nombreEtapa(destino))}”.`);
    if (!o.total && indiceEtapa(destino) >= indiceEtapa('repuestos')) cargarTrabajo(o);
    if (destino === 'listo') avisarCliente(o);
    resaltar = o.numero;
    render();
    enfocarTarjeta(o.numero);
  }

  tablero.addEventListener('click', (e) => {
    const boton = e.target.closest('button[data-accion]');
    if (!boton) return;
    const o = ordenes.find((x) => x.numero === boton.closest('.orden').dataset.id);
    const i = indiceEtapa(o.etapa);
    if (boton.dataset.accion === 'avanzar') mover(o, ETAPAS[i + 1].id);
    if (boton.dataset.accion === 'atras') mover(o, ETAPAS[i - 1].id);
    if (boton.dataset.accion === 'repuestos') {
      o.faltaRepuesto = false;
      registrar('caja', 'c-verde', `Llegaron los repuestos de <b>${esc(o.numero)}</b>: stock actualizado en el depósito.`);
      aviso('exito', 'Repuestos recibidos', 'Ya podés avanzar la orden.');
      resaltar = o.numero;
      render();
      enfocarTarjeta(o.numero);
    }
  });

  /* Arrastrar y soltar (computadora) */
  let arrastrando = null;
  tablero.addEventListener('dragstart', (e) => {
    const tarjeta = e.target.closest('.orden');
    if (!tarjeta) return;
    arrastrando = tarjeta.dataset.id;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', arrastrando);
    requestAnimationFrame(() => tarjeta.classList.add('orden--arrastrando'));
  });
  tablero.addEventListener('dragend', () => {
    arrastrando = null;
    tablero.querySelectorAll('.orden--arrastrando').forEach((t) => t.classList.remove('orden--arrastrando'));
    tablero.querySelectorAll('.columna--sobre').forEach((c) => c.classList.remove('columna--sobre'));
  });
  tablero.addEventListener('dragover', (e) => {
    const columna = e.target.closest('.columna');
    if (!columna || !arrastrando) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    tablero.querySelectorAll('.columna--sobre').forEach((c) => c !== columna && c.classList.remove('columna--sobre'));
    columna.classList.add('columna--sobre');
  });
  tablero.addEventListener('dragleave', (e) => {
    const columna = e.target.closest('.columna');
    if (columna && !columna.contains(e.relatedTarget)) columna.classList.remove('columna--sobre');
  });
  tablero.addEventListener('drop', (e) => {
    const columna = e.target.closest('.columna');
    if (!columna) return;
    e.preventDefault();
    columna.classList.remove('columna--sobre');
    const o = ordenes.find((x) => x.numero === e.dataTransfer.getData('text/plain'));
    mover(o, columna.dataset.etapa);
  });

  /* ---------- Correo al cliente ---------- */

  function verCorreo(o) {
    const v = vehiculoDe(o);
    $('[data-correo-para]').textContent = `Para: ${v.cliente} · Asunto: Su vehículo está listo para retirar`;
    const total = o.tipo === 'Garantía'
      ? 'Servicio en garantía: <b>sin costo para usted</b>.'
      : `Total: <b>${gs(o.total)} ₲</b>`;
    $('[data-correo-cuerpo]').innerHTML =
      `Hola ${esc(v.cliente)},\n\nLe avisamos que su vehículo <b>${esc(v.nombre)}</b> ya está listo para retirar del taller.\n\n` +
      `Orden de servicio: <b>${esc(o.numero)}</b>\n${total}\n\n` +
      'Lo esperamos. Al retirarlo le entregamos el acta de entrega con el detalle del trabajo realizado.\n\nSaludos,\nAutoFlow Concesionaria';
    modalCorreo.showModal();
  }

  /* ---------- Cierre: checklist, controles y firma ---------- */

  let ordenEnCierre = null;
  const formCierre = $('[data-form-cierre]');
  const errorCierre = $('[data-cierre-error]');
  const bloqueMecanico = $('[data-cierre-mecanico]');
  const checklist = $('[data-checklist]');

  function abrirCierre(o) {
    ordenEnCierre = o;
    const v = vehiculoDe(o);
    $('[data-cierre-sub]').textContent = `${o.numero} · ${v.nombre} · ${v.cliente}`;
    errorCierre.hidden = true;
    bloqueMecanico.hidden = Boolean(o.mecanico);
    formCierre.mecanico.value = '';
    checklist.innerHTML = CHECKLIST.map((punto, i) => `
      <div class="punto" data-punto="${i}">
        <span>${esc(punto)}</span>
        <div class="segmentos" role="radiogroup" aria-label="${esc(punto)}">
          <input type="radio" id="p${i}-ok" name="p${i}" value="ok"><label class="ok" for="p${i}-ok">OK</label>
          <input type="radio" id="p${i}-c" name="p${i}" value="cambio"><label class="cambio" for="p${i}-c">Requiere cambio</label>
          <input type="radio" id="p${i}-d" name="p${i}" value="danado"><label class="danado" for="p${i}-d">Dañado</label>
        </div>
      </div>`).join('');
    modalCierre.showModal();
    prepararFirma();
  }

  checklist.addEventListener('change', (e) => e.target.closest('.punto')?.classList.remove('punto--falta'));
  $('[data-todo-ok]').addEventListener('click', () => {
    checklist.querySelectorAll('input[value="ok"]').forEach((r) => { r.checked = true; });
    checklist.querySelectorAll('.punto--falta').forEach((p) => p.classList.remove('punto--falta'));
  });

  document.querySelectorAll('.modal [data-cerrar]').forEach((b) => b.addEventListener('click', () => b.closest('dialog').close()));
  document.querySelectorAll('.modal').forEach((m) => m.addEventListener('click', (e) => { if (e.target === m) m.close(); }));

  $('[data-finalizar]').addEventListener('click', () => {
    const o = ordenEnCierre;
    const v = vehiculoDe(o);
    const mecanico = o.mecanico || formCierre.mecanico.value;
    const puntos = [...checklist.querySelectorAll('.punto')];
    const sinRevisar = puntos.filter((p) => !p.querySelector('input:checked'));
    const errores = [];
    if (!mecanico) errores.push('Asigne el mecánico responsable.');
    if (!o.total) errores.push('Cargue la mano de obra o los repuestos utilizados (en la demo se cargan solos al pasar por “Esperando repuestos”).');
    if (sinRevisar.length) errores.push(`Faltan revisar ${sinRevisar.length} ${sinRevisar.length === 1 ? 'punto' : 'puntos'} del checklist de entrega.`);

    puntos.forEach((p) => p.classList.toggle('punto--falta', sinRevisar.includes(p)));
    if (errores.length) {
      errorCierre.innerHTML = `<b>No se puede finalizar la orden ${esc(o.numero)}:</b><ul>${errores.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`;
      errorCierre.hidden = false;
      errorCierre.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      aviso('error', 'Operación no válida', 'AutoFlow no deja cerrar una orden incompleta.');
      return;
    }

    const observados = puntos.filter((p) => p.querySelector('input:checked').value !== 'ok').length;
    o.mecanico = mecanico;
    o.etapa = 'finalizado';
    registrar('caja', 'c-violeta', `Repuestos de <b>${esc(o.numero)}</b> descontados del stock.`);
    registrar('odometro', 'c-azul', `Kilometraje de ${esc(v.nombre)} actualizado a <b>${gs(o.km || v.km)} km</b>.`);
    if (o.km) v.km = o.km;
    registrar('auto', 'c-azul', `${esc(v.nombre)} vuelve a su estado anterior: “${esc(v.estado)}”.`);
    if (o.tipo === 'Garantía') {
      registrar('escudo', 'c-verde', `<b>${esc(o.numero)}</b> es una garantía: no se factura al cliente.`);
    } else {
      o.facturada = true;
      facturado += o.total;
      registrar('factura', 'c-verde', `Factura en borrador creada para ${esc(v.cliente)} por <b>Gs. ${gs(o.total)}</b>.`);
    }
    registrar('firma', 'c-ambar', firmaHecha
      ? `Acta de entrega firmada por <b>${esc(v.cliente)}</b>.`
      : 'Acta de entrega lista para imprimir y firmar.');
    if (observados) {
      registrar('alerta', 'c-rojo', observados === 1
        ? '1 punto del checklist quedó anotado para el próximo service.'
        : `${observados} puntos del checklist quedaron anotados para el próximo service.`);
    }

    modalCierre.close();
    aviso('exito', `${o.numero} finalizada`, o.tipo === 'Garantía'
      ? 'Stock y kilometraje actualizados. Sin factura por ser garantía.'
      : `Stock descontado y factura en borrador por Gs. ${gs(o.total)}.`);
    resaltar = o.numero;
    render();
    enfocarTarjeta(o.numero);
  });

  /* Firma con el dedo o el mouse */
  const lienzo = $('[data-firma]');
  const ctx = lienzo.getContext('2d');
  let firmaHecha = false;
  let dibujando = false;

  function prepararFirma() {
    const escala = window.devicePixelRatio || 1;
    const ancho = lienzo.clientWidth || 600;
    lienzo.width = ancho * escala;
    lienzo.height = 160 * escala;
    ctx.setTransform(escala, 0, 0, escala, 0, 0);
    ctx.lineWidth = 2.4;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#1A3E78';
    ctx.clearRect(0, 0, ancho, 160);
    firmaHecha = false;
  }
  function punto(e) {
    const r = lienzo.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }
  lienzo.addEventListener('pointerdown', (e) => {
    dibujando = true;
    lienzo.setPointerCapture(e.pointerId);
    ctx.beginPath();
    ctx.moveTo(...punto(e));
  });
  lienzo.addEventListener('pointermove', (e) => {
    if (!dibujando) return;
    ctx.lineTo(...punto(e));
    ctx.stroke();
    firmaHecha = true;
  });
  ['pointerup', 'pointercancel'].forEach((tipo) => lienzo.addEventListener(tipo, () => { dibujando = false; }));
  $('[data-borrar-firma]').addEventListener('click', prepararFirma);

  /* ---------- Recepción ---------- */

  const selVehiculo = formRecepcion.vehiculo;
  const salidaCombustible = $('[data-combustible]');

  function ordenAbierta(idVehiculo) {
    return ordenes.find((o) => o.vehiculo === idVehiculo && o.etapa !== 'finalizado');
  }

  function actualizarOpcionesVehiculo() {
    const elegido = selVehiculo.value;
    selVehiculo.innerHTML = '<option value="">Elegí un vehículo…</option>' + vehiculos.map((v) => {
      const abierta = ordenAbierta(v.id);
      return `<option value="${v.id}">${esc(v.nombre)}${abierta ? ` · en taller (${esc(abierta.numero)})` : ''}</option>`;
    }).join('');
    selVehiculo.value = elegido;
  }

  function mostrarCombustible() {
    const p = Number(formRecepcion.combustible.value);
    const fraccion = ['Vacío', '1/4', '1/2', '3/4', 'Lleno'][Math.round(p / 25)];
    salidaCombustible.textContent = `${p} % · ${fraccion}`;
    salidaCombustible.dataset.nivel = p < 25 ? 'bajo' : p < 50 ? 'medio' : 'alto';
  }

  function errorCampo(control, mensaje) {
    const campo = control.closest('.campo');
    campo.classList.toggle('campo--error', Boolean(mensaje));
    campo.querySelector('.campo__error').textContent = mensaje || '';
    control.setAttribute('aria-invalid', String(Boolean(mensaje)));
  }

  selVehiculo.addEventListener('change', () => {
    const v = vehiculos.find((x) => x.id === selVehiculo.value);
    formRecepcion.cliente.value = v ? v.cliente : '';
    formRecepcion.km.value = v ? v.km : '';
    formRecepcion.km.min = v ? v.km : 0;
    errorCampo(selVehiculo, '');
    errorCampo(formRecepcion.km, '');
    const abierta = v && ordenAbierta(v.id);
    if (abierta) errorCampo(selVehiculo, `Este vehículo ya tiene la orden ${abierta.numero} abierta.`);
  });
  formRecepcion.combustible.addEventListener('input', mostrarCombustible);
  formRecepcion.motivo.addEventListener('input', () => errorCampo(formRecepcion.motivo, ''));
  formRecepcion.km.addEventListener('input', () => errorCampo(formRecepcion.km, ''));

  $('[data-ejemplo]').addEventListener('click', () => {
    const libre = vehiculos.find((v) => !ordenAbierta(v.id));
    if (!libre) {
      aviso('info', 'Todos los autos están en el taller', 'Finalizá alguna orden o reiniciá la demo.');
      return;
    }
    selVehiculo.value = libre.id;
    selVehiculo.dispatchEvent(new Event('change'));
    formRecepcion.km.value = libre.km + 1350;
    formRecepcion.mecanico.value = 'Hugo Martínez';
    formRecepcion.querySelector('#r-corr').checked = true;
    formRecepcion.combustible.value = 35;
    formRecepcion.combustible.dispatchEvent(new Event('input'));
    formRecepcion.querySelectorAll('[name="danos"]').forEach((c) => { c.checked = c.value === 'Rayones'; });
    formRecepcion.motivo.value = 'Ruido metálico en la rueda delantera derecha al frenar';
    errorCampo(formRecepcion.motivo, '');
  });

  formRecepcion.addEventListener('submit', (e) => {
    e.preventDefault();
    const v = vehiculos.find((x) => x.id === selVehiculo.value);
    const km = Number(formRecepcion.km.value);
    const motivo = formRecepcion.motivo.value.trim();
    let valido = true;

    if (!v) { errorCampo(selVehiculo, 'Elegí el vehículo que entra al taller.'); valido = false; }
    else if (ordenAbierta(v.id)) { errorCampo(selVehiculo, `Este vehículo ya tiene la orden ${ordenAbierta(v.id).numero} abierta.`); valido = false; }
    if (v && (!formRecepcion.km.value || km < v.km)) {
      errorCampo(formRecepcion.km, `El kilometraje no puede ser menor al actual (${gs(v.km)} km).`);
      valido = false;
    }
    if (motivo.length < 3) { errorCampo(formRecepcion.motivo, 'Contá brevemente por qué entra el auto.'); valido = false; }
    if (!valido) {
      formRecepcion.querySelector('.campo--error select, .campo--error input')?.focus();
      aviso('error', 'Faltan datos en la recepción', 'Revisá los campos marcados en rojo.');
      return;
    }

    const datos = new FormData(formRecepcion);
    const danos = datos.getAll('danos');
    const o = {
      numero: `OS/2026/${String(siguienteNumero++).padStart(4, '0')}`,
      vehiculo: v.id,
      tipo: datos.get('tipo'),
      mecanico: datos.get('mecanico'),
      etapa: 'recibido',
      total: 0,
      km,
    };
    ordenes.push(o);

    registrar('llave', 'c-ambar', `Orden <b>${esc(o.numero)}</b> creada para ${esc(v.nombre)} (${esc(v.cliente)}).`);
    registrar('combustible', 'c-ambar', `Recepción registrada: ${gs(km)} km, combustible ${esc(salidaCombustible.textContent)}` +
      `${danos.length ? `, daños: ${esc(danos.join(', ').toLowerCase())}` : ', sin daños visibles'}. Motivo: “${esc(motivo)}”.`);
    aviso('exito', `Orden ${o.numero} creada`, 'El vehículo ya está en la columna “Recibido”.');

    formRecepcion.reset();
    formRecepcion.combustible.dispatchEvent(new Event('input'));
    resaltar = o.numero;
    render();
    $('#tablero').scrollIntoView({ behavior: 'smooth', block: 'start' });
    tablero.scrollTo({ left: 0, behavior: 'smooth' });
  });

  /* ---------- Inicio y reinicio ---------- */

  function iniciar() {
    vehiculos = VEHICULOS_BASE.map((v) => ({ ...v }));
    ordenes = ORDENES_BASE.map((o) => ({ ...o }));
    siguienteNumero = 15;
    facturado = 0;
    resaltar = null;
    registroVacio();
    formRecepcion.reset();
    [selVehiculo, formRecepcion.km, formRecepcion.motivo].forEach((c) => errorCampo(c, ''));
    formRecepcion.combustible.dispatchEvent(new Event('input'));
    render();
  }

  $('[data-reiniciar]').addEventListener('click', () => {
    iniciar();
    aviso('info', 'Demo reiniciada', 'El tablero volvió a los datos de ejemplo.');
  });

  iniciar();
})();
