{
    "name": "Signature Widget Options",
    "version": "18.0.2.0.0",
    "category": "Technical",
    "summary": "Configure which signature modes (Draw / Auto / Load) the generic "
               "signature widget offers, separately for backend and frontend.",
    "description": """
Signature Widget Options
========================

Odoo's generic signature widget always offers the three modes *Auto*, *Draw*
and *Load*.  This module makes that choice configurable per company and per
context:

* **Backend** -- the internal web client (form view widgets, signature fields,
  the signature dialog).
* **Frontend** -- portal and website pages (e.g. the quotation signature form).

Unchecking every mode of a context disables signature input there entirely.

Only the generic widget from the ``web`` module is affected.  Addons that ship
their own signature implementation by subclassing the component -- most notably
the Enterprise *Sign* app -- keep their stock behaviour.

This module contains no Python code, so it can be installed through
*Apps > Import Module* as well as from the addons path.  The configuration
fields are declared as manual fields and therefore carry the ``x_`` prefix
required by Odoo for custom fields.

``base_setup`` is required for ``res.config.settings.company_id``, which the
company-specific related fields are built on.
""",
    "author": "Rackbit IT",
    "license": "LGPL-3",
    "depends": ["base", "web", "base_setup"],
    "data": [
        "data/ir_model_fields.xml",
        "data/ir_default.xml",
        "views/res_config_settings_views.xml",
        "views/frontend_layout.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "signature_widget_options/static/src/js/signature_scope_backend.js",
            "signature_widget_options/static/src/js/signature_modes.js",
            "signature_widget_options/static/src/js/name_and_signature_patch.js",
            "signature_widget_options/static/src/xml/name_and_signature.xml",
        ],
        "web.assets_frontend": [
            "signature_widget_options/static/src/js/signature_scope_frontend.js",
            "signature_widget_options/static/src/js/signature_modes.js",
            "signature_widget_options/static/src/js/name_and_signature_patch.js",
            "signature_widget_options/static/src/xml/name_and_signature.xml",
        ],
    },
    "installable": True,
    "application": False,
}
