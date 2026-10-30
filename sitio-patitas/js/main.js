/* ==========================================================================
   Patitas · sitio web de venta
   La mascota, el día que corre al bajar, el álbum de figuritas, los precios, el formulario y los chistes.
   El juego de la sala de espera está en juego.js.
   ========================================================================== */

/* Datos de contacto y precios: cambialos acá y se actualizan en todo el sitio. */
const CONFIG = {
  whatsapp: "595982600740",              // número para wa.me, sin "+" ni espacios
  email: "albamariafarinamoran@gmail.com",
  // La página de turnos de la veterinaria de ejemplo, para probarla como si fueras un dueño.
  demoTurnos: "http://patitas.localhost:8073/reservar",
  // Precios de referencia por mes.
  planes: [
    {
      icono: "🐶", nombre: "Cachorro", para: "Para la veterinaria que recién arranca", precio: 180000,
      incluye: ["1 o 2 personas atendiendo", "Turnos, historia clínica y carnet", "Avisos por WhatsApp y correo",
        "Cobro con factura y stock"],
    },
    {
      icono: "🐕", nombre: "Mediano", para: "Con peluquería, internación y hotel", precio: 320000, popular: true,
      incluye: ["Hasta 6 personas", "Todo lo del Cachorro", "Baño y peluquería con su agenda",
        "Internación y hotel", "Turnos por internet"],
    },
    {
      icono: "🐕‍🦺", nombre: "Gran danés", para: "Para varias sucursales", precio: null,
      incluye: ["Sin límite de personas", "Todo lo del Mediano", "Una caja y un stock por sucursal",
        "Lo armamos a tu medida"],
    },
  ],
};

/* Las figuritas del álbum: cada función del sistema. */
const FIGURITAS = [
  { emoji: "📋", titulo: "Hoy en Patitas", color: "#dfe8ff",
    texto: "La sala de espera en columnas: quién tiene turno, quién espera, a quién atienden y a quién cobrar. Se arrastra con el dedo." },
  { emoji: "🐶", titulo: "Ficha de la mascota", color: "#fff3c9",
    texto: "Dueño, raza, edad, alergias, alertas (\"muerde\") y una línea de tiempo con todo lo que le hicieron." },
  { emoji: "📈", titulo: "Gráfico del peso", color: "#d9f8ea",
    texto: "Cada vez que la pesan queda anotado. Ideal para seguir a los cachorros y a los que están a dieta." },
  { emoji: "🩺", titulo: "Historia clínica", color: "#ffe1de",
    texto: "Motivo, signos, examen, diagnóstico y tratamiento. Las indicaciones se imprimen con tu firma y matrícula." },
  { emoji: "💉", titulo: "Carnet de vacunas", color: "#dfe8ff",
    texto: "Cada vacuna con su lote y la fecha de la próxima dosis, calculada sola. Se imprime el carnet." },
  { emoji: "💬", titulo: "Avisos por WhatsApp", color: "#d9f8ea",
    texto: "\"A Toby le toca la antirrábica\": un solo mensaje con las vacunas de todas las mascotas del dueño." },
  { emoji: "🛁", titulo: "Baño y peluquería", color: "#fff3c9",
    texto: "Su propia agenda y el aviso \"ya está listo y perfumado\" con lo que encontraron (pulgas, nudos)." },
  { emoji: "🏥", titulo: "Internación", color: "#ffe1de",
    texto: "Jaula, controles del día, medicación y el parte al dueño. En rojo si alguien pasó horas sin control." },
  { emoji: "🏨", titulo: "Hotel y guardería", color: "#dfe8ff",
    texto: "Reservas por fecha, lo que dejó el dueño, constancia para firmar y el cobro por día." },
  { emoji: "💳", titulo: "Cobro mixto", color: "#d9f8ea",
    texto: "Una parte en efectivo y otra con tarjeta o QR. Calcula el vuelto y emite la factura." },
  { emoji: "📦", titulo: "Stock y compras", color: "#fff3c9",
    texto: "Alimentos, remedios y vacunas con stock mínimo. Avisa qué reponer y se pide al proveedor desde ahí." },
  { emoji: "📱", titulo: "Turnos por internet", color: "#ffe1de",
    texto: "Una página tipo chat donde el dueño pide el turno para su mascota, a cualquier hora." },
];

