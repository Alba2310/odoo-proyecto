import { Component, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Patitas › Ayuda › Manual de usuario: muestra el manual (static/manual/index.html) dentro de Odoo.
 */
export class ManualPatitas extends Component {
    static template = "veterinaria.ManualPatitas";
    static props = ["*"];

    setup() {
        // Odoo guarda los archivos estáticos una semana en la caché del navegador:
        // el parámetro hace que siempre se vea la última versión del manual.
        this.url = `/veterinaria/static/manual/index.html?v=${Date.now()}`;
        this.marco = useRef("marco");
    }

    imprimir() {
        this.marco.el.contentWindow.print();
    }
}

registry.category("actions").add("veterinaria.manual", ManualPatitas);
