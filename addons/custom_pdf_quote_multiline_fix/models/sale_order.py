from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def get_update_included_pdf_params(self):
        """Override to tell the Quote Builder tab which form fields are multiline."""
        params = super().get_update_included_pdf_params()
        if not self:
            return params

        multiline_names = self.env['sale.pdf.form.field']._get_multiline_names_by_type()
        for key in ('headers', 'footers'):
            section = params.get(key) or {}
            self._flag_multiline_form_fields(
                section.get('files') or (), multiline_names.get('quotation_document', set())
            )
        for section in params.get('lines') or ():
            self._flag_multiline_form_fields(
                section.get('files') or (), multiline_names.get('product_document', set())
            )
        return params

    @staticmethod
    def _flag_multiline_form_fields(files, multiline_names):
        for document in files:
            for form_field in document.get('custom_form_fields') or ():
                form_field['multiline'] = form_field.get('name') in multiline_names