const guaranies = (monto) => "Gs. " + Math.round(monto).toLocaleString("es-PY").replace(/,/g, ".");
const enlaceWhatsapp = (texto) => `https://wa.me/${CONFIG.whatsapp}?text=${encodeURIComponent(texto)}`;
const sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* Lo que comparten la página y el juego: sonidos chiquitos y la lluvia de huellas. */
window.Patitas = (() => {
  let audio = null;
  let conSonido = true;
  try {
    conSonido = localStorage.getItem("patitas-sonido") !== "no";
  } catch (error) {
    /* sin almacenamiento: queda con sonido */
  }

  function contexto() {
    if (!audio) {
      const Contexto = window.AudioContext || window.webkitAudioContext;
      audio = Contexto ? new Contexto() : null;
    }
    return audio;
  }

  /** Un sonido sintetizado (no hay archivos): "guau", "miau", "ok", "plata", "error" o "fin". */
  function sonar(tipo) {
    const ctx = conSonido && contexto();
    if (!ctx) {
      return;
    }
    const ahora = ctx.currentTime;
    const nota = (frecuencia, desde, dura, forma = "sine", hasta = frecuencia, volumen = 0.18) => {
      const osc = ctx.createOscillator();
      const gan = ctx.createGain();
      osc.type = forma;
      osc.frequency.setValueAtTime(frecuencia, ahora + desde);
      osc.frequency.exponentialRampToValueAtTime(hasta, ahora + desde + dura);
      gan.gain.setValueAtTime(0.0001, ahora + desde);
      gan.gain.exponentialRampToValueAtTime(volumen, ahora + desde + 0.02);
      gan.gain.exponentialRampToValueAtTime(0.0001, ahora + desde + dura);
      osc.connect(gan).connect(ctx.destination);
      osc.start(ahora + desde);
      osc.stop(ahora + desde + dura + 0.02);
    };
    const sonidos = {
      guau: () => { nota(420, 0, 0.13, "sawtooth", 160, 0.12); nota(380, 0.18, 0.15, "sawtooth", 140, 0.12); },
      miau: () => { nota(500, 0, 0.3, "triangle", 900, 0.12); nota(900, 0.25, 0.35, "triangle", 420, 0.1); },
      ok: () => { nota(660, 0, 0.09); nota(990, 0.08, 0.12); },
      plata: () => { nota(1300, 0, 0.08, "square", 1300, 0.07); nota(1750, 0.07, 0.18, "square", 1750, 0.07); },
      error: () => nota(220, 0, 0.3, "sawtooth", 110, 0.1),
      fin: () => [523, 659, 784, 1046].forEach((f, i) => nota(f, i * 0.12, 0.2, "triangle")),
    };
    (sonidos[tipo] || sonidos.ok)();
  }

  function cambiarSonido(valor) {
    conSonido = valor;
    try {
      localStorage.setItem("patitas-sonido", valor ? "si" : "no");
    } catch (error) {
      /* sin almacenamiento */
    }
  }

  /** Lluvia de huellas (o de lo que se le pase). */
  function lluvia(simbolos = ["🐾"], cantidad = 40) {
    if (sinMovimiento) {
      return;
    }
    const capa = document.createElement("div");
    capa.className = "lluvia";
    for (let i = 0; i < cantidad; i++) {
      const gota = document.createElement("span");
      gota.textContent = simbolos[i % simbolos.length];
      gota.style.left = `${Math.random() * 100}%`;
      gota.style.animationDuration = `${1.8 + Math.random() * 2}s`;
      gota.style.animationDelay = `${Math.random() * 0.8}s`;
      gota.style.fontSize = `${1.2 + Math.random() * 1.6}rem`;
      capa.append(gota);
    }
    document.body.append(capa);
    setTimeout(() => capa.remove(), 4800);
  }

  return { sonar, lluvia, cambiarSonido, get conSonido() { return conSonido; } };
})();

/* Rastro de huellas de arriba: cuánto de la página se bajó */
function iniciarRastro() {
  const lleno = document.getElementById("rastro");
  const actualizar = () => {
    const total = document.documentElement.scrollHeight - window.innerHeight;
    lleno.style.width = `${total > 0 ? (window.scrollY / total) * 100 : 0}%`;
  };
  window.addEventListener("scroll", actualizar, { passive: true });
  actualizar();
}

