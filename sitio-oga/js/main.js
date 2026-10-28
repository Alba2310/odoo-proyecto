/* ==========================================================================
   Óga · sitio web de venta
   Menú, tablero de prueba, calculadora, precios y formulario de contacto.
   ========================================================================== */

/* Datos de contacto y precios: cambialos acá y se actualizan en todo el sitio. */
const CONFIG = {
  whatsapp: "595982600740",              // número para wa.me, sin "+" ni espacios
  email: "albamariafarinamoran@gmail.com",
  // Precios de referencia por mes, según la cantidad de unidades (hasta: unidades).
  planes: [
    { nombre: "Casero", hasta: 3, precio: 99000 },
    { nombre: "Propietario", hasta: 10, precio: 199000 },
    { nombre: "Administrador", hasta: 40, precio: 449000 },
    { nombre: "A medida", hasta: Infinity, precio: null },
  ],
};

const guaranies = (monto) => "Gs. " + Math.round(monto).toLocaleString("es-PY").replace(/,/g, ".");
const enlaceWhatsapp = (texto) => `https://wa.me/${CONFIG.whatsapp}?text=${encodeURIComponent(texto)}`;

document.addEventListener("DOMContentLoaded", () => {
  menu();
  tablero();
  calculadora();
  precios();
  contacto();
  document.getElementById("anio").textContent = new Date().getFullYear();
});

/* Menú en el celular y borde de la cabecera al bajar */
function menu() {
  const boton = document.getElementById("menu-boton");
  const lista = document.getElementById("menu");
  boton.addEventListener("click", () => {
    const abierto = lista.classList.toggle("abierto");
    boton.setAttribute("aria-expanded", String(abierto));
  });
  lista.querySelectorAll("a").forEach((enlace) => enlace.addEventListener("click", () => {
    lista.classList.remove("abierto");
    boton.setAttribute("aria-expanded", "false");
  }));
  const cabeza = document.getElementById("cabeza");
  const marcar = () => cabeza.classList.toggle("con-borde", window.scrollY > 8);
  window.addEventListener("scroll", marcar, { passive: true });
  marcar();
}

/* Tablero de prueba: las mismas unidades que el sistema de ejemplo */
const UNIDADES = [
  { propiedad: "Casa Caacupé", nombre: "Casa", inquilino: "María González", monto: 2000000, estado: "al_dia", vence: "10 de noviembre" },
  { propiedad: "Casa Itauguá", nombre: "Casa", inquilino: "Carlos Benítez", monto: 2300000, estado: "debe", vence: "1 de octubre", atraso: 27 },
  { propiedad: "Edificio Ypacaraí", nombre: "Depto 1", inquilino: "Lucía Ramírez", monto: 1300000, estado: "vence", vence: "30 de octubre" },
  { propiedad: "Edificio Ypacaraí", nombre: "Depto 2", inquilino: "Jorge Villalba", monto: 1300000, estado: "debe", vence: "15 de octubre", atraso: 13, falta: 500000 },
  { propiedad: "Edificio Ypacaraí", nombre: "Depto 3", estado: "libre", monto: 1800000 },
  { propiedad: "Edificio Ypacaraí", nombre: "Depto 4", inquilino: "Ana Duarte", monto: 1300000, estado: "al_dia", vence: "5 de noviembre" },
  { propiedad: "Edificio Ypacaraí", nombre: "Depto 5", inquilino: "Ramón Acosta", monto: 1300000, estado: "al_dia", vence: "20 de noviembre" },
];
const ETIQUETAS = { al_dia: "Al día", vence: "Vence en 2 días", debe: "Debe", libre: "Libre" };
const COBRADO_INICIAL = 8000000;

