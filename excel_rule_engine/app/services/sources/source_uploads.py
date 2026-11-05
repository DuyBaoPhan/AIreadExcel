"""Explicit chatbot source upload; never overwrite existing inputs."""
from io import BytesIO
from pathlib import Path
import csv
import zipfile
from openpyxl import load_workbook


def save_source(input_dir,name,raw):
    root=Path(input_dir).resolve()
    if not isinstance(name,str) or not name or any(c in name for c in '/\\:') or name.startswith(('~$','.')):
        raise ValueError('Ten tep nguon khong hop le.')
    path=root/name
    if path.suffix.lower() not in {'.xlsx','.csv'}:
        raise ValueError('Chi ho tro XLSX/CSV cho nguon chatbot.')
    if not isinstance(raw,bytes) or not raw or len(raw)>40*1024*1024:
        raise ValueError('Tep rong hoac vuot 40 MB.')
    files=[p for p in root.iterdir() if p.suffix.lower() in {'.xlsx','.csv','.xls'} and not p.name.startswith('~$')]
    if len(files)>=20 or sum(p.stat().st_size for p in files)+len(raw)>40*1024*1024:
        raise ValueError('Vuot gioi han 20 tep / 40 MB nguon chatbot.')
    try:
        if path.suffix.lower()=='.xlsx':
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                if sum(i.file_size for i in archive.infolist())>200*1024*1024:
                    raise ValueError('Workbook giai nen vuot 200 MB.')
            book=load_workbook(BytesIO(raw),read_only=True)
            book.close()
        else:
            next(csv.reader(raw.decode('utf-8-sig').splitlines()))
    except Exception:
        raise ValueError('Tep Excel/CSV khong hop le.') from None
    try:
        with path.open('xb') as stream: stream.write(raw)
    except FileExistsError:
        raise ValueError('Ten tep da ton tai; khong ghi de nguon. Hay doi ten tep.') from None
    except OSError:
        raise ValueError('Khong the luu tep nguon.') from None
    return {'source':name,'bytes':len(raw)}
