import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const ICONOS = {
    consulta: "fa-stethoscope",
    estetica: "fa-bath",
    vacuna: "fa-eyedropper",
    desparasitacion: "fa-shield",
    internacion: "fa-bed",
    hotel: "fa-home",
    nacimiento: "fa-birthday-cake",
    fallecimiento: "fa-heart",
};
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

// Medidas del gráfico del peso (en unidades del viewBox del SVG).
const ANCHO = 600;
const ALTO = 140;
const MARGEN = 28;

/**
 * Ficha de la mascota › Línea de tiempo: todo lo que se le hizo, de lo más nuevo a lo más viejo, y el gráfico de
 * su peso. Los datos salen de vet.mascota.vet_linea_tiempo (models/mascota.py).
 */
export class LineaTiempo extends Component {
    static template = "veterinaria.LineaTiempo";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.estado = useState({ eventos: [], pesos: [], cargado: false, filtro: false });
        onWillStart(() => this.cargar(this.props.record.resId));
        onWillUpdateProps((siguientes) => {
            if (siguientes.record.resId !== this.props.record.resId) {
                return this.cargar(siguientes.record.resId);
            }
        });
    }

    async cargar(id) {
        if (!id) {
            Object.assign(this.estado, { eventos: [], pesos: [], cargado: true });
            return;
        }
        const datos = await this.orm.call("vet.mascota", "vet_linea_tiempo", [id]);
        Object.assign(this.estado, { ...datos, cargado: true });
    }

    get eventos() {
        const filtro = this.estado.filtro;
        return this.estado.eventos
            .filter((evento) => !filtro || evento.tipo === filtro || (filtro === "vacuna" && evento.tipo === "desparasitacion"))
            .map((evento, indice) => ({ ...evento, clave: `${evento.modelo}-${evento.id}-${indice}` }));
    }

    icono(tipo) {
        return ICONOS[tipo] || "fa-circle";
    }

    fecha(texto) {
        const [anio, mes, dia] = texto.split("-");
        return `${Number(dia)} ${MESES[Number(mes) - 1]} ${anio}`;
    }

    elegir(filtro) {
        this.estado.filtro = this.estado.filtro === filtro ? false : filtro;
    }

    abrir(evento) {
        if (!evento.modelo) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: evento.modelo,
            res_id: evento.id,
            views: [[false, "form"]],
        });
    }

    /** Puntos del gráfico del peso, repartidos por fecha. */
    get grafico() {
        const pesos = this.estado.pesos;
        if (pesos.length < 2) {
            return null;
        }
        const dias = pesos.map((punto) => new Date(punto.fecha).getTime());
        const valores = pesos.map((punto) => punto.peso);
        const [desde, hasta] = [Math.min(...dias), Math.max(...dias)];
        let [minimo, maximo] = [Math.min(...valores), Math.max(...valores)];
        if (maximo - minimo < 0.5) {
            minimo -= 0.5;
            maximo += 0.5;
        }
        const x = (dia) => MARGEN + ((dia - desde) / Math.max(hasta - desde, 1)) * (ANCHO - 2 * MARGEN);
        const y = (valor) => ALTO - MARGEN + 8 - ((valor - minimo) / (maximo - minimo)) * (ALTO - 2 * MARGEN);
        const puntos = pesos.map((punto, indice) => ({
            x: x(dias[indice]),
            y: y(punto.peso),
            texto: `${String(punto.peso).replace(".", ",")} kg`,
            fecha: this.fecha(punto.fecha),
            clave: indice,
        }));
        return {
            ancho: ANCHO,
            alto: ALTO,
            linea: puntos.map((punto) => `${punto.x.toFixed(1)},${punto.y.toFixed(1)}`).join(" "),
            puntos,
            primero: puntos[0],
            ultimo: puntos[puntos.length - 1],
        };
    }
}

registry.category("view_widgets").add("vet_linea_tiempo", { component: LineaTiempo });
