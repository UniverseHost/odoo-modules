"""Draw the values of the AcroForm text fields into their appearance streams.

``odoo.tools.pdf.fill_form_fields_pdf`` writes the field value into ``/V``, sets
``/NeedAppearances true`` and leaves the drawing to the viewer, because PyPDF2
cannot rebuild ``/AP /N`` itself. Viewers disagree on how to do that drawing:
pdfium - Chrome and Edge - does not word wrap a multiline field and cuts the
text off at the first line that overflows, which is what makes a long note lose
everything past its first line.

This module lays the text out with the metrics of the font the field asks for,
writes the result into ``/AP /N``, and switches ``/NeedAppearances`` off so no
viewer redraws it differently. The switch only happens when every filled field
could be drawn, so a field that cannot be handled here keeps being rendered by
the viewer rather than turning blank.
"""

import io
import logging

from odoo.tools.pdf import (
    DecodedStreamObject,
    BooleanObject,
    NameObject,
    PdfFileReader,
    PdfFileWriter,
    createStringObject,
)

_logger = logging.getLogger(__name__)

MULTILINE_FLAG = 1 << 12
PASSWORD_FLAG = 1 << 13
FILE_SELECT_FLAG = 1 << 20
COMB_FLAG = 1 << 24

# Padding Acrobat leaves between the field border and the text, in points.
PADDING = 2.0
# Font sizes considered when the field asks for auto-sizing.
MIN_AUTO_FONT_SIZE = 4.0
MAX_AUTO_FONT_SIZE = 12.0
# Line spacing Acrobat uses for a multiline field, as a multiple of the font size.
MIN_LEADING_FACTOR = 1.15

# The text of a form field lives in a marked content section inside the appearance
# stream; everything around it draws the background and the border of the field.
_MARKED_CONTENT_START = b'/Tx BMC'
_MARKED_CONTENT_END = b'EMC'

# Widths of Helvetica, used only when the font of the field carries no /Widths.
_HELVETICA_WIDTHS = {
    32: 278, 33: 278, 34: 355, 35: 556, 36: 556, 37: 889, 38: 667, 39: 191,
    40: 333, 41: 333, 42: 389, 43: 584, 44: 278, 45: 333, 46: 278, 47: 278,
    48: 556, 49: 556, 50: 556, 51: 556, 52: 556, 53: 556, 54: 556, 55: 556,
    56: 556, 57: 556, 58: 278, 59: 278, 60: 584, 61: 584, 62: 584, 63: 556,
    64: 1015, 65: 667, 66: 667, 67: 722, 68: 722, 69: 667, 70: 611, 71: 778,
    72: 722, 73: 278, 74: 500, 75: 667, 76: 556, 77: 833, 78: 722, 79: 778,
    80: 667, 81: 778, 82: 722, 83: 667, 84: 611, 85: 722, 86: 667, 87: 944,
    88: 667, 89: 667, 90: 611, 91: 278, 92: 278, 93: 278, 94: 469, 95: 556,
    96: 333, 97: 556, 98: 556, 99: 500, 100: 556, 101: 556, 102: 278, 103: 556,
    104: 556, 105: 222, 106: 222, 107: 500, 108: 222, 109: 833, 110: 556,
    111: 556, 112: 556, 113: 556, 114: 333, 115: 500, 116: 278, 117: 556,
    118: 500, 119: 722, 120: 500, 121: 500, 122: 500, 123: 334, 124: 260,
    125: 334, 126: 584,
}
_DEFAULT_WIDTH = 556


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class FontMetrics:
    """Measure a string with the metrics of a simple (single byte) PDF font."""

    def __init__(self, font=None):
        self.widths = {}
        self.default_width = _DEFAULT_WIDTH
        self.ascent = 750.0
        self.descent = -250.0

        if font is None:
            self.widths = dict(_HELVETICA_WIDTHS)
            return

        first_char = font.get('/FirstChar')
        raw_widths = font.get('/Widths')
        if raw_widths is not None and first_char is not None:
            first_char = int(_as_float(first_char))
            for offset, width in enumerate(raw_widths.get_object()):
                self.widths[first_char + offset] = _as_float(width)
        else:
            self.widths = dict(_HELVETICA_WIDTHS)

        descriptor = font.get('/FontDescriptor')
        if descriptor is not None:
            descriptor = descriptor.get_object()
            self.ascent = _as_float(descriptor.get('/Ascent'), self.ascent)
            self.descent = _as_float(descriptor.get('/Descent'), self.descent)
            self.default_width = _as_float(
                descriptor.get('/MissingWidth'), self.default_width
            )

    @staticmethod
    def encode(text):
        """Encode to the single byte encoding used by the /Differences of the font."""
        return text.encode('cp1252', errors='replace')

    def char_width(self, code, font_size):
        # A width of 0 in the /Widths array means "not covered by this font".
        width = self.widths.get(code) or self.default_width
        return width / 1000.0 * font_size

    def text_width(self, text, font_size):
        return sum(self.char_width(code, font_size) for code in self.encode(text))

    def leading(self, font_size):
        # Fonts that ship no descriptor fall back to a tight 1.0 em; keep the line
        # spacing Acrobat uses for multiline fields as a lower bound.
        factor = max((self.ascent - self.descent) / 1000.0, MIN_LEADING_FACTOR)
        return factor * font_size

    def first_baseline_offset(self, font_size):
        return self.ascent / 1000.0 * font_size


