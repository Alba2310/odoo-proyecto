import { Component, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Menú Studio Bella › Ayuda › Manual de usuario.
 * Muestra el manual (static/manual/index.html) dentro de Odoo, sin salir del sistema.
 */
export class ManualStudioBella extends Component {
    static template = "studio_bella.ManualStudioBella";
    static props = ["*"];

    setup() {
        // Odoo guarda los archivos estáticos una semana en la caché del navegador:
        // el parámetro hace que siempre se vea la última versión del manual.
        this.url = `/studio_bella/static/manual/index.html?v=${Date.now()}`;
        this.marco = useRef("marco");
    }

    imprimir() {
        this.marco.el.contentWindow.print();
    }
}

registry.category("actions").add("studio_bella.manual", ManualStudioBella);
