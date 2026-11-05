"""Source upload is explicit and cannot overwrite existing inputs."""
from io import BytesIO
from openpyxl import Workbook
import pytest
from app.services.source_uploads import save_source


def test_csv_saved_and_duplicate_preserved(tmp_path):
    raw=b'code,note\nA,warranty\n'
    assert save_source(tmp_path,'data.csv',raw)['source']=='data.csv'
    with pytest.raises(ValueError,match='ton tai'): save_source(tmp_path,'data.csv',b'code\nB\n')
    assert (tmp_path/'data.csv').read_bytes()==raw


def test_xlsx_validated(tmp_path):
    book=Workbook();book.active.append(['Code']);book.active.append(['A']);stream=BytesIO();book.save(stream)
    save_source(tmp_path,'book.xlsx',stream.getvalue())
    assert (tmp_path/'book.xlsx').is_file()


@pytest.mark.parametrize('name,raw',[('../x.csv',b'a'),('~$x.xlsx',b'a'),('bad.xlsx',b'notzip'),('bad.exe',b'a')])
def test_invalid_source_no_write(tmp_path,name,raw):
    with pytest.raises(ValueError):save_source(tmp_path,name,raw)
    assert not list(tmp_path.iterdir())
