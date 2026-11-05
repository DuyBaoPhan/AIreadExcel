"""Hybrid retrieval tests: deterministic local embeddings, never model downloads."""
import csv
from pathlib import Path

import numpy as np
from openpyxl import Workbook
import pytest

from app.services import rag_index as rag


class FakeEmbedder:
    max_seq_length = 512

    def __init__(self):
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.extend(texts)
        vectors = []
        for text in texts:
            text = text.casefold()
            # English/Vietnamese synonyms intentionally share a semantic direction.
            vectors.append([1., 0.1] if any(t in text for t in ('salary', 'thu nhập', 'lương')) else [0.1, 1.])
        return np.asarray(vectors, dtype='float32')


@pytest.fixture(autouse=True)
def clean_cache():
    rag.clear_cache()
    yield
    rag.clear_cache()


@pytest.fixture
def embedder():
    pytest.importorskip('faiss')
    return FakeEmbedder()


def csv_file(root, name='data.csv', rows=None):
    with (root / name).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerows(rows or [['Code', 'Description'], ['NV-001', 'salary'], ['NV-999', 'inventory']])


def test_lexical_exact_identifier(tmp_path, embedder):
    csv_file(tmp_path)
    index = rag.get_index(tmp_path, embedder)
    assert rag._lexical(index, 'NV-999', 5) == [1]
    result = rag.query_index(index, 'NV-999')
    assert result['hits'][0]['row'] == 3
    assert result['hits'][0]['source'] == 'data.csv'
    assert result['total_documents'] == 2
    assert result['truncated'] is False
    assert all(t.startswith(('passage: ', 'query: ')) for t in embedder.calls)


def test_semantic_multilingual_fake_vectors(tmp_path, embedder):
    csv_file(tmp_path)
    result = rag.search(tmp_path, 'thu nhập', top_k=1, embedder=embedder)
    assert result['hits'][0]['row'] == 2
    assert result['truncated'] is True
    index = rag.get_index(tmp_path, embedder)
    reconstructed = index.vector_index.reconstruct_n(0, 2)
    np.testing.assert_allclose(np.linalg.norm(reconstructed, axis=1), 1)
    assert type(index.vector_index).__name__ == 'IndexFlatIP'


def test_fusion_retains_both_candidate_branches(tmp_path, embedder, monkeypatch):
    csv_file(tmp_path)
    index = rag.get_index(tmp_path, embedder)

    class SemanticOnly:
        def search(self, vectors, count):
            return np.array([[1.]]), np.array([[0]])

    index.vector_index = SemanticOnly()
    monkeypatch.setattr(rag, '_lexical', lambda *args: [1])
    result = rag.query_index(index, 'x')
    assert {h['row'] for h in result['hits']} == {2, 3}
    assert all(h['score'] == 1 / 61 for h in result['hits'])


def test_cache_invalidation_for_bytes_add_delete(tmp_path, embedder):
    csv_file(tmp_path)
    first = rag.get_index(tmp_path, embedder)
    assert rag.get_index(tmp_path, embedder) is first
    # Same-length replacement still invalidates even without relying on mtime.
    path = tmp_path / 'data.csv'
    path.write_text(path.read_text().replace('NV-001', 'NV-002'), encoding='utf-8')
    second = rag.get_index(tmp_path, embedder)
    assert second.fingerprint != first.fingerprint
    assert second.documents[0].id == first.documents[0].id
    csv_file(tmp_path, 'more.csv')
    third = rag.get_index(tmp_path, embedder)
    assert len(third.documents) == 4
    (tmp_path / 'more.csv').unlink()
    assert rag.get_index(tmp_path, embedder).fingerprint == second.fingerprint


def test_project_and_embedding_space_isolation(tmp_path, embedder):
    one, two = tmp_path / 'one', tmp_path / 'two'
    one.mkdir()
    two.mkdir()
    csv_file(one)
    csv_file(two)
    first = rag.get_index(one, embedder)
    second = rag.get_index(two, embedder)
    assert first is not second
    assert first.project != second.project
    assert rag.get_index(one, FakeEmbedder()) is not first


def test_all_sheets_actual_rows_duplicates_and_lock_file(tmp_path, embedder):
    workbook = Workbook()
    one = workbook.active
    one.title = 'Nhân sự'
    one.append(['Code', 'Code'])
    one.append(['A', 'B'])
    one.append([None, None])
    one.append(['C', 'D'])
    two = workbook.create_sheet('Kho')
    two.append(['Code'])
    two.append(['E'])
    workbook.save(tmp_path / 'book.xlsx')
    (tmp_path / '~$book.xlsx').write_bytes(b'not an xlsx')
    (tmp_path / 'ignored.txt').write_text('ignored')
    nested = tmp_path / 'nested'
    nested.mkdir()
    csv_file(nested)
    docs = rag.get_index(tmp_path, embedder).documents
    assert [(d.sheet, d.row) for d in docs] == [('Nhân sự', 2), ('Nhân sự', 4), ('Kho', 2)]
    assert 'Code [1]: A' in docs[0].text and 'Code [2]: B' in docs[0].text
    assert all(d.source == 'book.xlsx' for d in docs)