def _format_number(value):
    formatted = '%.4f' % value
    if '.' in formatted:
        formatted = formatted.rstrip('0').rstrip('.')
    return formatted or '0'


def _parse_default_appearance(da):
    """Split a /DA string into (font name, font size, tokens, index of the Tf operator).

    ``/Fo1Form 12.00000 Tf 0.09 0.09 0.08 rg`` -> ``('Fo1Form', 12.0, [...], 2)``
    """
    tokens = (da or '').split()
    for index, token in enumerate(tokens):
        if token == 'Tf' and index >= 2 and tokens[index - 2].startswith('/'):
            return tokens[index - 2][1:], _as_float(tokens[index - 1]), tokens, index
    return None, 0.0, tokens, None


def _rebuild_default_appearance(tokens, tf_index, font_size):
    """Return the /DA operators with the font size replaced."""
    if tf_index is None:
        return ' '.join(tokens)
    tokens = list(tokens)
    tokens[tf_index - 1] = _format_number(font_size)
    return ' '.join(tokens)


def _split_long_word(word, metrics, font_size, available_width):
    """Break a word that does not fit on a line of its own, character by character."""
    chunks = []
    current = ''
    for char in word:
        if current and metrics.text_width(current + char, font_size) > available_width:
            chunks.append(current)
            current = char
        else:
            current += char
    if current:
        chunks.append(current)
    return chunks or ['']


def wrap(value, metrics, font_size, available_width):
    """Split the value into the lines that will be drawn, honouring its line breaks."""
    lines = []
    normalized = value.replace('\r\n', '\n').replace('\r', '\n')
    for paragraph in normalized.split('\n'):
        if not paragraph:
            lines.append('')
            continue
        current = ''
        for word in paragraph.split(' '):
            candidate = word if not current else current + ' ' + word
            if metrics.text_width(candidate, font_size) <= available_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            if metrics.text_width(word, font_size) > available_width:
                chunks = _split_long_word(word, metrics, font_size, available_width)
                lines.extend(chunks[:-1])
                current = chunks[-1]
            else:
                current = word
        lines.append(current)
    return lines


def _escape(raw_bytes):
    escaped = bytearray()
    for byte in raw_bytes:
        if byte in (0x28, 0x29, 0x5C):  # ( ) \
            escaped.append(0x5C)
            escaped.append(byte)
        elif byte < 32 or byte > 126:
            escaped += ('\\%03o' % byte).encode('ascii')
        else:
            escaped.append(byte)
    return bytes(escaped)


