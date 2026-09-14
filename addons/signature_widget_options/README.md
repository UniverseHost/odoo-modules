# Signature Widget Options

Makes the modes of Odoo's generic signature widget configurable, per company
and separately for the backend and the frontend.

Odoo's signature widget always offers three modes:

| Mode | What it does |
| ---- | ------------ |
| **Draw** | Draw the signature by hand on a canvas |
| **Auto** | Generate the signature from the typed name in a handwriting font |
| **Load** | Upload an image file |

This module lets an administrator decide which of them are actually offered.

* **Backend** — the internal web client: the signature dialog, the `signature`
  field widget and the `signature` view widget.
* **Frontend** — portal and website pages, e.g. the quotation signature form.

Unchecking every mode of a context removes the signature area entirely there,
and the confirm button of the surrounding form stays disabled.

## Requirements

* Odoo **18.0**
* Depends on `base`, `web` and `base_setup`

> `base_setup` is needed for `res.config.settings.company_id`, which the
> company-specific settings are built on. It is part of every standard Odoo
> installation.

## Installation

The module contains **no Python code**, so both installation routes work.

### A. Import Module (no file system access needed)

*Apps* → *Import Module* → upload `signature_widget_options-<version>.zip`.

Developer mode must be enabled for the menu entry to appear.

### B. From the addons path

```bash
unzip signature_widget_options-<version>.zip -d /path/to/custom-addons/
# restart Odoo, then:
odoo -c /etc/odoo/odoo.conf -d <database> -i signature_widget_options --stop-after-init
```

In the Apps list, remove the default **Apps** filter before searching — the
module is declared with `"application": False` and is hidden by that filter.

> Pick one route, not both. An imported module stores its assets as
> `ir.asset` / `ir.attachment` records; if the same module is *also* present on
> the addons path, its manifest assets are registered a second time and the
> JavaScript is loaded twice.

## Configuration

*Settings* → *General Settings* → **Signature Widget (Backend)** and
**Signature Widget (Frontend)**.

The settings are stored on `res.company`, so in a multi-company database each
company has its own configuration; use the company selector at the top of the
settings page to switch. All six options default to enabled, which reproduces
Odoo's stock behaviour on install.

## Testing

**Frontend.** Take a quotation with *Online Signature* enabled, send it, open
its portal link and click *Sign*. Only the configured modes appear in the
signature card.

**Backend.** Open any form with a signature widget. With developer mode on, the
signature dialog can also be opened from the browser console:

```js
const env = odoo.__WOWL_DEBUG__.root.env;
const { SignatureDialog } = odoo.loader.modules.get("@web/core/signature/signature_dialog");
env.services.dialog.add(SignatureDialog, {
    defaultName: "Test",
    nameAndSignatureProps: {},
    uploadSignature: () => {},
});
```

Changing a setting takes effect on the next page load.

## How it works

Everything is data records and static assets — this is what makes the module
importable, since *Import Module* deliberately discards Python files.

* The six configuration fields on `res.company` and their six `related`
  counterparts on `res.config.settings` are **manual fields**, declared as
  `ir.model.fields` records. Odoo requires custom fields to be prefixed, hence
  the `x_` in `x_signature_backend_mode_draw` and friends.
* `data/ir_model_fields.xml` ends with a `<function>` call that enables all
  modes on the existing companies, and `data/ir_default.xml` registers the same
  default for companies created later. Without those, the freshly added columns
  would be `NULL` and signing would be disabled everywhere right after install.
* `views/frontend_layout.xml` injects the current company's configuration into
  the page as `odoo.__signature_widget_options__`, once for
  `web.frontend_layout` (frontend, rendered from `request.env.company`) and once
  for `web.webclient_bootstrap` (backend, rendered for every company the user may
  access). The JavaScript therefore needs no RPC and the configuration is
  available before the first render.
* `NameAndSignature.prototype` is patched to restrict `allowedSignModes` and to
  realign `state.signMode` in `setup`, so the signature pad never starts in a
  mode the user cannot see. The template extension drops the buttons of disabled
  modes and, when nothing is left, the whole signature area.
* The scope is derived from the asset bundle that loaded the code
  (`signature_scope_backend.js` in `web.assets_backend`,
  `signature_scope_frontend.js` in `web.assets_frontend`), which matches exactly
  how the page was served.
* If the injected configuration is missing, all modes are reported as allowed,
  so a problem here can never make signing impossible.

## Scope and known behaviour

* **The Enterprise *Sign* app is not affected.** It ships its own signature
  flow by subclassing `NameAndSignature`; the patch only restricts instances of
  the generic component itself and leaves subclasses at stock behaviour.
* **When *Load* is the only enabled mode**, the file picker opens as soon as
  the signature area is rendered. That is Odoo's own behaviour for the *Load*
  mode and is not changed here.
* An **imported** module cannot be upgraded with `-u`; ship a new version by
  importing the new zip over it.
* Uninstalling drops the manual fields and with them the stored configuration.

## License

LGPL-3
