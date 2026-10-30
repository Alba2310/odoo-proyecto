/* ==========================================================================
   Patitas · el juego de la sala de espera
   Llegan mascotas a la sala; se pasan al consultorio (dos lugares), se espera que las atiendan y se cobran.
   Si una espera demasiado, se va y se pierde una vida. Se juega arrastrando o tocando las tarjetas.
   ========================================================================== */
(function () {
  "use strict";

  const DURACION = 60;            // segundos que dura el día
  const VIDAS = 3;
  const LUGARES_CONSULTORIO = 2;  // dos veterinarios
  const MAXIMO_SALA = 8;
  const MAXIMO_COBRAR = 4;
  const PACIENCIA = 11;           // segundos que una mascota espera antes de irse
  const MOVER_PARA_ARRASTRAR = 8; // píxeles que hay que mover el dedo para que sea arrastrar y no tocar

  const MASCOTAS = ["🐶", "🐱", "🐰", "🐹", "🐦", "🐕", "🐈", "🐩", "🐢"];
  const NOMBRES = ["Toby", "Luna", "Michi", "Rocky", "Coco", "Nala", "Simba", "Kiara", "Thor", "Pelusa", "Max",
    "Milo", "Bobby", "Chispa", "Lola", "Manchita", "Firulais", "Pirata", "Canela", "Chocolate", "Bigote"];
  const SERVICIOS = [
    { que: "Vacuna", precio: 60000, tiempo: 1.8 },
    { que: "Consulta", precio: 120000, tiempo: 2.6 },
    { que: "Baño", precio: 90000, tiempo: 3.2 },
    { que: "Uñas", precio: 20000, tiempo: 1.3 },
    { que: "Control", precio: 60000, tiempo: 2.0 },
  ];

  const tablero = document.getElementById("juego-tablero");
  if (!tablero) {
    return;
  }
  const listas = {
    sala: tablero.querySelector('[data-columna="sala"] .juego__lista'),
    consultorio: tablero.querySelector('[data-columna="consultorio"] .juego__lista'),
    cobrar: tablero.querySelector('[data-columna="cobrar"] .juego__lista'),
  };
  const ver = {
    tiempo: document.getElementById("juego-tiempo"),
    puntos: document.getElementById("juego-puntos"),
    plata: document.getElementById("juego-plata"),
    vidas: document.getElementById("juego-vidas"),
    aviso: document.getElementById("juego-aviso"),
    cartel: document.getElementById("juego-cartel"),
    cartelEmoji: document.getElementById("juego-cartel-emoji"),
    cartelTitulo: document.getElementById("juego-cartel-titulo"),
    cartelTexto: document.getElementById("juego-cartel-texto"),
    empezar: document.getElementById("juego-empezar"),
    compartir: document.getElementById("juego-compartir"),
    record: document.getElementById("juego-record"),
    sonido: document.getElementById("juego-sonido"),
  };
  const sonar = (tipo) => window.Patitas && window.Patitas.sonar(tipo);
  const guaranies = (monto) => "Gs. " + Math.round(monto).toLocaleString("es-PY").replace(/,/g, ".");
  const alAzar = (lista) => lista[Math.floor(Math.random() * lista.length)];

  let estado = null;
  let siguienteId = 1;
  let ocultarAviso = null;

  function leerRecord() {
    try {
      return Number(localStorage.getItem("patitas-record")) || 0;
    } catch (error) {
      return 0;
    }
  }

  function guardarRecord(puntos) {
    try {
      localStorage.setItem("patitas-record", String(puntos));
    } catch (error) {
      /* sin almacenamiento: no se guarda el récord */
    }
  }

  function avisar(texto) {
    ver.aviso.textContent = texto;
    clearTimeout(ocultarAviso);
    ocultarAviso = setTimeout(() => { ver.aviso.textContent = ""; }, 2600);
  }

  function enColumna(columna) {
    return [...estado.bichos.values()].filter((bicho) => bicho.columna === columna);
  }

  // Las mascotas

  function crearBicho() {
    const bicho = {
      id: siguienteId++,
      emoji: alAzar(MASCOTAS),
      nombre: alAzar(NOMBRES),
      servicio: alAzar(SERVICIOS),
      columna: "sala",
      espera: PACIENCIA,
      progreso: 0,
      terminado: false,
    };
    const el = document.createElement("button");
    el.type = "button";
    el.className = "bicho";
    el.innerHTML = `
      <span class="bicho__emoji" aria-hidden="true">${bicho.emoji}</span>
      <span><span class="bicho__nombre">${bicho.nombre}</span><span class="bicho__que"></span></span>
      <span class="bicho__barra" aria-hidden="true"><i></i></span>`;
    bicho.el = el;
    bicho.que = el.querySelector(".bicho__que");
    bicho.barra = el.querySelector(".bicho__barra i");
    escucharArrastre(bicho);
    el.addEventListener("click", () => {
      if (bicho.sinClick) {
        bicho.sinClick = false;
        return;
      }
      avanzar(bicho);
    });
    estado.bichos.set(bicho.id, bicho);
    listas.sala.append(el);
    pintar(bicho);
  }

  function pintar(bicho) {
    const textos = {
      sala: `${bicho.servicio.que} · esperando`,
      consultorio: bicho.terminado ? "✔ ¡Listo! Pasalo a cobrar" : `${bicho.servicio.que}: atendiendo…`,
      cobrar: `💰 Tocá para cobrar ${guaranies(bicho.servicio.precio)}`,
    };
    bicho.que.textContent = textos[bicho.columna];
    bicho.el.classList.toggle("bicho--atendiendo", bicho.columna === "consultorio" && !bicho.terminado);
    bicho.el.classList.toggle("bicho--terminado", bicho.columna === "consultorio" && bicho.terminado);
    bicho.el.classList.toggle("bicho--cobrar", bicho.columna === "cobrar");
    bicho.el.setAttribute("aria-label", `${bicho.nombre}: ${textos[bicho.columna]}`);
  }

  function sacar(bicho, clase) {
    estado.bichos.delete(bicho.id);
    bicho.el.classList.add(clase);
    bicho.el.disabled = true;
    setTimeout(() => bicho.el.remove(), 500);
  }

  function flotante(texto, el) {
    const caja = el.getBoundingClientRect();
    const punto = document.createElement("span");
    punto.className = "puntito";
    punto.textContent = texto;
    punto.style.left = `${caja.left + caja.width / 2 - 40}px`;
    punto.style.top = `${caja.top}px`;
    document.body.append(punto);
    setTimeout(() => punto.remove(), 900);
  }

  /** Tocar una tarjeta: pasa a la columna que sigue (o se cobra). */
  function avanzar(bicho) {
    if (!estado || !estado.corriendo) {
      return;
    }
    const siguiente = { sala: "consultorio", consultorio: "cobrar", cobrar: "cobrado" }[bicho.columna];
    mover(bicho, siguiente);
  }

  function mover(bicho, destino) {
    if (!estado.corriendo || !estado.bichos.has(bicho.id) || destino === bicho.columna) {
      return;
    }
    const orden = ["sala", "consultorio", "cobrar", "cobrado"];
    if (orden.indexOf(destino) < orden.indexOf(bicho.columna)) {
      avisar("Para atrás no: los pacientes no vuelven a la sala 🙃");
      sonar("error");
      return;
    }
    if (bicho.columna === "sala" && destino !== "consultorio") {
      avisar(`Primero ${bicho.nombre} tiene que pasar por el consultorio 🩺`);
      sonar("error");
      return;
    }
    if (destino === "consultorio") {
      if (enColumna("consultorio").length >= LUGARES_CONSULTORIO) {
        avisar("El consultorio está lleno: esperá que terminen con alguien.");
        sonar("error");
        return;
      }
      bicho.columna = "consultorio";
      bicho.progreso = 0;
      listas.consultorio.append(bicho.el);
      bicho.el.classList.remove("bicho--apurado");
      sonar("ok");
    } else if (destino === "cobrar") {
      if (!bicho.terminado) {
        avisar(`Todavía están atendiendo a ${bicho.nombre}, paciencia.`);
        sonar("error");
        return;
      }
      if (enColumna("cobrar").length >= MAXIMO_COBRAR) {
        avisar("Hay mucha gente esperando para pagar: ¡cobrales!");
        sonar("error");
        return;
      }
      bicho.columna = "cobrar";
      listas.cobrar.append(bicho.el);
      sonar("ok");
    } else if (destino === "cobrado") {
      estado.atendidas += 1;
      estado.plata += bicho.servicio.precio;
      flotante(`+${guaranies(bicho.servicio.precio)}`, bicho.el);
      sacar(bicho, "bicho--fuera");
      sonar("plata");
      actualizarMarcador();
      return;
    }
    pintar(bicho);
  }

  // Arrastrar con el mouse o con el dedo

  function escucharArrastre(bicho) {
    const el = bicho.el;
    let inicio = null;
    let arrastrando = false;
    let destinoActual = null;

    const columnaBajo = (x, y) => {
      const debajo = document.elementFromPoint(x, y);
      return debajo && debajo.closest(".juego__columna");
    };

    el.addEventListener("pointerdown", (evento) => {
      if (!estado || !estado.corriendo || evento.button !== 0) {
        return;
      }
      inicio = { x: evento.clientX, y: evento.clientY, caja: el.getBoundingClientRect() };
      bicho.sinClick = false;
      el.setPointerCapture(evento.pointerId);
    });

    el.addEventListener("pointermove", (evento) => {
      if (!inicio) {
        return;
      }
      const dx = evento.clientX - inicio.x;
      const dy = evento.clientY - inicio.y;
      if (!arrastrando && Math.hypot(dx, dy) < MOVER_PARA_ARRASTRAR) {
        return;
      }
      if (!arrastrando) {
        arrastrando = true;
        el.style.width = `${inicio.caja.width}px`;
        el.classList.add("bicho--arrastrando");
      }
      el.style.left = `${inicio.caja.left + dx}px`;
      el.style.top = `${inicio.caja.top + dy}px`;
      const columna = columnaBajo(evento.clientX, evento.clientY);
      if (columna !== destinoActual) {
        destinoActual?.classList.remove("destino");
        columna?.classList.add("destino");
        destinoActual = columna;
      }
    });

    const soltar = (evento) => {
      if (!inicio) {
        return;
      }
      const columna = arrastrando ? columnaBajo(evento.clientX, evento.clientY) : null;
      if (arrastrando) {
        // El click que viene después de soltar no tiene que avanzar la tarjeta otra vez.
        bicho.sinClick = true;
        el.classList.remove("bicho--arrastrando");
        el.style.left = el.style.top = el.style.width = "";
        destinoActual?.classList.remove("destino");
        if (columna) {
          mover(bicho, columna.dataset.columna);
        }
      }
      inicio = null;
      arrastrando = false;
      destinoActual = null;
    };
    el.addEventListener("pointerup", soltar);
    el.addEventListener("pointercancel", soltar);
  }

  // El día

  function actualizarMarcador() {
    ver.tiempo.textContent = Math.max(0, Math.ceil(estado.tiempo));
    ver.puntos.textContent = estado.atendidas;
    ver.plata.textContent = guaranies(estado.plata);
    ver.vidas.textContent = "❤️".repeat(estado.vidas) + "🤍".repeat(VIDAS - estado.vidas);
    ver.vidas.setAttribute("aria-label", `${estado.vidas} vidas`);
  }

  function empezar() {
    Object.values(listas).forEach((lista) => lista.replaceChildren());
    estado = {
      corriendo: true,
      tiempo: DURACION,
      vidas: VIDAS,
      atendidas: 0,
      plata: 0,
      bichos: new Map(),
      proximaLlegada: 1.2,
      anterior: performance.now(),
    };
    ver.cartel.hidden = true;
    ver.compartir.hidden = true;
    crearBicho();
    crearBicho();
    actualizarMarcador();
    sonar("ok");
    requestAnimationFrame(cuadro);
  }

  function cuadro(ahora) {
    if (!estado.corriendo) {
      return;
    }
    const dt = Math.min((ahora - estado.anterior) / 1000, 0.1);
    estado.anterior = ahora;
    estado.tiempo -= dt;

    // Llegan más mascotas a medida que pasa el día.
    estado.proximaLlegada -= dt;
    if (estado.proximaLlegada <= 0) {
      if (enColumna("sala").length < MAXIMO_SALA) {
        crearBicho();
      }
      const transcurrido = DURACION - estado.tiempo;
      estado.proximaLlegada = Math.max(1.1, 2.6 - transcurrido * 0.025) + Math.random() * 0.9;
    }

    for (const bicho of [...estado.bichos.values()]) {
      if (bicho.columna === "sala") {
        bicho.espera -= dt;
        bicho.barra.style.width = `${Math.max(bicho.espera / PACIENCIA, 0) * 100}%`;
        bicho.el.classList.toggle("bicho--apurado", bicho.espera < PACIENCIA * 0.3);
        if (bicho.espera <= 0) {
          estado.vidas -= 1;
          avisar(`${bicho.nombre} se cansó de esperar y se fue 😿`);
          sonar("error");
          sacar(bicho, "bicho--fuera");
          actualizarMarcador();
        }
      } else if (bicho.columna === "consultorio" && !bicho.terminado) {
        bicho.progreso += dt / bicho.servicio.tiempo;
        bicho.barra.style.width = `${Math.min(bicho.progreso, 1) * 100}%`;
        if (bicho.progreso >= 1) {
          bicho.terminado = true;
          pintar(bicho);
          sonar("ok");
        }
      } else if (bicho.columna === "cobrar") {
        bicho.barra.style.width = "100%";
      }
    }

    ver.tiempo.textContent = Math.max(0, Math.ceil(estado.tiempo));
    if (estado.tiempo <= 0 || estado.vidas <= 0) {
      terminar();
      return;
    }
    requestAnimationFrame(cuadro);
  }

  function terminar() {
    estado.corriendo = false;
    actualizarMarcador();
    const { atendidas, plata } = estado;
    const record = leerRecord();
    const nuevoRecord = atendidas > record;
    if (nuevoRecord) {
      guardarRecord(atendidas);
    }
    const sinVidas = estado.vidas <= 0;
    ver.cartelEmoji.textContent = atendidas >= 14 ? "🏆" : atendidas >= 7 ? "🐶" : "😿";
    ver.cartelTitulo.textContent = sinVidas ? "¡Se te juntó la sala!" : "¡Cerraste el día!";
    ver.cartelTexto.textContent = `Atendiste ${atendidas} mascota${atendidas === 1 ? "" : "s"} y cobraste ${guaranies(plata)}. `
      + "En la veterinaria de verdad, Patitas te ordena la sala solita.";
    ver.record.textContent = nuevoRecord && atendidas ? "🎉 ¡Nuevo récord en esta compu!" : record ? `Tu récord: ${record} mascotas` : "";
    ver.empezar.textContent = "Jugar otra vez";
    ver.compartir.hidden = false;
    ver.compartir.href = `https://wa.me/?text=${encodeURIComponent(
      `Atendí ${atendidas} mascotas en 60 segundos en el juego de Patitas 🐾 ¿Me ganás? ${location.href.split("#")[0]}#juego`)}`;
    ver.cartel.hidden = false;
    sonar("fin");
    if (atendidas >= 7 && window.Patitas) {
      window.Patitas.lluvia(["🐾", "⭐", "💰"]);
    }
  }

  // Si se cambia de pestaña, el día se pausa.
  document.addEventListener("visibilitychange", () => {
    if (!estado || !estado.corriendo) {
      return;
    }
    if (document.hidden) {
      estado.pausado = true;
    } else if (estado.pausado) {
      estado.pausado = false;
      estado.anterior = performance.now();
    }
  });

  ver.empezar.addEventListener("click", empezar);
  ver.sonido.addEventListener("click", () => {
    const activo = !(window.Patitas && window.Patitas.conSonido);
    window.Patitas && window.Patitas.cambiarSonido(activo);
    ver.sonido.textContent = activo ? "🔊" : "🔇";
    ver.sonido.setAttribute("aria-pressed", activo ? "true" : "false");
  });
  if (window.Patitas && !window.Patitas.conSonido) {
    ver.sonido.textContent = "🔇";
    ver.sonido.setAttribute("aria-pressed", "false");
  }
  const record = leerRecord();
  if (record) {
    ver.record.textContent = `Tu récord: ${record} mascotas`;
  }
})();
