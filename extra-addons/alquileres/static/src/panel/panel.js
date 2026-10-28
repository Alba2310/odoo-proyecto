import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Menú Óga › Panel: los números del mes, el gráfico de cobrado y gastos, la ganancia de cada propiedad
 * y lo que hay que atender hoy. Los datos salen de alquiler.panel (models/panel.py).
 */
export class PanelOga extends Component {
    static template = "alquileres.PanelOga";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.estado = useState({ datos: null });
        onWillStart(() => this.cargar());
    }

    async cargar() {
        this.estado.datos = await this.orm.call("alquiler.panel", "datos", []);
    }

    abrirIndicador(clave) {
        const acciones = {
            cobrado: ["alquileres.action_alquiler_pago", {}],
            deuda: ["alquileres.action_alquiler_cuota", { search_default_atrasadas: 1, search_default_sin_pagar: 0 }],
            ocupacion: ["alquileres.action_alquiler_control", {}],
            ganancia: ["alquileres.action_alquiler_resultado", {}],
        };
        const [accion, contexto] = acciones[clave];
        this.action.doAction(accion, { additionalContext: contexto });
    }

    abrirPendiente(pendiente) {
        if (pendiente.accion) {
            this.action.doAction(pendiente.accion);
        } else {
            this.abrirRegistro(pendiente.modelo, pendiente.id);
        }
    }

    abrirRegistro(modelo, id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: modelo,
            res_id: id,
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("alquileres.panel", PanelOga);
