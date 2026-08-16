"""Stage A0: PDFs that carry no readable text layer.

A scanned paper parses to an empty document unless it is caught up front, so
the extractor refuses it with a specific reason instead of letting stages B–E
produce a confusing "0 sections, 0 references" result.

The fixtures are built with PyMuPDF so the test exercises real image blocks and
a real absence of text, not a mocked page dict.
"""
import pymupdf
import pytest

from app.parsing.pdf_extract import (MIN_DOC_CHARS, EncryptedPdfError,
                                     NoTextLayerError, PdfExtractionError,
                                     extract_document)
from app.parsing.pipeline import parse_pdf

PAGE = pymupdf.paper_rect("letter")


def _image_pixmap() -> pymupdf.Pixmap:
    """A plain raster block — stands in for a scanned page image."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 600, 800))
    pix.clear_with(220)
    return pix


def _write(path, pages) -> str:
    """pages: list of callables that draw onto a fresh page."""
    doc = pymupdf.open()
    for draw in pages:
        draw(doc.new_page(width=PAGE.width, height=PAGE.height))
    doc.save(str(path))
    doc.close()
    return str(path)


def _scanned_page(page):
    page.insert_image(pymupdf.Rect(40, 40, 570, 740), pixmap=_image_pixmap())


def _text_page(page):
    body = ("Deep networks are hard to train. Layer normalisation helps [1]. "
            "Residual connections help as well [2]. This paragraph exists so the "
            "page carries a realistic amount of extractable text for the A0 gate. ")
    page.insert_textbox(pymupdf.Rect(40, 40, 570, 740), body * 6, fontsize=10)


# --------------------------------------------------------------- refuse --

def test_image_only_pdf_is_refused_with_a_reason(tmp_path):
    path = _write(tmp_path / "scan.pdf", [_scanned_page, _scanned_page])

    with pytest.raises(NoTextLayerError) as exc:
        extract_document(path)

    err = exc.value
    assert err.n_pages == 2
    assert err.n_image_only == 2
    assert err.n_chars < MIN_DOC_CHARS
    msg = str(err)
    assert "no extractable text layer" in msg
    assert "ocrmypdf" in msg               # tells the user what to do next
    assert isinstance(err, PdfExtractionError)


def test_pipeline_propagates_rather_than_returning_an_empty_document(tmp_path):
    """The failure must reach the caller — not surface as a parsed paper with
    zero sections and zero references."""
    path = _write(tmp_path / "scan.pdf", [_scanned_page])
    with pytest.raises(NoTextLayerError):
        parse_pdf(path)


def test_blank_pdf_with_no_images_is_also_refused(tmp_path):
    path = _write(tmp_path / "blank.pdf", [lambda page: None])
    with pytest.raises(NoTextLayerError) as exc:
        extract_document(path)
    assert exc.value.n_image_only == 0     # nothing to blame on scanning
    assert "no extractable text layer" in str(exc.value)


# -------------------------------------------------------------- degrade --

def test_partially_scanned_pdf_parses_and_warns(tmp_path):
    """Text pages + one scanned page: parse what is there, report the gap."""
    path = _write(tmp_path / "mixed.pdf",
                  [_text_page, _scanned_page, _text_page])

    extracted = extract_document(path)

    assert extracted.lines                 # the text pages still came through
    hits = [w for w in extracted.warnings
            if "no text layer" in w.message]
    assert len(hits) == 1
    assert "1 page(s)" in hits[0].message
    assert "Page(s) 2" in (hits[0].detail or "")   # 1-based, names the page


def test_fully_readable_pdf_raises_no_text_layer_warning(tmp_path):
    """Regression guard: the A0 gate must stay silent on a normal paper."""
    path = _write(tmp_path / "clean.pdf", [_text_page, _text_page])

    extracted = extract_document(path)

    assert extracted.lines
    assert not [w for w in extracted.warnings if "no text layer" in w.message]


# ------------------------------------------------------------ encrypted --

def test_encrypted_pdf_reports_the_password_not_a_missing_text_layer(tmp_path):
    path = tmp_path / "locked.pdf"
    doc = pymupdf.open()
    _text_page(doc.new_page(width=PAGE.width, height=PAGE.height))
    doc.save(str(path), encryption=pymupdf.PDF_ENCRYPT_AES_256,
             owner_pw="owner", user_pw="user")
    doc.close()

    with pytest.raises(EncryptedPdfError) as exc:
        extract_document(str(path))
    assert "password-protected" in str(exc.value)
