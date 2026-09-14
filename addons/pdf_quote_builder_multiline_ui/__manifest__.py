{
    "name": "PDF Quote Builder - Multiline Input Box",
    "version": "18.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Show a real multi-line box for the multiline PDF form fields in the "
               "Quote Builder tab of a sales order.",
    "description": """
PDF Quote Builder - Multiline Input Box
=======================================

In the *Quote Builder* tab of a sales order every customizable form field is
rendered as a ``<textarea>``, but ``useAutoresize`` sets its height to the
height of its content. An empty field is therefore exactly one row high and
looks like a single line input, no matter how large the field is in the PDF.

This module adds a **Multiline in PDF** flag to the form field configuration.
Fields carrying that flag get a real multi-line box, single line fields stay
compact.

Scope
-----

This module only changes the **input box**. It does *not* change how the values
are drawn into the final PDF: line breaks that are wider than the form field
are still cut off by the PDF viewer instead of being wrapped, because fixing
that requires post-processing the generated PDF, which is Python and cannot run
in an imported module. See the README.

This module contains no Python code, so it can be installed through
*Apps > Import Module* as well as from the addons path. The flag is declared as
a manual field and therefore carries the ``x_`` prefix Odoo requires for custom
fields.
""",
    "author": "Rackbit IT",
    "license": "LGPL-3",
    "depends": ["sale_pdf_quote_builder"],
    "data": [
        "data/ir_model_fields.xml",
        "views/sale_pdf_form_field_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pdf_quote_builder_multiline_ui/static/src/js/multiline_form_fields.js",
            "pdf_quote_builder_multiline_ui/static/src/xml/custom_field_card.xml",
            "pdf_quote_builder_multiline_ui/static/src/scss/custom_field_card.scss",
        ],
    },
    "installable": True,
    "application": False,
}
