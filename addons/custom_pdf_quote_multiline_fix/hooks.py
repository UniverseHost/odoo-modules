import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Detect the multiline form fields of the PDFs that are already uploaded."""
    try:
        env['sale.pdf.form.field']._sync_multiline_flags()
    except Exception:  # never block the installation on an unreadable PDF
        _logger.warning("Could not detect the multiline form fields", exc_info=True)
