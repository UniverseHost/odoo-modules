# PDF Quote Builder – Multiline Input Box

Importierbares Modul **ohne Python**. Gibt den mehrzeiligen PDF-Formularfeldern
im *Quote Builder*-Reiter eines Verkaufsauftrags eine echte mehrzeilige
Eingabebox.

Getestet gegen Odoo 18.0-20260908 über den echten Importweg
(`ir.module.module._import_zipfile`), mit `imported = True`.

---

## ⚠️ Was dieses Modul NICHT tut

Es behebt **nur die Eingabebox**, nicht die PDF-Ausgabe.

Der eigentliche Fehler – ein Absatz, der breiter als das Formularfeld ist, wird
im fertigen PDF **abgeschnitten statt umgebrochen** – bleibt bestehen. Das
Umbrechen erfordert eine Nachbearbeitung der erzeugten PDF mit PyPDF2, also
Python-Code, und der kann in einem importierten Modul grundsätzlich nicht
laufen.

### Warum importierte Module kein Python ausführen können

`odoo/modules/graph.py`:

```python
@functools.lru_cache(maxsize=1)
def _ignored_modules(cr):
    result = ['studio_customization']
    if tools.sql.column_exists(cr, 'ir_module_module', 'imported'):
        cr.execute('SELECT name FROM ir_module_module WHERE imported')
        result += [m[0] for m in cr.fetchall()]
    return result
```

Jedes Modul mit `imported = true` wird aus dem Modulgraphen ausgeschlossen.
`load_openerp_module()` wird dafür nie aufgerufen, das Python-Paket also nie
importiert – auch nach einem Neustart nicht.

Dazu passend verarbeitet `base_import_module._import_module()` aus dem Manifest
ausschließlich `.xml`, `.csv` und `.sql`:

```python
ext = os.path.splitext(filename)[1].lower()
if ext not in ('.xml', '.csv', '.sql'):
    _logger.info("module %s: skip unsupported file %s", module, filename)
    continue
```

Die entpackten Dateien liegen zudem nur in einem temporären Verzeichnis, das
nach dem Import verworfen wird. Erhalten bleiben `static/`-Dateien als
`ir.attachment`, die Manifest-Assets als `ir.asset` und die XML-Daten als
Records. Das ist Absicht (Sandboxing), kein Fehler.

**Für die PDF-Ausgabe brauchst du deshalb das Schwestermodul
`custom_pdf_quote_multiline_fix` im `addons_path`.**

## Was dieses Modul tut

Im Quote-Builder-Reiter ist jedes Feld bereits ein `<textarea>`, aber
`useAutoresize` setzt die Höhe auf `scrollHeight`. Bei leerem Feld ist das genau
eine Zeile – die Box sieht aus wie ein einzeiliges `<input>`, egal wie groß das
Feld im PDF ist.

Das Modul ergänzt ein Kennzeichen **Multiline in PDF** an der
Formularfeld-Konfiguration. Markierte Felder bekommen eine `min-height`,
einzeilige bleiben kompakt.

| Baustein | Umsetzung |
|---|---|
| Feld `x_is_multiline` | `ir.model.fields`-Record, `state=manual` (XML) |
| Spalte + Filter in der Konfigurationsliste | View-Vererbung (XML) |
| Flag ins Frontend holen | JS-Patch, liest `sale.pdf.form.field` per ORM |
| Prop an die Karte durchreichen | OWL-Template-Vererbung (`t-inherit`) |
| Höhe | SCSS `min-height` |

Kein Core- oder Enterprise-File wird verändert.

Das Feld heißt `x_is_multiline`, weil Odoo für manuelle Felder den Präfix `x_`
verlangt.

## Installation

*Apps → Import Module* → ZIP hochladen. Alternativ funktioniert auch der
normale Weg über den `addons_path`.

Rechte: Importieren darf nur ein Administrator. Für den Import muss
`base_import_module` installiert sein (in Odoo 18 über den Entwicklermodus,
*Apps → Import Module*).

## Einrichtung nach der Installation

Anders als die Python-Variante liest dieses Modul die PDFs **nicht** aus – es
kann das Multiline-Flag nicht selbst erkennen. Du setzt es einmalig von Hand:

1. Entwicklermodus aktivieren
2. *Einstellungen → Technisch → PDF-Formularfelder*
   (bzw. *Verkauf → Konfiguration → PDF-Formularfelder*)
3. In der Spalte **Multiline in PDF** die Felder anhaken, die im Quell-PDF
   mehrzeilig sind

Für `Werkvertrag_Individualsoftware.pdf` sind das:
`Projektbeschreibung`, `Meilensteine`, `Zahlungsplan`.

Welche Felder das in einem anderen PDF sind, verrät ein Blick auf das
Multiline-Bit (Bit 13, Wert 4096) im `/Ff`-Eintrag:

```python
import PyPDF2
reader = PyPDF2.PdfReader('deine_vorlage.pdf', strict=False)
for page in reader.pages:
    annots = page.get('/Annots')
    for ref in (annots.get_object() if annots is not None else []):
        annot = ref.get_object()
        if '/T' not in annot and '/Parent' in annot:
            annot = annot['/Parent'].get_object()
        if annot.get('/FT') == '/Tx' and int(annot.get('/Ff') or 0) & (1 << 12):
            print(annot.get('/T'))
```

Der Filter **Multiline** in der Suchleiste zeigt, was bereits markiert ist.

## Testschritte

1. Angebot öffnen → Reiter **Quote Builder**
2. Header-Dokument aktivieren
3. Vergleichen:
   * markierte Felder → hohe, mehrzeilige Box
   * nicht markierte Felder → weiterhin einzeilig
4. Mehrzeilig eintippen: die Box wächst beim Tippen weiter mit

Ein Haken wirkt sich erst nach dem Neuladen des Reiters aus, weil die Liste der
mehrzeiligen Felder beim Aufbau des Reiters einmal geladen wird.

## Deinstallation

Beim Deinstallieren wird das manuelle Feld `x_is_multiline` mitsamt Spalte
entfernt. Die gesetzten Haken gehen dabei verloren.
