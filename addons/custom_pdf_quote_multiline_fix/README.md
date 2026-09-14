# PDF Quote Builder – Multiline Fix

Behebt zwei Probleme mit mehrzeiligen AcroForm-Feldern im **PDF Quote Builder**
(`sale_pdf_quote_builder`, Odoo 18).

Getestet gegen Odoo 18.0-20260908 (Community-Docker-Image) mit PyPDF2 2.12.1.

---

## Das Problem

### (a) Eingabebox im Verkaufsauftrag

Die Komponente `CustomFieldCard` rendert bereits ein `<textarea>` – aber
`useAutoresize` (`web/static/src/core/utils/autoresize.js`) setzt die Höhe auf
`scrollHeight`. Bei leerem Feld ist das **genau eine Zeile**, zusammen mit
`resize: none` und `overflow-y-hidden` wirkt die Box wie ein einzeiliges
`<input>`.

### (b) Zeilenumbrüche in der finalen PDF

`ir.actions.report._add_pages_to_writer` im Quote Builder setzt bei **jedem**
Textfeld das Multiline-Flag (`/Ff |= 1<<12`), unabhängig vom Quell-PDF – das
Flag in der hochgeladenen PDF ist für den Export also gar nicht relevant.

`odoo.tools.pdf.fill_form_fields_pdf` schreibt den Wert nach `/V`, setzt
`/NeedAppearances true` und überlässt das Zeichnen dem Viewer, weil PyPDF2
`/AP /N` nicht selbst neu erzeugen kann. Und genau hier gehen die Viewer
auseinander:

| Viewer | Verhalten bei `/NeedAppearances true` |
|---|---|
| Adobe Acrobat/Reader | zeichnet neu, bricht um |
| **pdfium** (Chrome, Edge) | zeichnet neu, **bricht nicht um** – schneidet ab der ersten überlaufenden Zeile ab |
| Viewer ohne NeedAppearances-Support | zeigt den alten, meist leeren Appearance-Stream |

Harte `\n` kommen dabei durch, aber ein längerer Absatz verliert alles ab der
ersten zu breiten Zeile. Das ist die sichtbare Fehlerursache.

## Die Lösung

* **(a)** Das Modell `sale.pdf.form.field` bekommt ein Feld `is_multiline`, das
  beim Upload (und beim Modul-Install) aus dem PDF ausgelesen wird.
  `sale.order.get_update_included_pdf_params()` gibt das Flag an das Frontend
  weiter, eine Template-Erweiterung reicht es als Prop `multiline` an
  `CustomFieldCard` durch, und eine `min-height`-Regel gibt der Textarea eine
  echte mehrzeilige Starthöhe. Einzeilige Felder bleiben unverändert kompakt.

* **(b)** `ir.actions.report._render_qweb_pdf_prepare_streams` wird per
  `_inherit` erweitert. Nach dem Rendern werden die Feldwerte mit den Metriken
  der im `/DA` angegebenen Schrift umbrochen, in `/AP /N` gezeichnet und
  `/NeedAppearances` abgeschaltet, damit kein Viewer noch etwas anderes malt.

### Was dabei bewusst geschieht

* **Alle** befüllten Textfelder werden gezeichnet, nicht nur die mehrzeiligen.
  Das ist zwingend: sobald `/NeedAppearances` aus ist, zeichnet der Viewer gar
  nichts mehr, also müsste ein übergangenes Feld leer bleiben. Einzeilige Felder
  werden dabei vertikal zentriert, wie Acrobat es tut.
* `/NeedAppearances` wird **nur dann** abgeschaltet, wenn wirklich jedes
  befüllte Feld gezeichnet werden konnte. Bleibt auch nur eines übrig (Comb-,
  Passwort-, Datei-Feld, Type0/CID-Schrift, fehlender `/DA`-Font, fehlender
  Appearance-Stream), bleibt das Flag an und alles verhält sich wie bisher.
  Im Log steht dann eine INFO-Zeile mit der Anzahl.
* Der bestehende Appearance-Stream wird **nicht** komplett ersetzt – nur der
  Abschnitt zwischen `/Tx BMC` und `EMC`. Feldhintergrund, Rahmen und
  Unterstriche des Quell-PDFs bleiben damit erhalten.
* Der umbrochene Text wird zusätzlich nach `/V` zurückgeschrieben. Falls ein
  Viewer die Darstellung doch neu erzeugt, sind die weichen Umbrüche dann harte
  Zeilenumbrüche und der Text wird nicht abgeschnitten.
* Bei jedem Fehler wird geloggt und die **unveränderte** PDF ausgeliefert.

### Bekannte Grenzen

* Composite-Schriften (`/Subtype /Type0`, CID-kodiert) werden übersprungen –
  eine byteweise Kodierung wäre dort schlicht falsch. `/NeedAppearances` bleibt
  dann an.
* Der Text wird nach **cp1252** kodiert; Zeichen außerhalb (z. B. Kyrillisch,
  Griechisch) werden zu `?`. Das entspricht dem, was einfache PDF-Schriften mit
  WinAnsi-Encoding darstellen können.
