/* ==========================================================================
   Studio Bella · demo interactiva
   Simula en el navegador un turno completo: agendar, recordar por WhatsApp,
   cobrar con factura y reponer el stock. No se guarda nada.
   ========================================================================== */

(function () {
  const raiz = document.querySelector('[data-demo]');
  if (!raiz) return;

  const { aviso, gs, icono } = window.StudioBella;
  const $ = (selector, base = raiz) => base.querySelector(selector);
  const $$ = (selector, base = raiz) => [...base.querySelectorAll(selector)];

  /* ---------- Datos del salón de ejemplo ---------- */

  const APERTURA = 8 * 60;  // minutos desde la medianoche
  const CIERRE = 19 * 60;
  const PRECIO_SHAMPOO = 85000;

  const ESTILISTAS = [
    { id: 'lorena', nombre: 'Lorena', color: '#5BA94A', servicios: ['corte', 'brushing', 'raiz', 'hidratacion'] },
    { id: 'camila', nombre: 'Camila', color: '#C9A50F', servicios: ['corte', 'brushing', 'hidratacion'] },
    { id: 'diego', nombre: 'Diego', color: '#C4532F', servicios: ['caballero', 'barba'] },
    { id: 'fatima', nombre: 'Fátima', color: '#B23A7E', servicios: ['manicura'] },
  ];

  const SERVICIOS = {
    corte: { nombre: 'Corte de dama', minutos: 60, precio: 80000 },
    brushing: { nombre: 'Brushing', minutos: 45, precio: 60000 },
    raiz: { nombre: 'Tintura de raíz', minutos: 90, precio: 180000, insumos: { tinte: 1, oxidante: 0.06 } },
    hidratacion: { nombre: 'Hidratación profunda', minutos: 45, precio: 90000, insumos: { mascarilla: 0.05 } },
    caballero: { nombre: 'Corte de caballero', minutos: 30, precio: 50000 },
    barba: { nombre: 'Arreglo de barba', minutos: 30, precio: 35000 },
    manicura: { nombre: 'Manicura', minutos: 45, precio: 50000 },
  };

  // Turnos que ya están en la agenda de mañana.
  const CITAS = [
    { estilista: 'lorena', inicio: 9 * 60, fin: 11 * 60, cliente: 'Rosa Galeano', servicios: 'Tintura completa' },
    { estilista: 'lorena', inicio: 16 * 60, fin: 16 * 60 + 45, cliente: 'Valeria Rojas', servicios: 'Hidratación profunda' },
    { estilista: 'camila', inicio: 9 * 60, fin: 10 * 60, cliente: 'Gabriela Insfrán', servicios: 'Corte de dama' },
    { estilista: 'camila', inicio: 11 * 60, fin: 12 * 60 + 45, cliente: 'Lucía Acosta', servicios: 'Corte + Brushing' },
    { estilista: 'diego', inicio: 10 * 60, fin: 10 * 60 + 30, cliente: 'Jorge Ayala', servicios: 'Arreglo de barba' },
    { estilista: 'diego', inicio: 17 * 60, fin: 17 * 60 + 30, cliente: 'Rodrigo Báez', servicios: 'Corte de caballero' },
    { estilista: 'fatima', inicio: 15 * 60, fin: 15 * 60 + 45, cliente: 'María José Fernández', servicios: 'Manicura' },
  ];

  // Los que tienen correo ya recibieron el recordatorio automático de las 10:00.
  const AVISADOS_POR_CORREO = [
    { cliente: 'Gabriela Insfrán', detalle: '09:00 · Corte de dama · Camila' },
    { cliente: 'Rodrigo Báez', detalle: '17:00 · Corte de caballero · Diego' },
  ];

  // El tinte y el oxidante están justo en el mínimo: una tintura los deja por debajo.
  const STOCK_INICIAL = {
    tinte: { nombre: 'Tinte profesional (tubo 60 g)', cantidad: 10, minimo: 10, maximo: 30, costo: 28000, proveedor: 'Distribuidora Capilar S.A.' },
    oxidante: { nombre: 'Oxidante 20 vol (botella 1 L)', cantidad: 3.04, minimo: 3, maximo: 8, costo: 45000, proveedor: 'Distribuidora Capilar S.A.' },
    mascarilla: { nombre: 'Mascarilla profesional (pote 1 kg)', cantidad: 2, minimo: 1, maximo: 3, costo: 150000, proveedor: 'Distribuidora Capilar S.A.' },
    shampoo: { nombre: 'Shampoo reparador 300 ml', cantidad: 6, minimo: 6, maximo: 15, costo: 48000, proveedor: 'Belleza Total Importaciones S.R.L.' },
  };

  const NOMBRE_PAGO = { efectivo: 'efectivo', tarjeta: 'tarjeta', transferencia: 'transferencia / QR' };

  /* ---------- Utilidades ---------- */

  const hora = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
  const plata = (n) => `${gs(n)} ₲`;
  const cantidad = (n) => n.toLocaleString('es-PY', { maximumFractionDigits: 2 });
  const numero = (texto) => Number(String(texto).replace(/\D/g, '')) || 0;
  const estilista = (id) => ESTILISTAS.find((e) => e.id === id);
  const esc = (texto) => texto.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const serviciosTexto = (t) => t.servicios.map((id) => SERVICIOS[id].nombre).join(' + ');
  const horaActual = () => new Date().toLocaleTimeString('es-PY', { hour: '2-digit', minute: '2-digit' });
  const copia = (objeto) => JSON.parse(JSON.stringify(objeto));

  function numeroInternacional(telefono) {
    const digitos = telefono.replace(/\D/g, '');
    if (!digitos) return 'sin número';
    const local = digitos.startsWith('0') ? digitos.slice(1) : digitos.replace(/^595/, '');
    return `+595 ${local.replace(/(\d{3})(\d{3})(\d+)/, '$1 $2 $3')}`;
  }

  let estado;

  function estadoInicial() {
    return { citas: copia(CITAS), turno: null, cobro: null, pedidos: null, recibido: false, stock: copia(STOCK_INICIAL) };
  }

  /* ---------- Pasos ---------- */

  function irA(paso, desplazar = true) {
    $$('[data-paso]').forEach((panel) => { panel.hidden = panel.dataset.paso !== paso; });
    $$('[data-ir-paso]').forEach((boton) => {
      if (boton.dataset.irPaso === paso) boton.setAttribute('aria-current', 'step');
      else boton.removeAttribute('aria-current');
    });
    if (desplazar) raiz.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function habilitarHasta(paso) {
    const orden = ['agendar', 'recordar', 'cobrar', 'reponer'];
    const limite = orden.indexOf(paso);
    $$('[data-ir-paso]').forEach((boton) => {
      const i = orden.indexOf(boton.dataset.irPaso);
      boton.disabled = i > limite;
      boton.classList.toggle('hecho', i < limite);
    });
  }

  /* ---------- 1. Agendar ---------- */

  const formTurno = $('[data-form-turno]');
  const errorTurno = $('[data-error-turno]');

  ESTILISTAS.forEach((e) => formTurno.estilista.add(new Option(e.nombre, e.id)));
  for (let m = APERTURA; m <= CIERRE - 30; m += 30) formTurno.hora.add(new Option(hora(m), String(m)));
  $('[data-servicios]').innerHTML = Object.entries(SERVICIOS).map(([id, s]) => `
    <label><input type="checkbox" name="servicio" value="${id}"><span>${s.nombre}<small>${s.minutos} min · ${plata(s.precio)}</small></span></label>`).join('');

  function elegir(estilistaId, inicio, servicios) {
    formTurno.estilista.value = estilistaId;
    formTurno.hora.value = String(inicio);
    $$('input[name="servicio"]', formTurno).forEach((c) => { c.checked = servicios.includes(c.value); });
    actualizarResumen();
  }

  function datosTurno() {
    const servicios = $$('input[name="servicio"]:checked', formTurno).map((c) => c.value);
    const inicio = Number(formTurno.hora.value);
    const minutos = servicios.reduce((suma, id) => suma + SERVICIOS[id].minutos, 0);
    return {
      cliente: formTurno.cliente.value.trim() || 'Sofía Villalba',
      telefono: formTurno.telefono.value.trim(),
      estilista: formTurno.estilista.value,
      inicio,
      fin: inicio + (minutos || 30),
      minutos,
      servicios,
      total: servicios.reduce((suma, id) => suma + SERVICIOS[id].precio, 0),
    };
  }

  function actualizarResumen() {
    const t = datosTurno();
    $('[data-r="duracion"]').textContent = t.minutos ? `${t.minutos} min` : '—';
    $('[data-r="fin"]').textContent = t.minutos ? hora(t.fin) : '—';
    $('[data-r="total"]').textContent = t.minutos ? plata(t.total) : '—';
    errorTurno.hidden = true;
  }

  // Las mismas reglas que el sistema: servicios del estilista, horario del salón y sin superposiciones.
  function validarTurno(t) {
    const e = estilista(t.estilista);
    if (!t.servicios.length) return 'Elegí al menos un servicio.';
    const noHace = t.servicios.filter((id) => !e.servicios.includes(id)).map((id) => SERVICIOS[id].nombre);
    if (noHace.length) return `${e.nombre} no hace: ${noHace.join(', ')}. Elegí otro estilista o cambiá el servicio.`;
    if (t.fin > CIERRE) return `${e.nombre} no trabaja de ${hora(t.inicio)} a ${hora(t.fin)}: el salón atiende de 08:00 a 19:00.`;
    const otra = estado.citas.find((c) => !c.nuevo && c.estilista === t.estilista && c.inicio < t.fin && c.fin > t.inicio);
    if (otra) {
      return `${e.nombre} ya tiene la cita de ${otra.cliente} de ${hora(otra.inicio)} a ${hora(otra.fin)}. Elegí otro horario u otro estilista.`;
    }
    return '';
  }

  function dibujarAgenda() {
    const horas = [];
    for (let h = 9; h < 19; h++) horas.push(`<span style="top:calc(var(--hora) * ${h - 8})">${h}:00</span>`);
    const columnas = ESTILISTAS.map((e) => {
      const bloques = estado.citas.filter((c) => c.estilista === e.id).map((c) => `
        <div class="bloque${c.nuevo ? ' bloque--nuevo' : ''}" style="--color:${e.color};top:calc(var(--hora) * ${(c.inicio - APERTURA) / 60});height:calc(var(--hora) * ${(c.fin - c.inicio) / 60} - 2px)" title="${esc(`${c.cliente} · ${c.servicios} · ${hora(c.inicio)} a ${hora(c.fin)}`)}">
          <b>${hora(c.inicio)} ${esc(c.cliente.split(' ')[0])}</b>${esc(c.servicios)}
        </div>`).join('');
      return `<div class="agenda-mini__columna">${bloques}</div>`;
    }).join('');
    $('[data-agenda]').innerHTML =
      '<div class="agenda-mini__titulo"></div>'
      + ESTILISTAS.map((e) => `<div class="agenda-mini__titulo"><i style="background:${e.color}"></i>${e.nombre}</div>`).join('')
      + `<div class="agenda-mini__horas">${horas.join('')}</div>${columnas}`;
  }

  formTurno.addEventListener('input', actualizarResumen);
  formTurno.addEventListener('change', actualizarResumen);

  formTurno.addEventListener('submit', (evento) => {
    evento.preventDefault();
    const t = datosTurno();
    const error = validarTurno(t);
    if (error) {
      errorTurno.textContent = error;
      errorTurno.hidden = false;
      return;
    }
    // Agendar de nuevo empieza otra vez el recorrido con el turno nuevo.
    estado = estadoInicial();
    estado.turno = t;
    estado.citas.push({ estilista: t.estilista, inicio: t.inicio, fin: t.fin, cliente: t.cliente, servicios: serviciosTexto(t), nuevo: true });
    dibujarAgenda();
    prepararRecordatorios();
    habilitarHasta('recordar');
    aviso('exito', 'Turno agendado', `${t.cliente} · mañana de ${hora(t.inicio)} a ${hora(t.fin)} con ${estilista(t.estilista).nombre}.`);
    setTimeout(() => irA('recordar'), 900);
  });

  const PISTAS = {
    superpuesto: ['lorena', 10 * 60, ['raiz']],
    servicio: ['diego', 13 * 60, ['raiz']],
  };

  /* ---------- 2. Recordar por WhatsApp ---------- */

  const chatCuerpo = $('[data-chat-cuerpo]');
  const borrador = $('[data-chat-borrador]');
  const botonEnviar = $('[data-chat-enviar]');
  const siguienteCobro = $('[data-siguiente="cobrar"]');

  function textoWhatsapp(t) {
    return `¡Hola ${t.cliente}! Te recordamos tu turno en Studio Bella: mañana a las ${hora(t.inicio)} `
      + `(${serviciosTexto(t)}), con ${estilista(t.estilista).nombre}. Si no podés venir, avisanos por acá, `
      + 'así le damos el lugar a otra persona. ¡Te esperamos!';
  }

  function burbuja(texto, recibida = false) {
    const el = document.createElement('p');
    el.className = `burbuja burbuja--entrando${recibida ? ' burbuja--recibida' : ''}`;
    el.style.margin = '0';
    el.textContent = texto;
    const marca = document.createElement('span');
    marca.className = 'burbuja__hora';
    marca.innerHTML = `${horaActual()}${recibida ? '' : ` ${icono('check')}`}`;
    el.append(marca);
    chatCuerpo.append(el);
  }

  function prepararRecordatorios() {
    const t = estado.turno;
    $('[data-recordatorios]').innerHTML = `
      <div class="recordatorio" data-fila-turno>
        <div class="recordatorio__dato"><b>${esc(t.cliente)}</b><small>${hora(t.inicio)} · ${esc(serviciosTexto(t))} · ${estilista(t.estilista).nombre} · ${esc(t.telefono || 'sin teléfono')}</small></div>
        <button class="btn btn--wa btn--chico" type="button" data-whatsapp>${icono('whatsapp')} WhatsApp</button>
      </div>`
      + AVISADOS_POR_CORREO.map((o) => `
      <div class="recordatorio recordatorio--enviado">
        <div class="recordatorio__dato"><b>${o.cliente}</b><small>${o.detalle}</small></div>
        <span class="recordatorio__estado">${icono('check')} Por correo</span>
      </div>`).join('');
    $('[data-chat-nombre]').textContent = t.cliente;
    $('[data-chat-numero]').textContent = numeroInternacional(t.telefono);
    chatCuerpo.innerHTML = '<span class="chat__fecha">Hoy</span>';
    borrador.textContent = 'Tocá “WhatsApp” en la lista para escribir el mensaje.';
    borrador.classList.remove('lleno');
    botonEnviar.disabled = true;
    siguienteCobro.hidden = true;
  }

  function escribirWhatsapp() {
    if (!estado.turno.telefono.replace(/\D/g, '')) {
      aviso('error', 'Falta el celular', 'Volvé al paso 1 y cargá el celular de la clienta.');
      return;
    }
    borrador.textContent = textoWhatsapp(estado.turno);
    borrador.classList.add('lleno');
    botonEnviar.disabled = false;
    if (window.innerWidth < 900) $('[data-chat]').scrollIntoView({ behavior: 'smooth', block: 'center' });
    botonEnviar.focus({ preventScroll: true });
  }

  botonEnviar.addEventListener('click', () => {
    burbuja(textoWhatsapp(estado.turno));
    borrador.textContent = 'Mensaje';
    borrador.classList.remove('lleno');
    botonEnviar.disabled = true;
    const fila = $('[data-fila-turno]');
    fila.classList.add('recordatorio--enviado');
    fila.querySelector('[data-whatsapp]').outerHTML = `<span class="recordatorio__estado">${icono('check')} Por WhatsApp</span>`;
    setTimeout(() => burbuja('¡Gracias! Ahí estoy 😊', true), 1400);
    prepararCobro();
    habilitarHasta('cobrar');
    siguienteCobro.hidden = false;
  });
  siguienteCobro.addEventListener('click', () => irA('cobrar'));

  /* ---------- 3. Cobrar ---------- */

  const formCobro = $('[data-form-cobro]');
  const errorCobro = $('[data-error-cobro]');
  const resultadoCobro = $('[data-resultado-cobro]');
  const vacioCobro = resultadoCobro.innerHTML;

  const totalCobro = () => estado.turno.total + (formCobro.shampoo.checked ? PRECIO_SHAMPOO : 0);

  function prepararCobro() {
    const t = estado.turno;
    $('[data-c="cliente"]').textContent = t.cliente.split(' ')[0];
    $('[data-lineas]').innerHTML = t.servicios.map((id) => `
      <li><span>${SERVICIOS[id].nombre}<br><small>${SERVICIOS[id].minutos} min · ${estilista(t.estilista).nombre}</small></span><b>${plata(SERVICIOS[id].precio)}</b></li>`).join('');
    $('[data-stock-shampoo]').textContent = cantidad(estado.stock.shampoo.cantidad);
    formCobro.shampoo.checked = false;
    formCobro.pago.value = 'efectivo';
    formCobro.querySelector('[type="submit"]').disabled = false;
    resultadoCobro.innerHTML = vacioCobro;
    actualizarCobro(true);
  }

  function actualizarCobro(sugerirEfectivo = false) {
    const total = totalCobro();
    $('[data-c="total"]').textContent = plata(total);
    $('[data-efectivo]').hidden = formCobro.pago.value !== 'efectivo';
    // Propone un billete redondo, como paga casi siempre el cliente.
    if (sugerirEfectivo) formCobro.recibido.value = gs(Math.ceil(total / 50000) * 50000);
    $('[data-c="vuelto"]').textContent = plata(Math.max(0, numero(formCobro.recibido.value) - total));
    errorCobro.hidden = true;
  }
  formCobro.addEventListener('input', (e) => actualizarCobro(e.target.name === 'shampoo'));
  formCobro.addEventListener('change', (e) => { if (e.target.name === 'pago') actualizarCobro(); });

  formCobro.addEventListener('submit', (evento) => {
    evento.preventDefault();
    if (estado.cobro) return;
    const total = totalCobro();
    const pago = formCobro.pago.value;
    const recibido = pago === 'efectivo' ? numero(formCobro.recibido.value) : 0;
    if (pago === 'efectivo' && recibido && recibido < total) {
      errorCobro.textContent = 'El efectivo recibido es menor que el total a cobrar.';
      errorCobro.hidden = false;
      return;
    }

    // Lo vendido y los insumos de cada servicio salen del depósito.
    const descuentos = {};
    estado.turno.servicios.forEach((id) => {
      Object.entries(SERVICIOS[id].insumos || {}).forEach(([producto, q]) => { descuentos[producto] = (descuentos[producto] || 0) + q; });
    });
    if (formCobro.shampoo.checked) descuentos.shampoo = (descuentos.shampoo || 0) + 1;
    Object.entries(descuentos).forEach(([producto, q]) => {
      estado.stock[producto].cantidad = Math.round((estado.stock[producto].cantidad - q) * 100) / 100;
    });

    estado.cobro = { total, pago, recibido, shampoo: formCobro.shampoo.checked, descuentos };
    $('[data-stock-shampoo]').textContent = cantidad(estado.stock.shampoo.cantidad);
    formCobro.querySelector('[type="submit"]').disabled = true;
    mostrarFactura();
    prepararReposicion();
    habilitarHasta('reponer');
    aviso('exito', `Cobrado ${plata(total)}`, 'Factura emitida, pago registrado y stock descontado.');
  });

  function mostrarFactura() {
    const t = estado.turno;
    const c = estado.cobro;
    const lineas = t.servicios.map((id) => [SERVICIOS[id].nombre, SERVICIOS[id].precio]);
    if (c.shampoo) lineas.push(['Shampoo reparador 300 ml', PRECIO_SHAMPOO]);
    const iva = Math.round(c.total / 11);
    const detallePago = c.pago === 'efectivo' && c.recibido
      ? `Pagó en efectivo: recibido ${plata(c.recibido)}, vuelto ${plata(c.recibido - c.total)}. Entró a la caja.`
      : `Pagó con ${NOMBRE_PAGO[c.pago]}. ${c.pago === 'efectivo' ? 'Entró a la caja.' : 'Entró al banco.'}`;
    const descuentos = Object.entries(c.descuentos);
    resultadoCobro.innerHTML = `
      <div class="factura">
        <div class="factura__cabeza">
          <div><b>Factura INV/2026/00014</b><small>${esc(t.cliente)}</small></div>
          <span class="factura__sello">PAGADA</span>
        </div>
        <table>
          <tbody>${lineas.map(([nombre, precio]) => `<tr><td>${nombre}</td><td>${plata(precio)}</td></tr>`).join('')}</tbody>
          <tfoot>
            <tr><td>Subtotal sin IVA</td><td>${plata(c.total - iva)}</td></tr>
            <tr><td>IVA 10 % (incluido en el precio)</td><td>${plata(iva)}</td></tr>
            <tr><td>Total</td><td>${plata(c.total)}</td></tr>
          </tfoot>
        </table>
        <p style="margin:12px 0 0;color:var(--suave);font-size:.88rem">${detallePago}</p>
      </div>
      <div class="movimientos">
        <h3>Se descontó del stock</h3>
        <ul>${descuentos.length
          ? descuentos.map(([producto, q]) => `<li><span>${estado.stock[producto].nombre}</span><b>−${cantidad(q)}</b></li>`).join('')
          : '<li>Nada: estos servicios no usan insumos.</li>'}</ul>
      </div>
      <button class="btn btn--primario" type="button" data-siguiente-reponer>Siguiente: ver el stock ${icono('flecha')}</button>`;
  }

  /* ---------- 4. Reponer ---------- */

  const bajoMinimo = () => Object.entries(estado.stock).filter(([, s]) => s.cantidad < s.minimo);

  function prepararReposicion() {
    dibujarStock();
    dibujarReposicion();
  }

  function dibujarStock() {
    $('[data-stock]').innerHTML = Object.values(estado.stock).map((s) => {
      const bajo = s.cantidad < s.minimo;
      return `
        <div class="stock__fila${bajo ? ' stock__fila--bajo' : ''}">
          <div class="stock__titulo"><b>${s.nombre}</b><span>${cantidad(s.cantidad)} · mínimo ${cantidad(s.minimo)}</span></div>
          <div class="stock__barra"><i style="width:${Math.min(100, (s.cantidad / s.maximo) * 100)}%"></i><span class="stock__minimo" style="left:${(s.minimo / s.maximo) * 100}%"></span></div>
        </div>`;
    }).join('');
  }

  const htmlFinal = () => `
    <div class="final">
      <h3>¡Listo! Eso es Studio Bella</h3>
      <p>Agendaste sin choques, avisaste por WhatsApp, cobraste con factura y el stock se repuso. En tu salón, todo esto queda guardado en Odoo.</p>
      <div class="grupo-botones">
        <a class="btn btn--acento" href="contacto.html?origen=demo">Pedí tu demo con tus datos</a>
        <button class="btn btn--fantasma" type="button" data-reiniciar>${icono('reiniciar')} Volver a empezar</button>
      </div>
    </div>`;

  function dibujarReposicion() {
    const zona = $('[data-reposicion]');
    const bajos = bajoMinimo();

    if (estado.recibido) {
      zona.innerHTML = `
        <div class="aviso-reponer aviso-reponer--ok">${icono('check-circulo')}
          <div><b>Mercadería recibida</b>El stock subió y los avisos de “Reponer stock” se cerraron solos.</div>
        </div>${htmlFinal()}`;
      return;
    }
    if (!bajos.length) {
      zona.innerHTML = `
        <div class="aviso-reponer aviso-reponer--ok">${icono('check-circulo')}
          <div><b>Todo en orden</b>Ningún producto bajó del mínimo. Para ver el aviso, volvé a empezar y agendá una Tintura de raíz.</div>
        </div>${htmlFinal()}`;
      return;
    }

    const avisos = bajos.map(([, s]) => `
      <div class="aviso-reponer">${icono('campana')}
        <div><b>Reponer stock: ${s.nombre}</b>Quedan ${cantidad(s.cantidad)} y el mínimo es ${cantidad(s.minimo)}. Conviene pedir ${cantidad(Math.ceil(s.maximo - s.cantidad))} para llegar a ${cantidad(s.maximo)}.</div>
      </div>`).join('');

    if (!estado.pedidos) {
      zona.innerHTML = `<div style="display:grid;gap:10px">${avisos}</div>
        <button class="btn btn--acento" type="button" data-pedir style="margin-top:16px">${icono('camion')} Armar el pedido al proveedor</button>`;
      return;
    }

    zona.innerHTML = `<div style="display:grid;gap:10px">${avisos}</div>${estado.pedidos.map((p) => `
      <div class="pedido">
        <h3><span>Pedido ${p.numero}</span><span class="chip chip--ciruela">Confirmado</span></h3>
        <p>${p.proveedor} · llega en 3 días</p>
        <ul class="lista-iconos" style="margin:0 0 10px;gap:6px;font-size:.92rem">
          ${p.lineas.map((l) => `<li>${icono('caja')} ${cantidad(l.cantidad)} × ${l.nombre} · ${plata(l.cantidad * l.costo)}</li>`).join('')}
        </ul>
        <b>Total ${plata(p.lineas.reduce((suma, l) => suma + l.cantidad * l.costo, 0))}</b>
      </div>`).join('')}
      <button class="btn btn--primario" type="button" data-recibir style="margin-top:16px">${icono('check')} Llegó la mercadería: validar recepción</button>`;
  }

  function armarPedidos() {
    const porProveedor = {};
    bajoMinimo().forEach(([id, s]) => {
      (porProveedor[s.proveedor] ||= []).push({ id, nombre: s.nombre, cantidad: Math.ceil(s.maximo - s.cantidad), costo: s.costo });
    });
    estado.pedidos = Object.entries(porProveedor).map(([proveedor, lineas], i) => ({ numero: `P0000${4 + i}`, proveedor, lineas }));
    dibujarReposicion();
    aviso('exito', 'Pedido confirmado', 'Se armó con el proveedor y el precio de compra de cada producto.');
  }

  function recibirMercaderia() {
    estado.pedidos.forEach((p) => p.lineas.forEach((l) => {
      estado.stock[l.id].cantidad = Math.round((estado.stock[l.id].cantidad + l.cantidad) * 100) / 100;
    }));
    estado.recibido = true;
    dibujarStock();
    dibujarReposicion();
    $$('[data-ir-paso]').forEach((b) => b.classList.add('hecho'));
    aviso('exito', 'Recepción validada', 'El stock subió y se cerraron los avisos de reponer.');
  }

  /* ---------- Botones que se dibujan sobre la marcha ---------- */

  raiz.addEventListener('click', (evento) => {
    const boton = evento.target.closest('button');
    if (!boton) return;
    if (boton.matches('[data-ir-paso]')) irA(boton.dataset.irPaso);
    else if (boton.matches('[data-pista]')) elegir(...PISTAS[boton.dataset.pista]);
    else if (boton.matches('[data-whatsapp]')) escribirWhatsapp();
    else if (boton.matches('[data-siguiente-reponer]')) irA('reponer');
    else if (boton.matches('[data-pedir]')) armarPedidos();
    else if (boton.matches('[data-recibir]')) recibirMercaderia();
    else if (boton.matches('[data-reiniciar]')) reiniciar();
  });

  function reiniciar() {
    estado = estadoInicial();
    elegir('lorena', 12 * 60, ['raiz', 'brushing']);
    dibujarAgenda();
    habilitarHasta('agendar');
    irA('agendar');
  }

  estado = estadoInicial();
  elegir('lorena', 12 * 60, ['raiz', 'brushing']);
  dibujarAgenda();

  // Desde el enlace "Verlo en la demo" de la portada se arranca en el recordatorio.
  if (location.hash === '#recordar') formTurno.requestSubmit();
})();
