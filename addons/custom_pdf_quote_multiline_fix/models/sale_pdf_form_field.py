import base64
import logging

from odoo import api, fields, models

from ..pdf_appearance import get_multiline_form_fields

_logger = logging.getLogger(__name__)

# Which model holds the PDFs of each document type, and how to select them.
_DOCUMENT_MODELS = {
    'quotation_document': ('quotation.document', []),
    'product_document': ('product.document', [('attached_on_sale', '=', 'inside')]),
}


class SalePdfFormField(models.Model):
    _inherit = 'sale.pdf.form.field'

    is_multiline = fields.Boolean(
        string="Multiline in PDF",
        readonly=True,
        default=False,
        help="Detected automatically: the field carries the multiline flag in at least one of"
             " the PDF documents it is used in. Form field names are shared between documents"
             " of the same type, so a field counts as multiline as soon as one document"
             " declares it that way.",
    )

    # === BUSINESS METHODS === #

    @api.model
    def _create_or_update_form_fields_on_pdf_records(self, records, doc_type):
        """Override to detect the multiline flag of the fields of the uploaded PDFs."""
        result = super()._create_or_update_form_fields_on_pdf_records(records, doc_type)
        self._sync_multiline_flags(doc_types=[doc_type])
        return result

    @api.model
    def _cron_post_upgrade_assign_missing_form_fields(self):
        """Override to keep the multiline flags in sync after an upgrade."""
        result = super()._cron_post_upgrade_assign_missing_form_fields()
        self._sync_multiline_flags()
        return result

    @api.model
    def _get_multiline_names_by_type(self):
        """Return the names of the multiline form fields, grouped by document type.

        :rtype: dict[str, set]
        """
        names = {doc_type: set() for doc_type in _DOCUMENT_MODELS}
        for form_field in self.sudo().search([('is_multiline', '=', True)]):
            names.setdefault(form_field.document_type, set()).add(form_field.name)
        return names

    @api.model
    def _sync_multiline_flags(self, doc_types=None):
        """Refresh ``is_multiline`` from the PDFs currently stored on the documents.

        :param list doc_types: document types to refresh, all of them when omitted.
        :return: None
        """
        for doc_type in doc_types or list(_DOCUMENT_MODELS):
            model_name, domain = _DOCUMENT_MODELS[doc_type]
            documents = self.env[model_name].sudo().with_context(bin_size=False).search(domain)

            multiline_names = set()
            for document in documents:
                if not document.datas:
                    continue
                try:
                    multiline_names |= get_multiline_form_fields(
                        base64.b64decode(document.datas)
                    )
                except Exception:  # a single unreadable PDF must not break the sync
                    _logger.warning(
                        "Could not read the form fields of %s %s",
                        model_name, document.id, exc_info=True,
                    )

            form_fields = self.sudo().search([('document_type', '=', doc_type)])
            multiline = form_fields.filtered(lambda ff: ff.name in multiline_names)
            (multiline - multiline.filtered('is_multiline')).is_multiline = True
            stale = (form_fields - multiline).filtered('is_multiline')
            stale.is_multiline = False