def _line_offset(line, metrics, font_size, available_width, quadding):
    if quadding == 1:  # centered
        return (available_width - metrics.text_width(line, font_size)) / 2.0
    if quadding == 2:  # right aligned
        return available_width - metrics.text_width(line, font_size)
    return 0.0


def _fits(lines, metrics, font_size, available_width, available_height):
    if len(lines) * metrics.leading(font_size) > available_height:
        return False
    return all(metrics.text_width(line, font_size) <= available_width for line in lines)


def layout(value, width, height, da, metrics, multiline):
    """Break ``value`` into the lines that fit the field box.

    :param bool multiline: word wrap when True, keep a single line otherwise.
    :return: ``(lines, font size)``, or None when the box is too small to draw in.
    :rtype: tuple | None
    """
    _font_name, font_size, _tokens, _tf_index = _parse_default_appearance(da)
    available_width = width - 2 * PADDING
    available_height = height - 2 * PADDING
    if available_width <= 0 or available_height <= 0:
        return None

    def split(size):
        if multiline:
            return wrap(value, metrics, size, available_width)
        return [' '.join(value.split())]

    if font_size <= 0:  # auto-sized field: shrink until the text fits
        font_size = MIN_AUTO_FONT_SIZE
        candidate = MAX_AUTO_FONT_SIZE
        while candidate >= MIN_AUTO_FONT_SIZE:
            if _fits(split(candidate), metrics, candidate, available_width, available_height):
                font_size = candidate
                break
            candidate -= 0.5

    return split(font_size), font_size


def build_stream(lines, font_size, width, height, da, quadding, metrics, multiline):
    """Return the content stream drawing ``lines`` inside a ``width`` x ``height`` box."""
    _font_name, _size, tokens, tf_index = _parse_default_appearance(da)
    available_width = width - 2 * PADDING
    available_height = height - 2 * PADDING
    leading = metrics.leading(font_size)
    if multiline:
        baseline = height - PADDING - metrics.first_baseline_offset(font_size)
    else:
        # Acrobat centres the text of a single line field vertically in its box.
        text_height = (metrics.ascent - metrics.descent) / 1000.0 * font_size
        baseline = (height - text_height) / 2.0 - metrics.descent / 1000.0 * font_size

    operators = [
        b'/Tx BMC',
        b'q',
        # Clip on the field box so an overflowing text cannot bleed onto the page.
        ('%s %s %s %s re' % (
            _format_number(PADDING),
            _format_number(PADDING),
            _format_number(available_width),
            _format_number(available_height),
        )).encode('ascii'),
        b'W',
        b'n',
        b'BT',
        _rebuild_default_appearance(tokens, tf_index, font_size).encode('ascii'),
    ]
    for line in lines:
        if baseline < -leading:  # entirely below the field, nothing left to draw
            break
        if line:
            offset = _line_offset(line, metrics, font_size, available_width, quadding)
            operators.append(('1 0 0 1 %s %s Tm' % (
                _format_number(PADDING + offset), _format_number(baseline),
            )).encode('ascii'))
            operators.append(b'(' + _escape(metrics.encode(line)) + b') Tj')
        baseline -= leading
    operators += [b'ET', b'Q', b'EMC']
    return b'\n'.join(operators)


def replace_marked_content(existing_stream, marked_content):
    """Swap the ``/Tx BMC ... EMC`` section of an appearance stream.

    Everything outside that section paints the background and the border of the
    field, so it has to survive untouched.

    :param bytes existing_stream: the appearance stream currently on the widget.
    :param bytes marked_content: the replacement, starting with ``/Tx BMC``.
    :rtype: bytes
    """
    start = existing_stream.find(_MARKED_CONTENT_START)
    if start == -1:
        return existing_stream + b'\n' + marked_content
    end = existing_stream.rfind(_MARKED_CONTENT_END)
    if end < start:
        return existing_stream[:start] + marked_content
    return (
        existing_stream[:start]
        + marked_content
        + existing_stream[end + len(_MARKED_CONTENT_END):]
    )