function tablero() {
  const contenedor = document.getElementById("demo-unidades");
  const detalle = document.getElementById("demo-detalle");
  let unidades = [];
  let cobrado = 0;
  let elegida = null;

  const deuda = (unidad) => (unidad.estado === "debe" ? unidad.falta || unidad.monto : 0);
  const nombre = (unidad) => (unidad.nombre === "Casa" ? unidad.propiedad : `${unidad.propiedad} · ${unidad.nombre}`);

  function empezar() {
    unidades = UNIDADES.map((unidad) => ({ ...unidad }));
    cobrado = COBRADO_INICIAL;
    elegida = null;
    dibujar();
  }

  function resumen() {
    const alquiladas = unidades.filter((u) => u.estado !== "libre").length;
    document.getElementById("demo-cobrado").textContent = guaranies(cobrado);
    document.getElementById("demo-deuda").textContent = guaranies(unidades.reduce((suma, u) => suma + deuda(u), 0));
    document.getElementById("demo-ocupacion").textContent = `${Math.round((100 * alquiladas) / unidades.length)} %`;
  }

  function dibujar() {
    contenedor.replaceChildren();
    let propiedad = null;
    unidades.forEach((unidad, indice) => {
      if (unidad.propiedad !== propiedad) {
        propiedad = unidad.propiedad;
        const titulo = document.createElement("p");
        titulo.className = "grupo-titulo";
        titulo.textContent = propiedad;
        contenedor.append(titulo);
      }
      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = `unidad unidad--${unidad.estado}`;
      boton.setAttribute("role", "listitem");
      boton.setAttribute("aria-pressed", String(indice === elegida));
      const textoEstado = unidad.estado === "debe" ? `Debe ${guaranies(deuda(unidad))}` : ETIQUETAS[unidad.estado];
      boton.innerHTML = `<strong></strong><small></small><span class="estado"></span>`;
      boton.querySelector("strong").textContent = unidad.nombre;
      boton.querySelector("small").textContent = unidad.inquilino || "Sin inquilino";
      boton.querySelector(".estado").textContent = textoEstado;
      boton.addEventListener("click", () => {
        elegida = indice;
        dibujar();
      });
      contenedor.append(boton);
    });
    resumen();
    mostrarDetalle();
  }

  function mostrarDetalle() {
    detalle.replaceChildren();
    if (elegida === null) {
      const vacio = document.createElement("p");
      vacio.className = "tablero__vacio";
      vacio.textContent = "Elegí una unidad del tablero.";
      detalle.append(vacio);
      return;
    }
    const unidad = unidades[elegida];
    const caja = document.createElement("div");
    caja.className = "detalle";
    const titulo = document.createElement("h3");
    titulo.textContent = nombre(unidad);
    const sub = document.createElement("p");
    sub.className = "detalle__sub";
    caja.append(titulo, sub);
    const acciones = document.createElement("div");
    acciones.className = "detalle__acciones";

    if (unidad.estado === "libre") {
      sub.textContent = `Libre · se publica sola en tu página “Se alquila” a ${guaranies(unidad.monto)} por mes.`;
      acciones.append(botonDemo("Ver interesados", "boton--borde", () => avisar("En Óga ves acá a los que dejaron sus datos en tu página y les escribís con un toque.")));
    } else {
      const primer = unidad.inquilino.split(" ")[0];
      const estado = unidad.estado === "debe" ? `debe ${guaranies(deuda(unidad))} (${unidad.atraso} días de atraso)`
        : unidad.estado === "vence" ? `vence el ${unidad.vence}` : `al día · próximo vencimiento el ${unidad.vence}`;
      sub.textContent = `${unidad.inquilino} · ${guaranies(unidad.monto)} por mes · ${estado}`;
      if (unidad.estado !== "al_dia") {
        const mensaje = document.createElement("p");
        mensaje.className = "detalle__mensaje";
        mensaje.textContent = unidad.estado === "debe"
          ? `¡Hola ${primer}! El alquiler de octubre (${nombre(unidad)}) venció el ${unidad.vence} y figura pendiente: ${guaranies(deuda(unidad))}. Si ya pagaste, avisanos por acá así lo registramos. ¡Gracias!`
          : `¡Hola ${primer}! Te recordamos que el ${unidad.vence} vence el alquiler de octubre (${nombre(unidad)}): ${guaranies(unidad.monto)}. ¡Gracias!`;
        caja.append(mensaje);
        acciones.append(
          botonDemo("Avisar por WhatsApp", "boton--wa", () => avisar("En Óga este botón abre WhatsApp con el mensaje escrito: solo tocás Enviar.")),
          botonDemo("Registrar pago", "", () => {
            cobrado += unidad.estado === "debe" ? deuda(unidad) : unidad.monto;
            unidad.estado = "al_dia";
            unidad.vence = "el mes que viene";
            delete unidad.falta;
            avisar(`¡Listo! Pago registrado y recibo generado para ${unidad.inquilino}. La unidad pasó a verde.`);
            dibujar();
          }),
        );
      } else {
        acciones.append(botonDemo("Imprimir último recibo", "boton--borde", () => avisar("En Óga se descarga el recibo en PDF, con el monto en letras.")));
      }
    }
    caja.append(acciones);
    detalle.append(caja);
  }

  document.getElementById("demo-reiniciar").addEventListener("click", empezar);
  empezar();
}

function botonDemo(texto, clase, alTocar) {
  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = `boton boton--chico ${clase}`.trim();
  boton.textContent = texto;
  boton.addEventListener("click", alTocar);
  return boton;
}

