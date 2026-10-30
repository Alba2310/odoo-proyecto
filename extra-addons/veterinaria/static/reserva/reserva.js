/*
 * Patitas: turnos por internet (/reservar). Una conversación: el dueño cuenta cómo se llama su mascota, qué es,
 * qué necesita, con quién y cuándo, y deja sus datos. Cada respuesta se puede cambiar tocando "cambiar".
 * Sin dependencias: los datos de la veterinaria llegan en data-datos y los horarios se piden a /reservar/horarios.
 */
(function () {
    "use strict";

    const app = document.getElementById("app");
    const DATOS = JSON.parse(app.dataset.datos);
    const chat = document.getElementById("chat");
    const respuesta = document.getElementById("respuesta");
    const botonReiniciar = document.getElementById("reiniciar");

    const PASOS = ["mascota", "especie", "servicios", "profesional", "dia", "datos", "confirmar", "listo"];
    const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
        "noviembre", "diciembre"];

    let estado = nuevoEstado();
    const horariosGuardados = {};

    function nuevoEstado() {
        return {
            paso: "mascota", mascota: "", especie: null, servicios: [], profesional: null, dias: null, dia: null,
            inicio: null, hora: null, nombre: "", telefono: "", email: "", nota: "", web: "", error: "",
            enviando: false, confirmacion: null,
        };
    }

    // Ayudas

    function el(etiqueta, atributos, ...hijos) {
        const nodo = document.createElement(etiqueta);
        for (const [clave, valor] of Object.entries(atributos || {})) {
            if (valor === false || valor === null || valor === undefined) {
                continue;
            }
            if (clave.startsWith("on")) {
                nodo.addEventListener(clave.slice(2), valor);
            } else if (clave === "class") {
                nodo.className = valor;
            } else {
                nodo.setAttribute(clave, valor === true ? "" : valor);
            }
        }
        for (const hijo of hijos.flat()) {
            if (hijo !== null && hijo !== undefined && hijo !== false) {
                nodo.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
            }
        }
        return nodo;
    }

    function plata(monto) {
        const moneda = DATOS.moneda;
        const numero = moneda.decimales
            ? Number(monto).toFixed(moneda.decimales).replace(".", ",")
            : String(Math.round(monto));
        const [entero, decimales] = numero.split(",");
        const conPuntos = entero.replace(/\B(?=(\d{3})+(?!\d))/g, ".") + (decimales ? "," + decimales : "");
        return moneda.antes ? `${moneda.simbolo} ${conPuntos}` : `${conPuntos} ${moneda.simbolo}`;
    }

    function indice(paso) {
        return PASOS.indexOf(paso);
    }

    function especie() {
        return DATOS.especies.find((e) => e.id === estado.especie);
    }

    function servicios() {
        return estado.servicios.map((id) => DATOS.servicios.find((s) => s.id === id)).filter(Boolean);
    }

    function area() {
        const elegidos = servicios();
        return elegidos.length ? elegidos[0].area : null;
    }

    function serviciosParaEspecie() {
        return DATOS.servicios.filter((s) => !s.especies.length || s.especies.includes(estado.especie));
    }

    function profesionalesPosibles() {
        const pedidos = servicios().filter((s) => s.es_servicio).map((s) => s.id);
        return DATOS.profesionales.filter((p) => p.areas.includes(area())
            && (!p.servicios.length || pedidos.every((id) => p.servicios.includes(id))));
    }

    function profesional() {
        return DATOS.profesionales.find((p) => p.id === estado.profesional);
    }

    /** "hoy 30 de octubre", "mañana 31 de octubre", "el lunes 2 de noviembre". */
    function textoDia(dia) {
        const [, mes, numero] = dia.fecha.split("-").map(Number);
        const articulo = ["Hoy", "Mañana"].includes(dia.semana) ? "" : "el ";
        return `${articulo}${dia.semana.toLowerCase()} ${numero} de ${MESES[mes - 1]}`;
    }

    function mayuscula(texto) {
        return texto.charAt(0).toUpperCase() + texto.slice(1);
    }

    async function rpc(url, params) {
        const respuestaHttp = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
        });
        const datos = await respuestaHttp.json();
        if (datos.error) {
            throw new Error((datos.error.data && datos.error.data.message) || "No se pudo conectar.");
        }
        return datos.result;
    }

    // Moverse por la conversación

    function ir(paso) {
        estado.paso = paso;
        estado.error = "";
        dibujar();
    }

    /** Volver a una respuesta anterior: lo que depende de ella se borra. */
    function volver(paso) {
        const desde = indice(paso);
        if (desde <= indice("especie")) {
            estado.servicios = [];
        }
        if (desde <= indice("servicios")) {
            estado.profesional = null;
        }
        if (desde <= indice("profesional")) {
            Object.assign(estado, { dias: null, dia: null, inicio: null, hora: null });
        }
        if (desde <= indice("dia")) {
            Object.assign(estado, { inicio: null, hora: null });
        }
        ir(paso);
    }

    function despuesDeServicios() {
        // Con una sola persona (o ninguna para elegir), no se pregunta con quién.
        if (profesionalesPosibles().length > 1) {
            ir("profesional");
        } else {
            estado.profesional = null;
            ir("dia");
        }
    }

    // Lo que dice la veterinaria y lo que contesta el dueño

    function bot(texto, nuevo) {
        chat.append(el("div", { class: `mensaje mensaje--bot${nuevo ? " mensaje--nuevo" : ""}` },
            el("img", { class: "mensaje__avatar", src: "/veterinaria/static/description/icon.png", alt: "" }),
            el("div", { class: "burbuja" }, texto)));
    }

    function usuario(texto, paso) {
        const cambiar = estado.paso === "listo" ? null : el("button", {
            class: "burbuja__cambiar", type: "button", onclick: () => volver(paso),
        }, "cambiar");
        chat.append(el("div", { class: "mensaje mensaje--yo" }, el("div", { class: "burbuja" }, texto, cambiar)));
    }

    function preguntas() {
        const nombre = estado.mascota;
        return {
            mascota: `¡Hola! Soy el asistente de turnos de ${DATOS.clinica}. ¿Cómo se llama tu mascota?`,
            especie: `¡Qué lindo nombre! ¿${nombre} es...?`,
            servicios: `¿Qué necesita ${nombre}? Podés elegir más de una cosa.`,
            profesional: `¿Preferís a alguien en especial para ${nombre}?`,
            dia: "¿Qué día les queda bien?",
            datos: "¡Ya casi! ¿A nombre de quién anoto el turno?",
            confirmar: "Te lo anoto así. ¿Está bien?",
        };
    }

    function respuestas() {
        const elegida = especie();
        const persona = profesional();
        const dia = estado.dias && estado.dias.find((d) => d.fecha === estado.dia);
        return {
            mascota: estado.mascota,
            especie: elegida ? `${elegida.emoji} ${elegida.nombre}` : "",
            servicios: servicios().map((s) => s.nombre).join(" + "),
            profesional: persona ? persona.nombre : "Me da igual",
            dia: dia && estado.hora ? mayuscula(`${textoDia(dia)} a las ${estado.hora}`) : "",
            datos: [estado.nombre, estado.telefono].filter(Boolean).join(" · "),
            confirmar: "¡Sí, confirmar!",
        };
    }

    function dibujar() {
        chat.replaceChildren();
        respuesta.replaceChildren();
        botonReiniciar.hidden = estado.paso === "mascota";
        const actual = indice(estado.paso);
        const textos = preguntas();
        const contestado = respuestas();
        const saltaProfesional = actual > indice("profesional") && !estado.profesional
            && profesionalesPosibles().length <= 1;

        for (const paso of PASOS.slice(0, Math.min(actual, indice("confirmar") + 1))) {
            if (paso === "profesional" && saltaProfesional) {
                continue;
            }
            bot(textos[paso]);
            usuario(contestado[paso], paso);
        }
        if (estado.paso === "listo") {
            dibujarListo();
        } else {
            if (estado.paso === "confirmar") {
                bot(textos.confirmar, true);
                chat.append(resumen());
            } else {
                bot(textos[estado.paso], true);
            }
            const dibujantes = {
                mascota: pasoMascota, especie: pasoEspecie, servicios: pasoServicios, profesional: pasoProfesional,
                dia: pasoDia, datos: pasoDatos, confirmar: pasoConfirmar,
            };
            dibujantes[estado.paso]();
        }
        if (estado.error) {
            respuesta.prepend(el("p", { class: "aviso", role: "alert" }, estado.error));
        }
        // Se muestra la pregunta nueva arriba: las opciones largas (los servicios) quedan debajo para recorrer.
        const pregunta = chat.querySelector(".mensaje--nuevo") || chat.lastElementChild;
        requestAnimationFrame(() => pregunta.scrollIntoView({ block: "start", behavior: "smooth" }));
    }

    // Cada paso

    function pasoMascota() {
        const entrada = el("input", {
            class: "campo", name: "mascota", maxlength: "60", autocomplete: "off", placeholder: "Por ejemplo: Toby",
            value: estado.mascota, "aria-label": "Nombre de tu mascota",
        });
        const seguir = () => {
            const nombre = entrada.value.trim();
            if (!nombre) {
                entrada.focus();
                return;
            }
            estado.mascota = nombre.charAt(0).toUpperCase() + nombre.slice(1);
            ir("especie");
        };
        entrada.addEventListener("keydown", (evento) => evento.key === "Enter" && seguir());
        respuesta.append(el("div", { class: "escribir" }, entrada,
            el("button", { class: "boton", type: "button", onclick: seguir }, "Seguir")));
        setTimeout(() => entrada.focus(), 50);
    }

    function pasoEspecie() {
        respuesta.append(el("div", { class: "opciones opciones--especies" }, DATOS.especies.map((opcion) =>
            el("button", {
                class: `opcion opcion--especie${estado.especie === opcion.id ? " opcion--elegida" : ""}`,
                type: "button",
                onclick: () => {
                    if (estado.especie !== opcion.id) {
                        estado.servicios = [];
                    }
                    estado.especie = opcion.id;
                    ir("servicios");
                },
            }, el("span", { class: "opcion__emoji" }, opcion.emoji), opcion.nombre))));
    }

    function pasoServicios() {
        const posibles = serviciosParaEspecie();
        const elegida = area();
        const grupos = DATOS.areas.map((grupo) => {
            const propios = posibles.filter((s) => s.area === grupo.clave);
            if (!propios.length) {
                return null;
            }
            const bloqueado = elegida && elegida !== grupo.clave;
            return el("div", { class: `grupo${bloqueado ? " grupo--bloqueado" : ""}` },
                el("h3", { class: "grupo__titulo" }, grupo.nombre,
                    bloqueado ? el("small", {}, " · se pide en otro turno") : null),
                el("div", { class: "opciones" }, propios.map((servicio) => {
                    const marcado = estado.servicios.includes(servicio.id);
                    return el("button", {
                        class: `opcion opcion--servicio${marcado ? " opcion--elegida" : ""}`,
                        type: "button",
                        disabled: bloqueado,
                        "aria-pressed": marcado ? "true" : "false",
                        onclick: () => {
                            estado.servicios = marcado
                                ? estado.servicios.filter((id) => id !== servicio.id)
                                : [...estado.servicios, servicio.id];
                            dibujar();
                        },
                    },
                    el("span", { class: "opcion__nombre" }, servicio.nombre),
                    el("span", { class: "opcion__detalle" }, `${servicio.duracion} min · ${plata(servicio.precio)}`));
                })));
        }).filter(Boolean);
        if (!grupos.length) {
            respuesta.append(el("p", { class: "aviso" },
                "Por ahora no tenemos turnos por internet para esta mascota. Escribinos o llamanos, por favor."));
            return;
        }
        const total = servicios().reduce((suma, s) => suma + s.precio, 0);
        respuesta.append(...grupos, el("div", { class: "pie-paso" },
            el("span", { class: "pie-paso__total" }, estado.servicios.length
                ? `Total aproximado: ${plata(total)} (con IVA)` : "Elegí al menos una opción."),
            el("button", {
                class: "boton", type: "button", disabled: !estado.servicios.length, onclick: despuesDeServicios,
            }, "Listo")));
    }

    function pasoProfesional() {
        const opciones = profesionalesPosibles().map((persona) => el("button", {
            class: `opcion${estado.profesional === persona.id ? " opcion--elegida" : ""}`, type: "button",
            onclick: () => {
                estado.profesional = persona.id;
                Object.assign(estado, { dias: null, dia: null, inicio: null, hora: null });
                ir("dia");
            },
        }, persona.nombre));
        respuesta.append(el("div", { class: "opciones" },
            el("button", {
                class: `opcion opcion--destacada${!estado.profesional ? " opcion--elegida" : ""}`, type: "button",
                onclick: () => {
                    estado.profesional = null;
                    Object.assign(estado, { dias: null, dia: null, inicio: null, hora: null });
                    ir("dia");
                },
            }, "Me da igual: el primer horario libre"), opciones));
    }

    async function pasoDia() {
        const clave = `${estado.servicios.join(",")}|${estado.profesional || ""}`;
        if (!estado.dias) {
            respuesta.append(el("p", { class: "cargando" }, "Buscando horarios libres..."));
            try {
                const dias = horariosGuardados[clave] || await rpc("/reservar/horarios", {
                    servicio_ids: estado.servicios, profesional_id: estado.profesional,
                });
                if (dias.error) {
                    throw new Error(dias.error);
                }
                horariosGuardados[clave] = dias;
                estado.dias = dias;
            } catch (error) {
                estado.error = error.message;
                respuesta.replaceChildren(el("p", { class: "aviso", role: "alert" }, error.message));
                return;
            }
            dibujar();
            return;
        }
        const conLugar = estado.dias.filter((dia) => dia.horarios.length);
        if (!conLugar.length) {
            respuesta.append(el("p", { class: "aviso" },
                "No nos quedan horarios libres en las próximas dos semanas para esto. Escribinos y lo vemos juntos."),
            botonWhatsapp("Escribir por WhatsApp", `Hola, quiero un turno para ${estado.mascota}.`));
            return;
        }
        if (!estado.dia || !conLugar.some((dia) => dia.fecha === estado.dia)) {
            estado.dia = conLugar[0].fecha;
        }
        const tira = el("div", { class: "dias" }, estado.dias.map((dia) => el("button", {
            class: `dia${dia.fecha === estado.dia ? " dia--elegido" : ""}`, type: "button",
            disabled: !dia.horarios.length,
            onclick: () => {
                estado.dia = dia.fecha;
                dibujar();
            },
        }, el("span", { class: "dia__semana" }, dia.semana), el("span", { class: "dia__numero" }, dia.dia),
        el("span", { class: "dia__mes" }, dia.mes.slice(0, 3)))));
        const delDia = estado.dias.find((dia) => dia.fecha === estado.dia);
        const horas = el("div", { class: "horas" }, delDia.horarios.map((horario) => el("button", {
            class: `hora${estado.inicio === horario.inicio ? " hora--elegida" : ""}`, type: "button",
            onclick: () => {
                Object.assign(estado, { inicio: horario.inicio, hora: horario.hora });
                ir("datos");
            },
        }, horario.hora)));
        respuesta.append(tira, horas);
        const elegido = tira.querySelector(".dia--elegido");
        if (elegido) {
            elegido.scrollIntoView({ block: "nearest", inline: "center" });
        }
    }

    function pasoDatos() {
        const campo = (nombre, etiqueta, atributos) => el("label", { class: "etiqueta" },
            el("span", {}, etiqueta),
            el(atributos.multilinea ? "textarea" : "input", {
                class: "campo", name: nombre, value: atributos.multilinea ? null : estado[nombre], ...atributos.html,
            }, atributos.multilinea ? estado[nombre] : null));
        const formulario = el("form", { class: "formulario", novalidate: true },
            campo("nombre", "Tu nombre y apellido", { html: { autocomplete: "name", maxlength: "80", required: true } }),
            campo("telefono", "Tu celular (para avisarte)", {
                html: { type: "tel", autocomplete: "tel", inputmode: "tel", maxlength: "30", placeholder: "0981 123 456",
                    required: true },
            }),
            campo("email", "Correo (opcional)", { html: { type: "email", autocomplete: "email", maxlength: "120" } }),
            campo("nota", `¿Algo que tengamos que saber de ${estado.mascota}? (opcional)`, {
                multilinea: true,
                html: { rows: "2", maxlength: "300", placeholder: "Por ejemplo: está con vómitos, es miedosa, muerde..." },
            }),
            el("label", { class: "trampa", "aria-hidden": "true" }, "No completar",
                el("input", { name: "web", tabindex: "-1", autocomplete: "off" })),
            el("button", { class: "boton boton--ancho", type: "submit" }, "Seguir"));
        formulario.addEventListener("submit", (evento) => {
            evento.preventDefault();
            const valores = Object.fromEntries(new FormData(formulario).entries());
            Object.assign(estado, {
                nombre: (valores.nombre || "").trim(), telefono: (valores.telefono || "").trim(),
                email: (valores.email || "").trim(), nota: (valores.nota || "").trim(), web: valores.web || "",
            });
            if (!estado.nombre) {
                estado.error = "Escribí tu nombre, por favor.";
            } else if ((estado.telefono.match(/\d/g) || []).length < 8) {
                estado.error = "Revisá el celular: escribilo con la característica, por ejemplo 0981 123 456.";
            } else {
                ir("confirmar");
                return;
            }
            dibujar();
        });
        respuesta.append(formulario);
    }

    function resumen() {
        const elegida = especie();
        const persona = profesional();
        const dia = estado.dias.find((d) => d.fecha === estado.dia);
        const total = servicios().reduce((suma, s) => suma + s.precio, 0);
        const fila = (etiqueta, valor) => el("div", { class: "resumen__fila" }, el("dt", {}, etiqueta), el("dd", {}, valor));
        return el("div", { class: "mensaje mensaje--bot mensaje--tarjeta" }, el("dl", { class: "resumen" },
            fila("Mascota", `${elegida.emoji} ${estado.mascota}`),
            fila("Para", servicios().map((s) => s.nombre).join(" + ")),
            fila("Cuándo", mayuscula(`${textoDia(dia)} a las ${estado.hora}`)),
            fila("Con", persona ? persona.nombre : "Quien esté libre"),
            fila("A nombre de", `${estado.nombre} · ${estado.telefono}`),
            fila("Total aproximado", plata(total))));
    }

    function pasoConfirmar() {
        const boton = el("button", {
            class: "boton boton--ancho", type: "button", disabled: estado.enviando, onclick: confirmar,
        }, estado.enviando ? "Anotando..." : "Confirmar el turno");
        respuesta.append(boton);
    }

    async function confirmar() {
        estado.enviando = true;
        estado.error = "";
        dibujar();
        try {
            const resultado = await rpc("/reservar/confirmar", {
                servicio_ids: estado.servicios,
                profesional_id: estado.profesional,
                inicio: estado.inicio,
                web: estado.web,
                datos: {
                    mascota: estado.mascota, especie_id: estado.especie, nombre: estado.nombre,
                    telefono: estado.telefono, email: estado.email, nota: estado.nota,
                },
            });
            estado.enviando = false;
            if (resultado.error) {
                estado.error = resultado.error;
                if (/horario/i.test(resultado.error)) {
                    // Otro dueño se llevó el horario: se vuelven a pedir los libres.
                    delete horariosGuardados[`${estado.servicios.join(",")}|${estado.profesional || ""}`];
                    Object.assign(estado, { dias: null, inicio: null, hora: null, paso: "dia" });
                }
                dibujar();
                return;
            }
            estado.confirmacion = resultado;
            ir("listo");
        } catch (error) {
            estado.enviando = false;
            estado.error = error.message;
            dibujar();
        }
    }

    function botonWhatsapp(texto, mensaje) {
        if (!DATOS.whatsapp) {
            return DATOS.telefono ? el("p", { class: "ayuda" }, `O llamanos al ${DATOS.telefono}.`) : null;
        }
        return el("a", {
            class: "boton boton--wa", target: "_blank", rel: "noopener",
            href: `https://wa.me/${DATOS.whatsapp}?text=${encodeURIComponent(mensaje)}`,
        }, texto);
    }

    function dibujarListo() {
        const listo = estado.confirmacion;
        chat.append(el("div", { class: "mensaje mensaje--bot mensaje--tarjeta mensaje--nuevo" },
            el("div", { class: "listo" },
                el("div", { class: "listo__icono", "aria-hidden": "true" }, "🎉"),
                el("h2", {}, `¡Listo, ${listo.nombre}!`),
                el("p", { class: "listo__texto" },
                    `${listo.mascota} tiene turno el ${listo.turno} con ${listo.profesional} (${listo.servicios}).`),
                el("p", { class: "ayuda" },
                    "Si no pueden venir, avisanos así le damos el lugar a otra mascota."))));
        const whatsapp = listo.whatsapp ? el("a", {
            class: "boton boton--wa", target: "_blank", rel: "noopener", href: listo.whatsapp,
        }, "Avisar por WhatsApp") : null;
        respuesta.append(el("div", { class: "pie-paso pie-paso--columna" }, whatsapp,
            el("button", { class: "boton boton--claro", type: "button", onclick: reiniciar }, "Pedir otro turno")));
    }

    function reiniciar() {
        estado = nuevoEstado();
        dibujar();
    }

    botonReiniciar.addEventListener("click", reiniciar);
    dibujar();
})();
