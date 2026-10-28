/* Página "Se alquila": filtrar por ciudad y, con "Dejar mis datos", elegir esa unidad en el formulario. */
document.addEventListener("DOMContentLoaded", () => {
    const filtros = document.querySelectorAll(".filtro");
    const tarjetas = document.querySelectorAll(".tarjeta");
    filtros.forEach((filtro) => {
        filtro.addEventListener("click", () => {
            filtros.forEach((otro) => otro.classList.toggle("activo", otro === filtro));
            const ciudad = filtro.dataset.ciudad;
            tarjetas.forEach((tarjeta) => {
                tarjeta.hidden = Boolean(ciudad) && tarjeta.dataset.ciudad !== ciudad;
            });
        });
    });

    const unidad = document.getElementById("unidad");
    document.querySelectorAll("[data-unidad]").forEach((enlace) => {
        enlace.addEventListener("click", () => {
            if (unidad) {
                unidad.value = enlace.dataset.unidad;
            }
        });
    });
});