# Entries that describe the encoding of the old stream and must not be carried over.
_ENCODING_KEYS = ('/Filter', '/DecodeParms', '/DecodeParams', '/DL', '/Length')


def _replace_appearance_stream(writer, appearance, old_stream, data):
    """Put ``data`` in ``/AP /N``, replacing the stream object when it is compressed.

    PyPDF2 refuses ``set_data`` on an encoded (usually Flate compressed) stream, so
    an uncompressed copy that keeps every other entry - ``/BBox``, ``/Resources``,
    ``/Subtype`` - takes its place.

    :param PdfFileWriter writer: the writer owning the object.
    :param dict appearance: the ``/AP`` dictionary of the widget.
    :param old_stream: the current ``/AP /N`` stream object.
    :param bytes data: the new content stream.
    :return: None
    """
    new_stream = DecodedStreamObject()
    for key, entry in old_stream.items():
        if key not in _ENCODING_KEYS:
            new_stream[NameObject(key)] = entry
    new_stream.set_data(data)
    appearance[NameObject('/N')] = writer._add_object(new_stream)


def _resolve(container, key):
    value = container.get(key) if container is not None else None
    return value.get_object() if value is not None else None


def _get_field_font(font_name, appearance, acroform):
    """Look the /DA font up in the resources of the appearance, then in /DR."""
    for resources in (_resolve(appearance, '/Resources'), _resolve(acroform, '/DR')):
        fonts = _resolve(resources, '/Font')
        if fonts and '/' + font_name in fonts:
            return _resolve(fonts, '/' + font_name)
    return None


def _iter_widgets(page):
    """Yield (widget annotation, field dictionary) for every annotation of a page."""
    annots = page.get('/Annots')
    if annots is None:
        return
    for annot_ref in annots.get_object():
        annot = annot_ref.get_object()
        field = annot
        if '/FT' not in field and '/Parent' in field:
            field = field['/Parent'].get_object()
        yield annot, field


def _inherited(annot, field, key, default=None):
    for source in (annot, field):
        if key in source:
            return source[key]
    return default


def _matches_multiline_name(prefixed_name, multiline_names):
    """The Quote Builder prefixes every field name with the document identifier."""
    if not prefixed_name or not multiline_names:
        return False
    prefixed_name = str(prefixed_name)
    if prefixed_name in multiline_names:
        return True
    return any(prefixed_name.endswith('__' + name) for name in multiline_names)


