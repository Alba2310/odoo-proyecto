# -*- coding: utf-8 -*-
from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _es_ticket(self):
        """Reportes impresos en papel de ticket. Su modelo define _alto_ticket_mm()."""
        papel = self.env.ref('tienda_ventas.paperformat_ticket_80mm', raise_if_not_found=False)
        return bool(papel) and self.paperformat_id == papel and hasattr(self.env[self.model], '_alto_ticket_mm')

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        # El largo del papel del ticket depende de lo que se imprime.
        report = self._get_report(report_ref)
        if res_ids and report._es_ticket():
            registros = self.env[report.model].browse(res_ids)
            self = self.with_context(tienda_ticket_alto_mm=max(r._alto_ticket_mm() for r in registros))
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def get_paperformat(self):
        paperformat = super().get_paperformat()
        alto = self.env.context.get('tienda_ticket_alto_mm')
        if alto and self._es_ticket():
            # Copia en memoria: no se modifica el formato guardado.
            return paperformat.new({'page_height': alto}, origin=paperformat)
        return paperformat