* `is_multiline` gilt pro Feldname und Dokumenttyp, nicht pro Dokument – so ist
  das Datenmodell von `sale.pdf.form.field` aufgebaut. Trägt ein Feldname in
  einem Dokument das Multiline-Flag, gilt er überall als mehrzeilig. Das
  betrifft nur die Höhe der Eingabebox, nicht die PDF-Ausgabe.
* Kein Core- oder Enterprise-File wird verändert; alles läuft über `_inherit`,
  View-Vererbung und Asset-Erweiterung.

---

## Installation

Das Modul liegt bereits unter `addons/custom_pdf_quote_multiline_fix` und ist
damit im Container als `/mnt/extra-addons/...` sichtbar.

```powershell
# installieren
docker compose -p odoo-module-signature-widget-options run --rm --no-deps odoo `
  odoo -c /etc/odoo/odoo.conf -d dev -i custom_pdf_quote_multiline_fix --stop-after-init

# aktualisieren
docker compose -p odoo-module-signature-widget-options run --rm --no-deps odoo `
  odoo -c /etc/odoo/odoo.conf -d dev -u custom_pdf_quote_multiline_fix --stop-after-init
```

> Der Projektname `-p odoo-module-signature-widget-options` ist nötig, weil die
> vorhandenen Volumes (`..._odoo-db-data`) noch unter dem alten Ordnernamen
> angelegt wurden. Ohne ihn legt Compose ein zweites, leeres Setup an.

Alternativ in Odoo unter *Apps → Update Apps List* und dann
*PDF Quote Builder - Multiline Fix* installieren.

Beim Installieren liest ein `post_init_hook` alle bereits hochgeladenen
Header-/Footer- und Produkt-PDFs und setzt `is_multiline`. Danach passiert das
automatisch bei jedem Upload.

## Testschritte

### 1. Erkennung prüfen

*Verkauf → Konfiguration → PDF-Formularfelder* (bzw. direkt in der DB):

```sql
SELECT name, document_type, is_multiline
FROM sale_pdf_form_field WHERE is_multiline;
```

Für `Werkvertrag_Individualsoftware.pdf` müssen genau diese drei erscheinen:
`Projektbeschreibung`, `Meilensteine`, `Zahlungsplan`.

### 2. Eingabebox im Verkaufsauftrag

1. Angebot öffnen → Reiter **Quote Builder**
2. Header `Werkvertrag_Individualsoftware.pdf` aktivieren
3. Vergleichen:
   * `Zahlungsplan`, `Meilensteine`, `Projektbeschreibung` → hohe, mehrzeilige Box
   * `Angebotsnummer`, `Stundensatz`, `Wartung_Option` → weiterhin einzeilig
4. In `Zahlungsplan` mehrzeilig eintippen, inklusive Leerzeile und eines
   Absatzes, der breiter als das Feld ist. Die Box wächst beim Tippen mit.
5. Speichern.

### 3. PDF prüfen

**Drucken → Angebot / Auftragsbestätigung**, dann die PDF **in Chrome** öffnen –
Chrome ist der Viewer, der den Fehler ausgelöst hat.

Erwartet:
* die harten Zeilenumbrüche stehen an derselben Stelle wie in der Eingabe,
* die Leerzeile bleibt erhalten,
* der lange Absatz ist **umbrochen statt abgeschnitten**,
* Umlaute stimmen,
* Feldhintergrund und Unterstriche sehen aus wie vorher,
* die einzeiligen Felder stehen unverändert an ihrem Platz.

Zur Gegenprobe (zeigt den alten Zustand):

```python
# odoo shell -d dev
from odoo.addons.sale_pdf_quote_builder.models.ir_actions_report import IrActionsReport as Base
report = env.ref('sale.action_report_saleorder').sudo()
streams = Base._render_qweb_pdf_prepare_streams(report, 'sale.report_saleorder', {}, res_ids=[<ID>])
open('/tmp/ohne_fix.pdf', 'wb').write(streams[<ID>]['stream'].getvalue())
```

`/tmp/ohne_fix.pdf` umgeht den Override und zeigt den abgeschnittenen Absatz.

### 4. Unit-Tests

```powershell
docker compose -p odoo-module-signature-widget-options run --rm --no-deps odoo `
  odoo -c /etc/odoo/odoo.conf -d dev -u custom_pdf_quote_multiline_fix `
  --test-enable --test-tags /custom_pdf_quote_multiline_fix --stop-after-init
```

## Aufbau

| Datei | Zweck |
|---|---|
| `pdf_appearance.py` | Textlayout und Appearance-Streams (ohne Odoo-Abhängigkeit außer `odoo.tools.pdf`) |
| `models/sale_pdf_form_field.py` | Feld `is_multiline` + Erkennung aus dem PDF |
| `models/sale_order.py` | reicht das Flag an den Quote-Builder-Tab weiter |
| `models/ir_actions_report.py` | Hook nach dem Rendern des Angebots |
| `static/src/js/…` | meldet den Prop `multiline` an `CustomFieldCard` an |
| `static/src/xml/…` | Template-Vererbung: Prop durchreichen, CSS-Klasse setzen |
| `static/src/scss/…` | `min-height` für mehrzeilige Felder |
| `views/…` | Spalte `Multiline in PDF` in der Formularfeld-Liste |