let temporizadorAviso;
function avisar(texto) {
  const aviso = document.getElementById("aviso-demo");
  aviso.textContent = texto;
  aviso.hidden = false;
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => { aviso.hidden = true; }, 3800);
}

/* Calculadora: horas y plata que se cobra antes */
const MINUTOS_POR_UNIDAD = 40;     // anotar, buscar y escribir a cada inquilino, por mes
const ATRASOS_QUE_SE_EVITAN = 0.5; // con avisos a tiempo, la mitad de los atrasos se corrige

function calculadora() {
  const unidades = document.getElementById("calc-unidades");
  const alquiler = document.getElementById("calc-alquiler");
  const atraso = document.getElementById("calc-atraso");
  const calcular = () => {
    const cantidad = Number(unidades.value);
    const horas = Math.max(1, Math.round((cantidad * MINUTOS_POR_UNIDAD) / 60));
    const plata = cantidad * Number(alquiler.value) * (Number(atraso.value) / 100) * ATRASOS_QUE_SE_EVITAN;
    document.getElementById("calc-unidades-valor").textContent = cantidad;
    document.getElementById("calc-alquiler-valor").textContent = guaranies(alquiler.value);
    document.getElementById("calc-atraso-valor").textContent = `${atraso.value} %`;
    document.getElementById("calc-horas").textContent = `${horas} ${horas === 1 ? "hora" : "horas"}`;
    document.getElementById("calc-plata").textContent = guaranies(plata);
  };
  [unidades, alquiler, atraso].forEach((control) => control.addEventListener("input", calcular));
  calcular();
}

/* Precios: el plan que corresponde a la cantidad de unidades */
function precios() {
  const control = document.getElementById("precio-unidades");
  const contenedor = document.getElementById("planes");
  let desde = 1;
  const tarjetas = CONFIG.planes.map((plan) => {
    const tarjeta = document.createElement("article");
    tarjeta.className = "plan";
    const rango = plan.hasta === Infinity ? `Más de ${desde - 1} unidades` : `${desde} a ${plan.hasta} unidades`;
    tarjeta.innerHTML = `<h3></h3><p class="plan__unidades"></p><p class="plan__precio"></p>`;
    tarjeta.querySelector("h3").textContent = plan.nombre;
    tarjeta.querySelector(".plan__unidades").textContent = rango;
    const precio = tarjeta.querySelector(".plan__precio");
    if (plan.precio) {
      precio.textContent = guaranies(plan.precio);
      const mes = document.createElement("small");
      mes.textContent = " por mes";
      precio.append(mes);
    } else {
      precio.textContent = "Consultanos";
    }
    desde = plan.hasta + 1;
    contenedor.append(tarjeta);
    return tarjeta;
  });
  const elegir = () => {
    const cantidad = Number(control.value);
    document.getElementById("precio-unidades-valor").textContent = control.value === control.max ? `${cantidad}+` : cantidad;
    const indice = CONFIG.planes.findIndex((plan) => cantidad <= plan.hasta);
    tarjetas.forEach((tarjeta, i) => tarjeta.classList.toggle("elegido", i === indice));
  };
  control.addEventListener("input", elegir);
  elegir();
}

/* Contacto: arma el mensaje y abre WhatsApp */
function contacto() {
  document.getElementById("contacto-whatsapp").href = enlaceWhatsapp("Hola, quiero conocer Óga para mis alquileres.");
  document.getElementById("contacto-email").href = `mailto:${CONFIG.email}?subject=${encodeURIComponent("Quiero conocer Óga")}`;

  const formulario = document.getElementById("formulario");
  const error = document.getElementById("formulario-error");
  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const datos = new FormData(formulario);
    const faltan = ["nombre", "telefono"].filter((campo) => !String(datos.get(campo) || "").trim());
    formulario.querySelectorAll("input").forEach((campo) => campo.setAttribute("aria-invalid", String(faltan.includes(campo.name))));
    if (faltan.length) {
      error.textContent = "Completá tu nombre y tu teléfono, así te podemos escribir.";
      error.hidden = false;
      formulario.elements[faltan[0]].focus();
      return;
    }
    error.hidden = true;
    const lineas = [
      "Hola, quiero probar Óga.",
      `Nombre: ${datos.get("nombre").trim()}`,
      `Teléfono: ${datos.get("telefono").trim()}`,
      `Unidades: ${datos.get("unidades")}`,
      datos.get("ciudad").trim() ? `Ciudad: ${datos.get("ciudad").trim()}` : "",
      datos.get("mensaje").trim() ? `Mensaje: ${datos.get("mensaje").trim()}` : "",
    ].filter(Boolean);
    window.open(enlaceWhatsapp(lineas.join("\n")), "_blank", "noopener");
  });
}