def bake_form_field_appearances(pdf_bytes, multiline_names=()):
    """Draw the value of every filled text field of ``pdf_bytes`` into its appearance.

    The PDF Quote Builder relies on ``/NeedAppearances`` to have the viewer draw the
    values it wrote into ``/V``. Viewers disagree on how to do that: pdfium (Chrome,
    Edge) does not word wrap and cuts an overflowing line off. Drawing the text here
    and switching ``/NeedAppearances`` off makes the output identical everywhere.

    ``/NeedAppearances`` is only switched off when *every* filled field could be
    drawn, so a field this function cannot handle keeps being rendered by the viewer
    instead of silently turning blank.

    :param bytes pdf_bytes: the PDF produced by the PDF Quote Builder.
    :param iterable multiline_names: unprefixed names of the form fields that are
        flagged as multiline in the source PDFs. A field also counts as multiline
        when its value contains a line break.
    :return: the rewritten PDF, or None when nothing had to be changed.
    :rtype: bytes | None
    """
    multiline_names = set(multiline_names or ())
    reader = PdfFileReader(io.BytesIO(pdf_bytes), strict=False)
    if _resolve(reader.trailer['/Root'], '/AcroForm') is None:
        return None  # a quotation without any attached form, nothing to draw

    writer = PdfFileWriter()
    writer.clone_document_from_reader(reader)
    acroform = _resolve(writer._root_object, '/AcroForm')
    if acroform is None:
        return None
    form_quadding = _as_float(acroform.get('/Q'), 0.0)
    form_da = acroform.get('/DA')

    rebuilt = 0
    skipped = 0
    for page in writer.pages:
        for annot, field in _iter_widgets(page):
            if field.get('/FT') != '/Tx':
                continue
            value = field.get('/V')
            if not isinstance(value, str) or not value.strip():
                continue  # an empty field has nothing to draw

            name = field.get('/T')
            flags = int(_as_float(field.get('/Ff'), 0.0))
            # Comb, password and file select fields have their own layout rules.
            if flags & (COMB_FLAG | PASSWORD_FLAG | FILE_SELECT_FLAG):
                skipped += 1
                continue

            # The Quote Builder flags every text field as multiline, so the flag in
            # the merged file says nothing; go by the source PDF and by the value.
            multiline = (
                '\n' in value
                or '\r' in value
                or _matches_multiline_name(name, multiline_names)
            )

            appearance = _resolve(annot, '/AP')
            normal = _resolve(appearance, '/N')
            # A dictionary of appearance states has no stream to rewrite.
            if normal is None or not hasattr(normal, 'get_data'):
                skipped += 1
                continue
            bbox = normal.get('/BBox')
            if bbox is None or len(bbox) != 4:
                skipped += 1
                continue
            width = abs(_as_float(bbox[2]) - _as_float(bbox[0]))
            height = abs(_as_float(bbox[3]) - _as_float(bbox[1]))
            if width <= 0 or height <= 0:
                skipped += 1
                continue

            da = _inherited(annot, field, '/DA', form_da)
            font_name, _size, _tokens, tf_index = _parse_default_appearance(da)
            if tf_index is None:
                skipped += 1  # no font to draw with, leave the field to the viewer
                continue
            font = _get_field_font(font_name, normal, acroform)
            if font is not None and font.get('/Subtype') == '/Type0':
                # Composite fonts are addressed by CID, not by byte: refuse rather
                # than write a wrongly encoded string.
                _logger.info(
                    "Form field %s uses the composite font %s, leaving it to the viewer",
                    name, font_name,
                )
                skipped += 1
                continue

            quadding = int(_as_float(_inherited(annot, field, '/Q', form_quadding), 0.0))
            metrics = FontMetrics(font)
            layouted = layout(value, width, height, da, metrics, multiline)
            if layouted is None:
                skipped += 1
                continue
            lines, font_size = layouted

            # Should a viewer regenerate the appearance anyway, the hard line breaks
            # keep it from cutting the text off at the first overflowing line.
            wrapped_value = '\n'.join(lines)
            if wrapped_value != value:
                field[NameObject('/V')] = createStringObject(wrapped_value)

            marked_content = build_stream(
                lines, font_size, width, height, da, quadding, metrics, multiline
            )
            _replace_appearance_stream(
                writer, appearance, normal,
                replace_marked_content(normal.get_data(), marked_content),
            )
            # Drop a stale /AS so the viewer cannot pick another appearance state.
            annot.pop(NameObject('/AS'), None)
            rebuilt += 1

    if not rebuilt:
        return None

    if skipped:
        _logger.info(
            "Drew %s form field(s); %s left to the viewer, so /NeedAppearances stays on",
            rebuilt, skipped,
        )
    else:
        acroform[NameObject('/NeedAppearances')] = BooleanObject(False)
        _logger.debug("Drew %s form field(s) and switched /NeedAppearances off", rebuilt)

    with io.BytesIO() as buffer:
        writer.write(buffer)
        return buffer.getvalue()


def get_multiline_form_fields(pdf_bytes):
    """Return the names of the text fields flagged as multiline in ``pdf_bytes``.

    :param bytes pdf_bytes: the decoded PDF.
    :rtype: set
    """
    names = set()
    reader = PdfFileReader(io.BytesIO(pdf_bytes), strict=False)
    for page in reader.pages:
        for _annot, field in _iter_widgets(page):
            if field.get('/FT') != '/Tx':
                continue
            if int(_as_float(field.get('/Ff'), 0.0)) & MULTILINE_FLAG:
                name = field.get('/T')
                if name:
                    names.add(str(name))
    return names