/* La mascota: mira el puntero, ladra (o maúlla) al tocarla y se vuelve gato con el botón */
function iniciarMascota() {
  const boton = document.getElementById("mascota");
  const svg = document.getElementById("mascota-svg");
  const globo = document.getElementById("globo");
  const quien = document.getElementById("quien-entiende");
  const ojos = [...svg.querySelectorAll("[data-ojo]")];
  let especie = "perro";
  let toques = 0;
  let ocultarGlobo = null;

  const mirar = (x, y) => {
    for (const ojo of ojos) {
      const caja = ojo.getBoundingClientRect();
      const dx = x - (caja.left + caja.width / 2);
      const dy = y - (caja.top + caja.height / 2);
      const distancia = Math.min(Math.hypot(dx, dy) / 40, 1);
      const angulo = Math.atan2(dy, dx);
      const mover = `translate(${Math.cos(angulo) * 8 * distancia}px, ${Math.sin(angulo) * 8 * distancia}px)`;
      ojo.querySelectorAll(".ojo__pupila, .ojo__brillo").forEach((parte) => { parte.style.transform = mover; });
    }
  };
  window.addEventListener("pointermove", (evento) => mirar(evento.clientX, evento.clientY), { passive: true });
  // En el celular no hay puntero: mira para los costados de vez en cuando.
  if (window.matchMedia("(hover: none)").matches && !sinMovimiento) {
    setInterval(() => {
      const caja = svg.getBoundingClientRect();
      mirar(caja.left + Math.random() * caja.width * 2 - caja.width / 2, caja.top + Math.random() * caja.height);
    }, 1800);
  }

  boton.addEventListener("click", () => {
    toques += 1;
    const frases = especie === "perro"
      ? ["¡Guau!", "¡Guau guau!", "¡Turno!", "🦴?", "¡Vacunas al día!"]
      : ["¡Miau!", "Miau…", "¿Y mi turno?", "🐟?", "¡Purr!"];
    globo.textContent = toques >= 7 && toques % 7 === 0 ? "¡Me encanta Patitas! 💛" : frases[(toques - 1) % frases.length];
    globo.classList.add("visible");
    boton.classList.remove("ladrando");
    void boton.offsetWidth; // reinicia la animación
    boton.classList.add("ladrando");
    window.Patitas.sonar(especie === "perro" ? "guau" : "miau");
    clearTimeout(ocultarGlobo);
    ocultarGlobo = setTimeout(() => globo.classList.remove("visible"), 1400);
    if (toques % 7 === 0) {
      window.Patitas.lluvia(especie === "perro" ? ["🐾", "🦴", "🐶"] : ["🐾", "🐟", "🐱"]);
    }
  });

  for (const opcion of document.querySelectorAll(".cambiar__opcion")) {
    opcion.addEventListener("click", () => {
      especie = opcion.dataset.especie;
      svg.classList.toggle("perro", especie === "perro");
      svg.classList.toggle("gato", especie === "gato");
      boton.classList.toggle("gato-activo", especie === "gato");
      quien.textContent = especie === "perro" ? "hasta tu perro" : "hasta tu gato";
      for (const otra of document.querySelectorAll(".cambiar__opcion")) {
        const activa = otra === opcion;
        otra.classList.toggle("cambiar__opcion--activa", activa);
        otra.setAttribute("aria-pressed", activa ? "true" : "false");
      }
      boton.click();
    });
  }
}

/* Un día en Patitas: cada paso que entra en pantalla mueve el reloj y el cielo */
function iniciarDia() {
  const cielo = document.getElementById("cielo");
  const reloj = document.getElementById("reloj");
  const pasos = [...document.querySelectorAll(".paso")];
  const activar = (paso) => {
    pasos.forEach((otro) => otro.classList.toggle("activo", otro === paso));
    cielo.dataset.momento = paso.dataset.momento;
    reloj.textContent = paso.dataset.hora;
  };
  if (!("IntersectionObserver" in window)) {
    pasos.forEach((paso) => paso.classList.add("activo"));
    return;
  }
  const observador = new IntersectionObserver((entradas) => {
    const visibles = entradas.filter((entrada) => entrada.isIntersecting);
    if (visibles.length) {
      activar(visibles.sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0].target);
    }
  }, { rootMargin: "-35% 0px -35% 0px", threshold: [0, 0.25, 0.5, 0.75, 1] });
  pasos.forEach((paso) => observador.observe(paso));
  activar(pasos[0]);
}

/* Álbum de figuritas */
function iniciarAlbum() {
  const contenedor = document.getElementById("album-figuritas");
  const contador = document.getElementById("album-contador");
  const album = document.getElementById("album");
  const abiertas = new Set();
  FIGURITAS.forEach((figurita, indice) => {
    const numero = String(indice + 1).padStart(2, "0");
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "figurita";
    boton.setAttribute("aria-pressed", "false");
    boton.setAttribute("aria-label", `Figurita ${numero}: ${figurita.titulo}`);
    boton.style.setProperty("--color", figurita.color);
    boton.innerHTML = `
      <span class="figurita__cara figurita__frente">
        <span class="figurita__numero">${numero}</span>
        <span class="figurita__emoji" aria-hidden="true">${figurita.emoji}</span>
        <span class="figurita__titulo">${figurita.titulo}</span>
      </span>
      <span class="figurita__cara figurita__dorso">
        <span class="figurita__numero">${numero}</span>
        <b>${figurita.titulo}</b>
        <span>${figurita.texto}</span>
      </span>`;
    boton.addEventListener("click", () => {
      const abierta = boton.classList.toggle("abierta");
      boton.setAttribute("aria-pressed", abierta ? "true" : "false");
      window.Patitas.sonar("ok");
      if (abierta && !abiertas.has(indice)) {
        abiertas.add(indice);
        contador.textContent = abiertas.size === FIGURITAS.length
          ? "¡Álbum completo! 🎉 Ya sabés todo lo que hace Patitas"
          : `Abriste ${abiertas.size} de ${FIGURITAS.length}`;
        if (abiertas.size === FIGURITAS.length) {
          album.classList.add("completo");
          window.Patitas.sonar("fin");
          window.Patitas.lluvia(["🐾", "⭐", "🎉"]);
        }
      }
    });
    contenedor.append(boton);
  });
}

