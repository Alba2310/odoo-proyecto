import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Nivel de combustible (0 a 100 %) que se marca arrastrando un slider,
 * como la aguja del tablero. Se usa en campos Integer: widget="fuel_slider".
 */
export class FuelSliderField extends Component {
    static template = "autoflow_management.FuelSliderField";
    static props = { ...standardFieldProps };

    setup() {
        // Mientras se arrastra se muestra el valor sin guardarlo en el registro.
        this.state = useState({ dragging: null });
    }

    get value() {
        return this.state.dragging ?? (this.props.record.data[this.props.name] || 0);
    }

    get badgeClass() {
        if (this.value <= 15) {
            return "text-bg-danger";
        }
        if (this.value <= 40) {
            return "text-bg-warning";
        }
        return "text-bg-success";
    }

    get label() {
        const marks = [
            [0, _t("Vacío")],
            [25, "1/4"],
            [50, "1/2"],
            [75, "3/4"],
            [100, _t("Lleno")],
        ];
        const closest = marks.reduce((best, mark) =>
            Math.abs(mark[0] - this.value) < Math.abs(best[0] - this.value) ? mark : best
        );
        return closest[1];
    }

    onInput(ev) {
        this.state.dragging = parseInt(ev.target.value, 10);
    }

    async onChange(ev) {
        await this.props.record.update({ [this.props.name]: parseInt(ev.target.value, 10) });
        this.state.dragging = null;
    }
}

export const fuelSliderField = {
    component: FuelSliderField,
    displayName: _t("Fuel level"),
    supportedTypes: ["integer"],
};

registry.category("fields").add("fuel_slider", fuelSliderField);
