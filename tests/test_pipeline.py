import io
import pathlib
import zipfile

from pipeline import clean
from pipeline.datasets import ALL
from pipeline.readers import read_table


def test_parse_number_handles_indian_grouping_and_junk():
    assert clean.parse_number("20,00,00,000") == 200000000
    assert clean.parse_number("1,51,09,500.00") == 15109500
    assert clean.parse_number("14,342,000+") == 14342000
    assert clean.parse_number("\\\\xc2\\\\xa020,000,000") == 20000000
    assert clean.parse_number("\u20b9 40") == 40
    for junk in ("N/A", "undisclosed", "Unknown", "nan", ""):
        assert clean.parse_number(junk) is None


def test_parse_date_messy_inputs():
    assert clean.parse_date("09/01/2020") == "2020-01-09"
    assert clean.parse_date("12/05.2015") == "2015-05-12"
    assert clean.parse_date("05/072018") == "2018-07-05"
    assert clean.parse_date("22/01//2015") == "2015-01-22"
    assert clean.parse_date("01/07/015") == "2015-07-01"
    assert clean.parse_date("20240117") == "2024-01-17"
    assert clean.parse_date("2024-10-08 15:17:28") == "2024-10-08"
    assert clean.parse_date("31/02/2020") is None


def test_fix_text_mojibake():
    assert clean.fix_text("Byju\\\\xe2\\\\x80\\\\x99s") == "Byju's"
    assert clean.fix_text("\\\\xc2\\\\xa0Gurgaon") == "Gurgaon"
    assert clean.fix_text("  N/A ") is None


def test_column_detection_on_original_layouts():
    for cls in ALL:
        ds = cls()
        head, rows = ds.placeholder()
        assert ds.score(head) > 0.5, cls.__name__
        recs = ds.records(head, rows[:5])
        assert all(r for r in recs)
    # foreign header spellings still map
    from pipeline.datasets import Funding
    m = Funding().map_columns(["Startup", "Funding Date", "City", "Amount (USD)"])
    assert {"startup", "date", "city", "amount"} <= set(m)


def _xlsx(rows):
    def cell(ref, v):
        return f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>'
    sheet = "".join(f'<row r="{i + 1}">' + "".join(cell(chr(65 + j) + str(i + 1), v) for j, v in enumerate(r)) + "</row>" for i, r in enumerate(rows))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{sheet}</sheetData></worksheet>')
    return buf.getvalue()


def test_xlsx_reader(tmp_path: pathlib.Path):
    p = tmp_path / "zepto.xlsx"
    p.write_bytes(_xlsx([["Category", "name", "mrp"], ["Dairy", "Milk", "2500"]]))
    head, rows = read_table(p)
    assert head == ["Category", "name", "mrp"] and rows == [["Dairy", "Milk", "2500"]]


def test_csv_reader_latin1(tmp_path: pathlib.Path):
    p = tmp_path / "x.csv"
    p.write_bytes("name,price\nCaf\xe9,10\n".encode("latin-1"))
    head, rows = read_table(p)
    assert rows[0][0] == "Caf\u00e9"


def test_build_is_deterministic(tmp_path):
    from pipeline.datasets import Catalog
    a, b = Catalog(), Catalog()
    ha, ra = a.placeholder()
    hb, rb = b.placeholder()
    assert ra == rb
    ta, tb = a.build(a.records(ha, ra)), b.build(b.records(hb, rb))
    assert ta[0].rows == tb[0].rows