/* Precios: chapitas de collar */
function iniciarPrecios() {
  const contenedor = document.getElementById("chapitas");
  contenedor.innerHTML = CONFIG.planes.map((plan) => `
    <article class="chapita-plan${plan.popular ? " chapita-plan--popular" : ""}">
      ${plan.popular ? '<span class="chapita-plan__cinta">⭐ La más elegida</span>' : ""}
      <p class="chapita-plan__icono" aria-hidden="true">${plan.icono}</p>
      <h3>${plan.nombre}</h3>
      <p class="chapita-plan__para">${plan.para}</p>
      <p class="chapita-plan__precio">${plan.precio ? `${guaranies(plan.precio)}<small> /mes</small>` : "A medida"}</p>
      <ul>${plan.incluye.map((item) => `<li>${item}</li>`).join("")}</ul>
      <a class="boton boton--azul" href="#huella" data-plan="${plan.nombre}">Quiero el ${plan.nombre}</a>
    </article>`).join("");
  contenedor.addEventListener("click", (evento) => {
    const enlace = evento.target.closest("[data-plan]");
    if (enlace) {
      document.getElementById("formulario").dataset.plan = enlace.dataset.plan;
    }
  });
}

/* Contacto: el formulario arma el mensaje y abre WhatsApp (no se guarda nada) */
function iniciarContacto() {
  document.getElementById("contacto-whatsapp").href = enlaceWhatsapp("¡Hola! Quiero conocer Patitas para mi veterinaria 🐾");
  document.getElementById("contacto-email").href =
    `mailto:${CONFIG.email}?subject=${encodeURIComponent("Quiero conocer Patitas")}`;
  const demo = document.getElementById("contacto-demo");
  if (CONFIG.demoTurnos) {
    demo.href = CONFIG.demoTurnos;
  } else {
    demo.hidden = true;
  }

  const formulario = document.getElementById("formulario");
  const error = document.getElementById("formulario-error");
  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const datos = new FormData(formulario);
    const valor = (campo) => String(datos.get(campo) || "").trim();
    if (!valor("nombre") || (valor("telefono").match(/\d/g) || []).length < 8) {
      error.textContent = !valor("nombre") ? "Falta tu nombre 🐶" : "Revisá el celular: con la característica, por ejemplo 0981 123 456.";
      error.hidden = false;
      window.Patitas.sonar("error");
      return;
    }
    error.hidden = true;
    const lineas = [
      "¡Hola! Quiero conocer Patitas 🐾",
      `Soy ${valor("nombre")}${valor("veterinaria") ? `, de ${valor("veterinaria")}` : ""}${valor("ciudad") ? ` (${valor("ciudad")})` : ""}.`,
      `Atendemos ${valor("personas")} personas.`,
      formulario.dataset.plan ? `Me interesa el plan ${formulario.dataset.plan}.` : "",
      `Mi celular: ${valor("telefono")}`,
    ].filter(Boolean);
    formulario.classList.remove("sellado");
    void formulario.offsetWidth;
    formulario.classList.add("sellado");
    window.Patitas.sonar("guau");
    window.open(enlaceWhatsapp(lineas.join("\n")), "_blank", "noopener");
  });
}

/* Escribir "guau" (o "miau") en cualquier parte: lluvia de huellas */
function iniciarSecreto() {
  let escrito = "";
  window.addEventListener("keydown", (evento) => {
    if (evento.target.closest("input, textarea") || evento.key.length !== 1) {
      return;
    }
    escrito = (escrito + evento.key.toLowerCase()).slice(-4);
    if (escrito === "guau" || escrito === "miau") {
      window.Patitas.sonar(escrito === "guau" ? "guau" : "miau");
      window.Patitas.lluvia(escrito === "guau" ? ["🐾", "🐶", "🦴"] : ["🐾", "🐱", "🐟"], 60);
      escrito = "";
    }
  });
}

iniciarRastro();
iniciarMascota();
iniciarDia();
iniciarAlbum();
iniciarPrecios();
iniciarContacto();
iniciarSecreto();
