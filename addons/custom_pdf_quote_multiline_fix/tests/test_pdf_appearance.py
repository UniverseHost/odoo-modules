from odoo.tests import TransactionCase, tagged

from odoo.addons.custom_pdf_quote_multiline_fix.pdf_appearance import (
    FontMetrics,
    build_stream,
    layout,
    replace_marked_content,
    wrap,
)


@tagged('post_install', '-at_install')
class TestPdfAppearance(TransactionCase):
    """The text layout is pure computation, so it is tested without a PDF."""

    def setUp(self):
        super().setUp()
        self.metrics = FontMetrics()  # Helvetica fallback metrics

    def test_wrap_keeps_explicit_line_breaks(self):
        lines = wrap('a\nb\n\nc', self.metrics, 9, 500)
        self.assertEqual(lines, ['a', 'b', '', 'c'])

    def test_wrap_breaks_on_the_available_width(self):
        text = ' '.join(['wort'] * 40)
        lines = wrap(text, self.metrics, 9, 100)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(self.metrics.text_width(line, 9), 100)

    def test_wrap_breaks_a_word_wider_than_the_box(self):
        lines = wrap('A' * 200, self.metrics, 9, 100)
        self.assertGreater(len(lines), 1)
        self.assertEqual(''.join(lines), 'A' * 200)

    def test_layout_of_a_single_line_field_keeps_one_line(self):
        lines, _size = layout(
            'erste Zeile\nzweite Zeile', 200, 13, '/Helv 9 Tf 0 g', self.metrics, False
        )
        self.assertEqual(lines, ['erste Zeile zweite Zeile'])

    def test_layout_shrinks_an_auto_sized_field(self):
        _lines, size = layout(
            ' '.join(['wort'] * 30), 200, 40, '/Helv 0 Tf 0 g', self.metrics, True
        )
        self.assertLess(size, 12)

    def test_build_stream_escapes_and_encodes(self):
        stream = build_stream(
            ['Grüße (x)\\y'], 9, 200, 40, '/Helv 9 Tf 0 g', 0, self.metrics, True
        )
        self.assertIn(b'/Tx BMC', stream)
        self.assertTrue(stream.rstrip().endswith(b'EMC'))
        # ü as a single byte octal escape, parentheses and backslash escaped.
        self.assertIn(br'Gr\374\337e \(x\)\\y', stream)

    def test_replace_marked_content_keeps_the_background(self):
        existing = b'.8 .8 1 rg\n0 0 10 10 re\nf\n/Tx BMC\nold\nEMC\n'
        result = replace_marked_content(existing, b'/Tx BMC\nnew\nEMC')
        self.assertTrue(result.startswith(b'.8 .8 1 rg\n0 0 10 10 re\nf\n'))
        self.assertIn(b'new', result)
        self.assertNotIn(b'old', result)

    def test_replace_marked_content_appends_when_absent(self):
        result = replace_marked_content(b'0 0 10 10 re\nf\n', b'/Tx BMC\nnew\nEMC')
        self.assertIn(b'0 0 10 10 re', result)
        self.assertTrue(result.rstrip().endswith(b'EMC'))
