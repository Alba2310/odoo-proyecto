/* Página de turnos de Studio Bella (/turnos): la clienta reserva sola en cuatro pasos.
 * Los servicios y estilistas vienen en data-datos; los horarios libres y la reserva, del servidor. */
(function () {
    'use strict';

    const raiz = document.getElementById('turnos');
    if (!raiz) {
        return;
    }
    const datos = JSON.parse(raiz.dataset.datos);
    const $ = (selector) => raiz.querySelector(selector);

    const estado = {
        paso: 1,
        servicios: [], // ids, en el orden en que se eligieron
        estilista: 0, // 0: cualquiera
        dias: null, // horarios libres por día; null: hay que pedirlos
        dia: null,
        horario: null,
        enviando: false,
    };
    const servicios = new Map();
    datos.categorias.forEach((categoria) => categoria.servicios.forEach((servicio) => servicios.set(servicio.id, servicio)));

    // Formatos

    const numero = new Intl.NumberFormat('es-PY', {
        minimumFractionDigits: datos.moneda.decimales,
        maximumFractionDigits: datos.moneda.decimales,
    });

    function precio(monto) {
        const texto = numero.format(monto);
        return datos.moneda.antes ? `${datos.moneda.simbolo} ${texto}` : `${texto} ${datos.moneda.simbolo}`;
    }

    function duracion(minutos) {
        const horas = Math.floor(minutos / 60);
        const resto = minutos % 60;
        if (!horas) {
            return `${resto} min`;
        }
        return resto ? `${horas} h ${resto} min` : `${horas} h`;
    }

    function iniciales(nombre) {
        return nombre.split(/\s+/).slice(0, 2).map((parte) => parte[0]).join('').toUpperCase();
    }

    /** Crea un elemento; el texto se agrega como texto (nunca como HTML). */
    function el(etiqueta, atributos, ...hijos) {
        const nodo = document.createElement(etiqueta);
        for (const [clave, valor] of Object.entries(atributos || {})) {
            if (valor === false || valor === null || valor === undefined) {
                continue;
            }
            if (clave === 'class') {
                nodo.className = valor;
            } else if (clave.startsWith('on')) {
                nodo.addEventListener(clave.slice(2), valor);
            } else {
                nodo.setAttribute(clave, valor === true ? '' : valor);
            }
        }
        nodo.append(...hijos.flat(Infinity).filter((hijo) => hijo !== null && hijo !== false && hijo !== undefined));
        return nodo;
    }

    // Lo elegido

    const elegidos = () => estado.servicios.map((id) => servicios.get(id));
    const minutos = () => elegidos().reduce((total, servicio) => total + servicio.duracion, 0);
    const total = () => elegidos().reduce((suma, servicio) => suma + servicio.precio, 0);
    const diaElegido = () => (estado.dias || []).find((dia) => dia.fecha === estado.dia);

    function estilistasPosibles() {
        return datos.estilistas.filter((estilista) => !estilista.servicios.length
            || estado.servicios.every((id) => estilista.servicios.includes(id)));
    }

    function nombreEstilista() {
        const estilista = datos.estilistas.find((opcion) => opcion.id === estado.estilista);
        return estilista ? estilista.nombre : 'El primero libre';
    }

    function textoDia(dia) {
        return `${dia.semana} ${dia.dia} de ${dia.mes}`;
    }

    function olvidarHorario() {
        estado.dias = null;
        estado.horario = null;
    }

    // Servidor (JSON-RPC de Odoo)

    async function pedir(ruta, parametros) {
        const respuesta = await fetch(ruta, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: parametros}),
        });
        const json = await respuesta.json();
        if (json.error) {
            throw new Error((json.error.data && json.error.data.message) || json.error.message);
        }
        return json.result;
    }

    // Paso 1: servicios

    function alternarServicio(id, elegido) {
        estado.servicios = estado.servicios.filter((otro) => otro !== id);
        if (elegido) {
            estado.servicios.push(id);
        }
        if (estado.estilista && !estilistasPosibles().some((estilista) => estilista.id === estado.estilista)) {
            estado.estilista = 0;
        }
        olvidarHorario();
        actualizar();
    }

    function pintarServicios() {
        const caja = $('#servicios');
        if (!datos.categorias.length) {
            caja.replaceChildren(el('p', {class: 'vacio'}, 'Por ahora no hay servicios para reservar por internet. Llamanos y te damos un turno.'));
            return;
        }
        caja.replaceChildren(...datos.categorias.map((categoria) => el('fieldset', {class: 'grupo'},
            el('legend', {}, categoria.nombre),
            categoria.servicios.map((servicio) => el('label', {class: 'servicio'},
                el('input', {
                    type: 'checkbox',
                    value: servicio.id,
                    checked: estado.servicios.includes(servicio.id),
                    onchange: (evento) => alternarServicio(servicio.id, evento.target.checked),
                }),
                el('span', {class: 'servicio__nombre'}, servicio.nombre),
                el('span', {class: 'servicio__detalle'}, duracion(servicio.duracion)),
                el('b', {class: 'servicio__precio'}, precio(servicio.precio)),
            )),
        )));
    }

    // Paso 2: estilista

    function pintarEstilistas() {
        const posibles = estilistasPosibles();
        if (!posibles.length) {
            $('#estilistas').replaceChildren(el('p', {class: 'vacio'},
                'Nadie hace todos esos servicios en el mismo turno. Probá reservarlos por separado o llamanos.'));
            return;
        }
        const opciones = [{id: 0, nombre: 'Cualquiera', detalle: 'Te damos el primer horario libre'}].concat(posibles);
        $('#estilistas').replaceChildren(...opciones.map((opcion) => el('label', {class: 'opcion'},
            el('input', {
                type: 'radio',
                name: 'estilista',
                value: opcion.id,
                checked: estado.estilista === opcion.id,
                onchange: () => {
                    estado.estilista = opcion.id;
                    olvidarHorario();
                    actualizar();
                },
            }),
            el('span', {class: 'avatar', 'aria-hidden': 'true'}, opcion.id ? iniciales(opcion.nombre) : '✦'),
            el('span', {class: 'opcion__texto'}, el('b', {}, opcion.nombre), opcion.detalle ? el('small', {}, opcion.detalle) : null),
        )));
    }

    // Paso 3: día y hora

    async function cargarHorarios() {
        $('#dias').replaceChildren();
        $('#horarios').replaceChildren(el('p', {class: 'cargando'}, 'Buscando horarios libres…'));
        try {
            estado.dias = await pedir('/turnos/horarios', {
                servicio_ids: estado.servicios,
                estilista_id: estado.estilista || null,
            });
        } catch (error) {
            $('#horarios').replaceChildren(el('p', {class: 'vacio'},
                'No pudimos traer los horarios. Revisá tu conexión e intentá de nuevo.'));
            return;
        }
        const dia = diaElegido();
        if (!dia || !dia.horarios.length) {
            const primero = estado.dias.find((opcion) => opcion.horarios.length);
            estado.dia = primero ? primero.fecha : null;
        }
        pintarDias();
        pintarHorarios();
    }

    function pintarDias() {
        $('#dias').replaceChildren(...(estado.dias || []).map((dia) => el('button', {
            type: 'button',
            class: dia.fecha === estado.dia ? 'dia dia--activo' : 'dia',
            disabled: !dia.horarios.length,
            'aria-pressed': String(dia.fecha === estado.dia),
            'aria-label': textoDia(dia) + (dia.horarios.length ? '' : ', sin horarios libres'),
            onclick: () => {
                estado.dia = dia.fecha;
                estado.horario = null;
                pintarDias();
                pintarHorarios();
                actualizar();
            },
        }, el('small', {}, dia.semana), el('b', {}, String(dia.dia)), el('small', {}, dia.mes))));
        const activo = $('.dia--activo');
        if (activo) {
            activo.scrollIntoView({block: 'nearest', inline: 'nearest'});
        }
    }

    function pintarHorarios() {
        const dia = diaElegido();
        if (!dia) {
            $('#horarios').replaceChildren(el('p', {class: 'vacio'},
                'No quedan horarios libres en los próximos días. Probá con otra estilista o llamanos.'));
            return;
        }
        const franjas = [['Mañana', (horario) => horario.hora < '12:00'], ['Tarde', (horario) => horario.hora >= '12:00']];
        $('#horarios').replaceChildren(...franjas.map(([titulo, filtro]) => {
            const horarios = dia.horarios.filter(filtro);
            return horarios.length ? el('div', {class: 'franja'},
                el('h3', {}, titulo),
                el('div', {class: 'franja__horas'}, horarios.map((horario) => {
                    const activo = estado.horario && estado.horario.inicio === horario.inicio;
                    return el('button', {
                        type: 'button',
                        class: activo ? 'hora hora--activa' : 'hora',
                        'aria-pressed': String(Boolean(activo)),
                        onclick: () => {
                            estado.horario = horario;
                            pintarHorarios();
                            actualizar();
                        },
                    }, horario.hora);
                })),
            ) : null;
        }).filter(Boolean));
    }

    // Paso 4: datos y reserva

    function pintarResumen() {
        const dia = diaElegido();
        const filas = [
            ['Servicios', elegidos().map((servicio) => servicio.nombre).join(' + ')],
            ['Con', nombreEstilista()],
            ['Cuándo', dia && estado.horario ? `${textoDia(dia)}, a las ${estado.horario.hora}` : ''],
            ['Duración', duracion(minutos())],
            ['Total', precio(total())],
        ];
        $('#resumen').replaceChildren(el('dl', {}, filas.map(([titulo, valor]) => [el('dt', {}, titulo), el('dd', {}, valor)])));
    }

    function avisar(mensaje, campo) {
        const aviso = $('#aviso');
        aviso.textContent = mensaje;
        aviso.hidden = !mensaje;
        if (mensaje) {
            (campo || aviso).scrollIntoView({block: 'center', behavior: 'smooth'});
            if (campo) {
                campo.focus({preventScroll: true});
            }
        }
    }

    async function reservar() {
        const formulario = $('#formulario');
        const valores = Object.fromEntries(new FormData(formulario));
        if (!valores.nombre.trim()) {
            avisar('Escribí tu nombre.', formulario.elements.nombre);
            return;
        }
        if (valores.telefono.replace(/\D/g, '').length < 7) {
            avisar('Escribí tu número de celular, con la característica.', formulario.elements.telefono);
            return;
        }
        avisar('');
        estado.enviando = true;
        actualizar();
        try {
            const respuesta = await pedir('/turnos/reservar', Object.assign(valores, {
                servicio_ids: estado.servicios,
                estilista_id: estado.estilista || null,
                inicio: estado.horario.inicio,
            }));
            if (respuesta.error) {
                if (/horario/i.test(respuesta.error)) {
                    olvidarHorario();
                    irA(3);
                }
                avisar(respuesta.error);
                return;
            }
            mostrarListo(respuesta);
        } catch (error) {
            avisar('No pudimos reservar el turno. Revisá tu conexión e intentá de nuevo.');
        } finally {
            estado.enviando = false;
            actualizar();
        }
    }

    function mostrarListo(respuesta) {
        raiz.querySelectorAll('.paso, #pasos, #barra').forEach((nodo) => {
            nodo.hidden = true;
        });
        $('#listo-titulo').textContent = `¡Listo, ${respuesta.nombre}!`;
        $('#listo-texto').replaceChildren('Te esperamos el ', el('b', {}, respuesta.turno),
            ` para ${respuesta.servicios}, con ${respuesta.estilista}.`);
        const whatsapp = $('#listo-whatsapp');
        if (respuesta.whatsapp) {
            whatsapp.href = respuesta.whatsapp;
            whatsapp.hidden = false;
        }
        $('#listo').hidden = false;
        window.scrollTo({top: 0});
    }

    // Navegación

    function puedeSeguir() {
        switch (estado.paso) {
            case 1: return estado.servicios.length > 0;
            case 2: return estilistasPosibles().length > 0;
            case 3: return Boolean(estado.horario);
            default: return !estado.enviando;
        }
    }

    function irA(paso) {
        estado.paso = paso;
        raiz.querySelectorAll('section.paso').forEach((seccion) => {
            seccion.hidden = Number(seccion.dataset.paso) !== paso;
        });
        raiz.querySelectorAll('#pasos li').forEach((item) => {
            const numeroPaso = Number(item.dataset.paso);
            item.classList.toggle('activo', numeroPaso === paso);
            item.classList.toggle('hecho', numeroPaso < paso);
            if (numeroPaso === paso) {
                item.setAttribute('aria-current', 'step');
            } else {
                item.removeAttribute('aria-current');
            }
        });
        avisar('');
        if (paso === 1) {
            pintarServicios();
        } else if (paso === 2) {
            pintarEstilistas();
        } else if (paso === 3) {
            if (estado.dias) {
                pintarDias();
                pintarHorarios();
            } else {
                cargarHorarios();
            }
        } else {
            pintarResumen();
        }
        actualizar();
        window.scrollTo({top: 0});
    }

    function actualizar() {
        const cantidad = estado.servicios.length;
        const resumen = $('#barra-resumen');
        if (!cantidad) {
            resumen.replaceChildren('Elegí uno o más servicios');
        } else {
            const dia = diaElegido();
            const cuando = estado.paso >= 3 && dia && estado.horario;
            resumen.replaceChildren(...[
                el('b', {}, precio(total())),
                el('span', {class: 'barra__detalle'}, cuando
                    ? `${dia.semana} ${dia.dia} ${dia.mes} · ${estado.horario.hora}`
                    : `${duracion(minutos())} · ${cantidad} ${cantidad === 1 ? 'servicio' : 'servicios'}`),
            ]);
        }
        const siguiente = $('#siguiente');
        siguiente.disabled = !puedeSeguir();
        siguiente.textContent = estado.paso === 4 ? (estado.enviando ? 'Reservando…' : 'Reservar') : 'Siguiente';
        $('#atras').hidden = estado.paso === 1;
    }

    $('#siguiente').addEventListener('click', () => {
        if (!puedeSeguir()) {
            return;
        }
        if (estado.paso < 4) {
            irA(estado.paso + 1);
        } else {
            reservar();
        }
    });
    $('#atras').addEventListener('click', () => irA(Math.max(1, estado.paso - 1)));
    $('#formulario').addEventListener('submit', (evento) => {
        evento.preventDefault();
        reservar();
    });
    $('#otro').addEventListener('click', () => window.location.reload());

    if (datos.telefono) {
        const pie = $('#pie');
        pie.replaceChildren('¿Dudas? Llamanos al ', el('a', {href: `tel:${datos.telefono.replace(/[^\d+]/g, '')}`}, datos.telefono));
        pie.hidden = false;
    }
    irA(1);
})();