@pytest.mark.parametrize('limit, value, message', [
    ('MAX_FILES', 0, 'files'), ('MAX_TOTAL_BYTES', 1, 'byte'),
    ('MAX_ROWS', 1, 'rows'), ('MAX_DOCUMENT_CHARS', 2, 'Row too long'),
    ('MAX_COLUMNS', 1, 'columns')])
def test_explicit_size_failures(tmp_path, embedder, monkeypatch, limit, value, message):
    csv_file(tmp_path)
    monkeypatch.setattr(rag, limit, value)
    with pytest.raises(rag.RetrievalError, match=message):
        rag.get_index(tmp_path, embedder)
    assert not rag._CACHE


def test_expanded_zip_limit(tmp_path, embedder, monkeypatch):
    workbook = Workbook()
    workbook.active.append(['a'])
    workbook.active.append(['b'])
    workbook.save(tmp_path / 'book.xlsx')
    monkeypatch.setattr(rag, 'MAX_EXPANDED_BYTES', 1)
    with pytest.raises(rag.RetrievalError, match='Expanded XLSX'):
        rag.get_index(tmp_path, embedder)


def test_long_cell_rejected_not_silently_truncated(tmp_path, embedder):
    csv_file(tmp_path, rows=[['value'], ['x' * 600]])
    with pytest.raises(rag.RetrievalError, match='token-safe'):
        rag.build_index(tmp_path, embedder)


def test_real_tokenizer_bound_precedes_encode(tmp_path, embedder):
    csv_file(tmp_path)
    embedder.tokenizer = lambda texts, **kw: {'input_ids': [[1] * 513 for _ in texts]}
    with pytest.raises(rag.RetrievalError, match='512-token'):
        rag.build_index(tmp_path, embedder)
    assert not embedder.calls


def test_empty_and_invalid_queries(tmp_path, embedder):
    assert rag.search(tmp_path, 'salary', embedder=embedder)['hits'] == []
    index = rag.get_index(tmp_path, embedder)
    for query, top_k in [('', 1), ('x', 0), ('x', 101), ('x', True)]:
        with pytest.raises(rag.RetrievalError):
            rag.query_index(index, query, top_k)


def test_cache_is_bounded(tmp_path, embedder, monkeypatch):
    monkeypatch.setattr(rag, 'MAX_CACHE_PROJECTS', 2)
    for i in range(3):
        folder = tmp_path / str(i)
        folder.mkdir()
        csv_file(folder)
        rag.get_index(folder, embedder)
    assert len(rag._CACHE) == 2


def test_semicolon_csv_preserves_fields(tmp_path,embedder):
    (tmp_path/'semi.csv').write_text('code;note\nA;salary\n',encoding='utf-8')
    result=rag.search(tmp_path,'A',embedder=embedder)
    assert 'code [1]: A' in result['hits'][0]['text']
    assert 'note [2]: salary' in result['hits'][0]['text']


def test_legacy_xls_is_explicit_error(tmp_path,embedder):
    (tmp_path/'legacy.xls').write_bytes(b'not supported')
    with pytest.raises(rag.RetrievalError,match='Legacy'):
        rag.search(tmp_path,'x',embedder=embedder)


def test_bm25_vietnamese_accents_normalized(tmp_path,embedder):
    csv_file(tmp_path,rows=[['code','note'],['A','Bảo hành thiết bị'],['B','Kho hàng']])
    index=rag.get_index(tmp_path,embedder)
    assert rag._lexical(index,'bao hanh',5)==[0]


def test_source_sheet_names_are_searchable(tmp_path,embedder):
    book=Workbook();book.active.title='WarrantyPolicy';book.active.append(['code']);book.active.append(['A'])
    book.save(tmp_path/'Printer.xlsx')
    index=rag.get_index(tmp_path,embedder)
    assert rag._lexical(index,'Printer.xlsx WarrantyPolicy',5)==[0]


def test_model_path_changes_index_fingerprint(tmp_path,embedder,monkeypatch):
    csv_file(tmp_path)
    first=rag.get_index(tmp_path,embedder)
    monkeypatch.setenv('RAG_MODEL_PATH','local-e5-copy')
    second=rag.get_index(tmp_path,embedder)
    assert first.fingerprint!=second.fingerprint
