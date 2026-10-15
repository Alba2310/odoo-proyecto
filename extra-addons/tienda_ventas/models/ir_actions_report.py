# -*- coding: utf-8 -*-
from odoo import models

# Reportes impresos en papel de ticket; cada modelo define _alto_ticket_mm().
TICKETS = ('tienda_ventas.ticket_venta', 'tienda_ventas.ticket_cierre_caja')


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        # El largo del papel del ticket depende de lo que se imprime.
        report = self._get_report(report_ref)
        if res_ids and report.report_name in TICKETS:
            registros = self.env[report.model].browse(res_ids)
            self = self.with_context(tienda_ticket_alto_mm=max(r._alto_ticket_mm() for r in registros))
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def get_paperformat(self):
        paperformat = super().get_paperformat()
        alto = self.env.context.get('tienda_ticket_alto_mm')
        if alto and self.report_name in TICKETS:
            # Copia en memoria: no se modifica el formato guardado.
            return paperformat.new({'page_height': alto}, origin=paperformat)
        return paperformat
