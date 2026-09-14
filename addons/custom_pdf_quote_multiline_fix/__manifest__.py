{
    'name': "PDF Quote Builder - Multiline Fix",
    'summary': "Multiline form fields work end to end in the PDF Quote Builder",
    'description': """
Two targeted fixes for the multiline AcroForm text fields of the PDF Quote Builder:

* the Quote Builder tab of a sales order shows a real multi-line box for the form
  fields that carry the multiline flag in the PDF, instead of a box collapsed to a
  single row;
* the values are drawn into the appearance streams of the final PDF, with word
  wrapping, so a long note no longer loses everything past its first line in the
  viewers that do not wrap while regenerating the appearance themselves.

Nothing is patched in place: everything goes through _inherit and asset
extensions.
""",
    'category': 'Sales/Sales',
    'version': '18.0.1.0.0',
    'depends': ['sale_pdf_quote_builder'],
    'data': [
        'views/sale_pdf_form_field_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_pdf_quote_multiline_fix/static/src/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
}
