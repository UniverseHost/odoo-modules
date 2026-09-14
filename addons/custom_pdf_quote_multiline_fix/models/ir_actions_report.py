import io
import logging

from odoo import models

from ..pdf_appearance import bake_form_field_appearances

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        """Override to draw the form field values into the quotation PDF.

        The PDF Quote Builder fills ``/V`` and sets ``/NeedAppearances``, leaving the
        drawing to the viewer. pdfium (Chrome, Edge) does not word wrap while doing
        so and cuts a multiline note off at its first overflowing line. Laying the
        text out here makes the result identical in every viewer.
        """
        result = super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)
        if self._get_report(report_ref).report_name != 'sale.report_saleorder':
            return result

        multiline_names = set()
        for names in self.env['sale.pdf.form.field']._get_multiline_names_by_type().values():
            multiline_names |= names

        for res_id, values in result.items():
            stream = values.get('stream')
            if not stream:
                continue
            try:
                rewritten = bake_form_field_appearances(stream.getvalue(), multiline_names)
            except Exception:
                # Never lose the quotation over the appearance of its form fields.
                _logger.warning(
                    "Could not draw the form fields of sale.order %s, keeping the"
                    " original PDF", res_id, exc_info=True,
                )
                continue
            if rewritten:
                values['stream'] = io.BytesIO(rewritten)
        return result
