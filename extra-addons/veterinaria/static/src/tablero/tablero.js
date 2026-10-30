import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSortable } from "@web/core/utils/sortable_owl";

// Cada cuánto se actualiza solo (la recepción lo deja abierto todo el día).
const SEGUNDOS_ACTUALIZAR = 60;

/**
 * Patitas › Hoy: la sala de espera en columnas (turnos de hoy, en espera, en atención, para retirar y cobrar),
 * los internados y hospedados, y los avisos del día. Los datos salen de vet.tablero (models/tablero.py) y los
 * botones llaman a los métodos de vet.atencion y vet.internacion. Las tarjetas se arrastran de una columna a otra
 * (con el mouse o con el dedo): vet.atencion.action_mover decide qué hacer.
 */
export class TableroPatitas extends Component {
    static template = "veterinaria.TableroPatitas";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.estado = useState({ datos: null, area: false, ocupado: false });
        this.raiz = useRef("raiz");
        let columnaOrigen = null;
        useSortable({
            ref: this.raiz,
            elements: ".o_vet_arrastrable",
            groups: ".o_vet_columna",
            connectGroups: true,
            // Los botones de la tarjeta se siguen tocando sin arrastrarla.
            ignore: "button, a",
            cursor: "grabbing",
            placeholderClasses: ["o_vet_hueco"],
            onDragStart: ({ element, group }) => {
                columnaOrigen = group;
                element.classList.add("o_vet_arrastrando");
            },
            onGroupEnter: ({ group }) => group.classList.add("o_vet_columna_destino"),
            onGroupLeave: ({ group }) => group.classList.remove("o_vet_columna_destino"),
            onDragEnd: ({ element }) => {
                element.classList.remove("o_vet_arrastrando");
                for (const columna of this.raiz.el.querySelectorAll(".o_vet_columna_destino")) {
                    columna.classList.remove("o_vet_columna_destino");
                }
            },
            onDrop: ({ element, group, parent }) => {
                const destino = parent || group;
                if (destino && destino !== columnaOrigen) {
                    this.mover(Number(element.dataset.id), destino.dataset.clave);
                }
            },
        });
        onWillStart(() => this.cargar());
        onMounted(() => {
            this.reloj = setInterval(() => this.cargar(), SEGUNDOS_ACTUALIZAR * 1000);
        });
        onWillUnmount(() => clearInterval(this.reloj));
    }

    async cargar() {
        this.estado.datos = await this.orm.call("vet.tablero", "datos", [], { area: this.estado.area });
    }

    elegirArea(area) {
        this.estado.area = this.estado.area === area ? false : area;
        this.cargar();
    }

    contar(clave) {
        return this.estado.datos.columnas.find((columna) => columna.clave === clave).tarjetas.length;
    }

    /** Un botón de una tarjeta: llama al método como un botón de formulario, así si devuelve una acción
     * (WhatsApp, la ventana de cobro) Odoo la abre. Al cerrar la ventana se vuelve a cargar el tablero. */
    async ejecutar(modelo, id, metodo) {
        if (this.estado.ocupado) {
            return;
        }
        this.estado.ocupado = true;
        try {
            await this.action.doActionButton({
                type: "object",
                name: metodo,
                resModel: modelo,
                resId: id,
                onClose: () => this.cargar(),
            });
        } finally {
            this.estado.ocupado = false;
        }
        await this.cargar();
    }

    /** La tarjeta se soltó en otra columna. Si no se puede (por ejemplo, nadie la atiende), avisa y vuelve. */
    async mover(id, columna) {
        if (this.estado.ocupado) {
            return;
        }
        this.estado.ocupado = true;
        try {
            await this.orm.call("vet.atencion", "action_mover", [[id], columna]);
        } finally {
            this.estado.ocupado = false;
            await this.cargar();
        }
    }

    abrir(modelo, id) {
        this.action.doAction(
            { type: "ir.actions.act_window", res_model: modelo, res_id: id, views: [[false, "form"]] },
            { onClose: () => this.cargar() }
        );
    }

    llegoSinTurno() {
        this.action.doAction("veterinaria.action_vet_atencion_sin_turno", {
            additionalContext: { default_area: this.estado.area || "consultorio" },
            onClose: () => this.cargar(),
        });
    }

    abrirAccion(xmlId) {
        this.action.doAction(xmlId);
    }
}

registry.category("actions").add("veterinaria.tablero", TableroPatitas);
