import { Component, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Menú Óga › Ayuda › Manual de usuario: muestra el manual (static/manual/index.html) dentro de Odoo.
 */
export class ManualOga extends Component {
    static template = "alquileres.ManualOga";
    static props = ["*"];

    setup() {
        // Odoo guarda los archivos estáticos una semana en la caché del navegador:
        // el parámetro hace que siempre se vea la última versión del manual.
        this.url = `/alquileres/static/manual/index.html?v=${Date.now()}`;
        this.marco = useRef("marco");
    }

    imprimir() {
        this.marco.el.contentWindow.print();
    }
}

registry.category("actions").add("alquileres.manual", ManualOga);
