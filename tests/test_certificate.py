import re

from reports.audit_certificate import pdf_from_jpeg


def test_pdf_structure():
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100 + b"\xff\xd9"
    pdf = pdf_from_jpeg(jpeg, 1600, 1130)
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    xref = int(re.search(rb"startxref\n(\d+)", pdf).group(1))
    assert pdf[xref:xref + 4] == b"xref"
    offsets = [int(x) for x in re.findall(rb"(\d{10}) 00000 n", pdf)]
    for i, off in enumerate(offsets, start=1):
        assert pdf[off:].startswith(f"{i} 0 obj".encode())
    assert jpeg in pdf
