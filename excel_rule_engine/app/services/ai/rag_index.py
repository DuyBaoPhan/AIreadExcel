"""Local hybrid retrieval over bounded project input snapshots.

Only immediate .xlsx/.csv files are read. No workbook content is sent to a
service, and no disk index or pickle is loaded. The default E5 model may be
downloaded by sentence-transformers on first use; inference remains local.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from dataclasses import dataclass, field
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import threading
import unicodedata
import zipfile

MODEL_NAME = "intfloat/multilingual-e5-large"
MAX_FILES = 20
MAX_TOTAL_BYTES = 40 * 1024 * 1024
MAX_EXPANDED_BYTES = 200 * 1024 * 1024
MAX_ROWS = 20_000
MAX_COLUMNS = 256
MAX_DOCUMENT_CHARS = 12_000
MAX_SEQUENCE_LENGTH = 512
MAX_CACHE_PROJECTS = 4
BATCH_SIZE = 32
RRF_K = 60
_CACHE = OrderedDict()
_LOCK = threading.RLock()
_MODEL = None
_MODEL_PATH = None
_EMBED_LOCK = threading.RLock()


class RetrievalError(ValueError):
    """An explicit retrieval/dependency/size error; never a partial index."""


@dataclass(frozen=True)
class Document:
    id: str
    text: str
    source: str
    sheet: str
    row: int


@dataclass
class RetrievalIndex:
    fingerprint: str
    documents: tuple[Document, ...]
    vector_index: object
    embedder: object
    terms: tuple[Counter, ...]
    document_frequency: Counter
    average_length: float
    project: str
    lock: object = field(default_factory=threading.RLock, repr=False)


def _dependencies():
    try:
        import numpy as np
        import faiss
    except ImportError as exc:
        raise RetrievalError("Hybrid retrieval requires numpy and faiss-cpu; install the project requirements.") from exc
    return np, faiss


def _model():
    global _MODEL, _MODEL_PATH
    with _LOCK:
        model_path = os.getenv("RAG_MODEL_PATH", MODEL_NAME).strip() or MODEL_NAME
        if _MODEL is None or _MODEL_PATH != model_path:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RetrievalError("Install sentence-transformers to use local multilingual-e5-large embeddings.") from exc
            try:
                _MODEL = SentenceTransformer(model_path, trust_remote_code=False)
                _MODEL.max_seq_length = MAX_SEQUENCE_LENGTH
                _MODEL_PATH = model_path
            except Exception as exc:
                raise RetrievalError("Cannot load multilingual-e5-large. Download/cache the model with network access, then retry locally.") from exc
        return _MODEL


def _configuration(embedder):
    # Object identity prevents two injected embedding spaces sharing an index.
    return {"version": 1, "model": os.getenv("RAG_MODEL_PATH", MODEL_NAME).strip() or MODEL_NAME, "max_sequence_length": MAX_SEQUENCE_LENGTH,
            "normalization": "l2", "prefixes": ["query: ", "passage: "],
            "embedder": "default" if embedder is None else f"{type(embedder).__module__}.{type(embedder).__qualname__}:{id(embedder)}"}


def _snapshot(input_dir, embedder):
    root = Path(input_dir).resolve(strict=True)
    if not root.is_dir():
        raise RetrievalError("Input must be a directory.")
    files = sorted((p for p in root.iterdir() if not p.name.startswith("~$")
                    and p.suffix.lower() in {".xlsx", ".csv", ".xls"}), key=lambda p: p.name)
    if len(files) > MAX_FILES:
        raise RetrievalError(f"Input exceeds {MAX_FILES} files; no partial index was created.")
    contents = []
    total = 0
    digest = hashlib.sha256(json.dumps(_configuration(embedder), sort_keys=True).encode())
    for path in files:
        if path.suffix.lower() == ".xls":
            raise RetrievalError("Legacy .xls is not indexed; convert it to .xlsx before retrieval.")
        if path.is_symlink() or not path.is_file() or path.resolve().parent != root:
            raise RetrievalError(f"Input file must be a regular file inside input: {path.name}")
        total += path.stat().st_size
        if total > MAX_TOTAL_BYTES:
            raise RetrievalError("Input exceeds the 40 MB total byte limit.")
        # Read at most the remaining allowance even if a source changes during reading.
        with path.open("rb") as stream:
            data = stream.read(MAX_TOTAL_BYTES - sum(len(b) for _, b in contents) + 1)
        if sum(len(b) for _, b in contents) + len(data) > MAX_TOTAL_BYTES:
            raise RetrievalError("Input exceeds the 40 MB total byte limit.")
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
        contents.append((path.name, data))
    return str(root), digest.hexdigest(), contents


def _documents(contents):
    from openpyxl import load_workbook
    documents = []
    rows_seen = 0
    expanded_total = 0

    def consume(source, sheet, rows):
        nonlocal rows_seen
        header = next(rows, ())
        if len(header) > MAX_COLUMNS:
            raise RetrievalError(f"Too many columns in {source}/{sheet} (limit {MAX_COLUMNS}).")
        columns = [str(v) if v is not None and str(v) else f"Column {i + 1}" for i, v in enumerate(header)]
        for row_number, values in enumerate(rows, 2):
            rows_seen += 1
            if rows_seen > MAX_ROWS:
                raise RetrievalError(f"Input exceeds {MAX_ROWS} data rows; no rows were silently omitted.")
            if len(values) > MAX_COLUMNS:
                raise RetrievalError(f"Too many columns in {source}/{sheet}, row {row_number}.")
            if not any(v is not None and str(v) != "" for v in values):
                continue
            # Positional labels preserve duplicate headers and values beyond a short CSV header.
            fields = [f"{columns[i] if i < len(columns) else f'Column {i + 1}'} [{i + 1}]: {'' if v is None else v}"
                      for i, v in enumerate(values)]
            text = f"Source: {source}; Sheet: {sheet}; Row: {row_number} | " + " | ".join(fields)
            if len(text) > MAX_DOCUMENT_CHARS:
                raise RetrievalError(f"Row too long in {source}/{sheet}, row {row_number}; shorten the row (no cell is truncated).")
            doc_id = hashlib.sha256(json.dumps([source, sheet, row_number], ensure_ascii=False).encode()).hexdigest()[:24]
            documents.append(Document(doc_id, text, source, sheet, row_number))

    for name, data in contents:
        try:
            if name.lower().endswith(".csv"):
                text = data.decode("utf-8-sig")
                try:
                    dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
                except csv.Error:
                    dialect = csv.excel
                consume(name, "CSV", iter(csv.reader(io.StringIO(text, newline=""), dialect)))
            else:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    expanded_total += sum(info.file_size for info in archive.infolist())
                    if expanded_total > MAX_EXPANDED_BYTES:
                        raise RetrievalError("Expanded XLSX data exceeds the 200 MB limit.")
                workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=False)
                try:
                    for sheet in workbook.worksheets:
                        # Ignore untrusted dimension hints, preserving actual physical row numbers.
                        sheet.reset_dimensions()
                        consume(name, sheet.title, iter(sheet.iter_rows(values_only=True)))
                finally:
                    workbook.close()
        except RetrievalError:
            raise
        except Exception as exc:
            raise RetrievalError(f"Cannot index {name}: {exc}") from exc
    return tuple(documents)


def _validate_lengths(embedder, texts):
    tokenizer = getattr(embedder, "tokenizer", None)
    limit = min(MAX_SEQUENCE_LENGTH, getattr(embedder, "max_seq_length", MAX_SEQUENCE_LENGTH))
    if tokenizer is not None:
        for start in range(0, len(texts), BATCH_SIZE):
            ids = tokenizer(texts[start:start + BATCH_SIZE], truncation=False, padding=False)["input_ids"]
            if any(len(tokens) > limit for tokens in ids):
                raise RetrievalError(f"A row/query exceeds the model's {limit}-token limit; shorten it. No text was truncated.")
    elif any(len(text.encode("utf-8")) > limit - 8 for text in texts):
        # Safe conservative bound for custom embedders without a tokenizer.
        raise RetrievalError("Row/query exceeds the conservative token-safe byte limit; provide a tokenizer or shorten it.")


def _encode(embedder, texts):
    np, _ = _dependencies()
    _validate_lengths(embedder, texts)
    batches = []
    for start in range(0, len(texts), BATCH_SIZE):
        with _EMBED_LOCK:
            result = embedder.encode(texts[start:start + BATCH_SIZE], batch_size=BATCH_SIZE,
                                     normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        array = np.asarray(result, dtype="float32")
        if array.ndim != 2 or len(array) != len(texts[start:start + BATCH_SIZE]) or not np.isfinite(array).all():
            raise RetrievalError("Embedder returned invalid vectors.")
        norms = np.linalg.norm(array, axis=1, keepdims=True)
        if (norms == 0).any():
            raise RetrievalError("Embedder returned zero vectors.")
        batches.append(array / norms)
    return np.ascontiguousarray(np.concatenate(batches), dtype="float32")


def _tokens(text):
    # Keep identifiers such as NV-001 intact, in addition to individual words.
    text = ''.join(c for c in unicodedata.normalize('NFD', text.casefold().replace('?', 'd'))
                   if not unicodedata.combining(c))
    return re.findall(r"[^\W_]+(?:[-_.][^\W_]+)*", text, re.UNICODE)


def _build(project, fingerprint, contents, embedder):
    _, faiss = _dependencies()
    docs = _documents(contents)
    model = embedder if embedder is not None else (_model() if docs else None)
    vectors = _encode(model, ["passage: " + doc.text for doc in docs]) if docs else None
    index = faiss.IndexFlatIP(vectors.shape[1] if docs else 1)
    if docs:
        index.add(vectors)
    terms = tuple(Counter(_tokens(doc.text)) for doc in docs)
    df = Counter(term for counts in terms for term in counts)
    avg = sum(sum(counts.values()) for counts in terms) / len(terms) if terms else 0
    return RetrievalIndex(fingerprint, docs, index, model, terms, df, avg, project)


def build_index(input_dir, embedder=None):
    """Build a fresh bounded snapshot, without reading/writing a disk cache."""
    project, fingerprint, contents = _snapshot(input_dir, embedder)
    return _build(project, fingerprint, contents, embedder)


def get_index(input_dir, embedder=None):
    """Return a current project-isolated index, rebuilding on any byte/name change."""
    with _LOCK:
        project, fingerprint, contents = _snapshot(input_dir, embedder)
        key = (project, json.dumps(_configuration(embedder), sort_keys=True))
        existing = _CACHE.get(key)
        if existing is not None and existing.fingerprint == fingerprint:
            _CACHE.move_to_end(key)
            return existing
        result = _build(project, fingerprint, contents, embedder)
        _CACHE[key] = result
        _CACHE.move_to_end(key)
        while len(_CACHE) > MAX_CACHE_PROJECTS:
            _CACHE.popitem(last=False)
        return result


def clear_cache():
    """Discard in-memory snapshots (the lazy model remains loaded)."""
    with _LOCK:
        _CACHE.clear()


def _lexical(index, query, count):
    scores = []
    for position, terms in enumerate(index.terms):
        score = 0.0
        length = sum(terms.values())
        for term in set(_tokens(query)):
            frequency = terms.get(term, 0)
            if frequency:
                df = index.document_frequency[term]
                idf = math.log(1 + (len(index.documents) - df + .5) / (df + .5))
                score += idf * frequency * 2.5 / (frequency + 1.5 * (.25 + .75 * length / index.average_length))
        if score > 0:
            scores.append((position, score))
    return [position for position, _ in sorted(scores, key=lambda item: (-item[1], item[0]))[:count]]


def query_index(index, query, top_k=8):
    """Fuse independent semantic and BM25 candidates with reciprocal rank fusion."""
    if not isinstance(query, str) or not query.strip():
        raise RetrievalError("Query must be nonempty text.")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 100:
        raise RetrievalError("top_k must be an integer between 1 and 100.")
    if len(query) > MAX_DOCUMENT_CHARS:
        raise RetrievalError("Query is too long.")
    n = len(index.documents)
    if not n:
        return {"hits": [], "fingerprint": index.fingerprint, "total_documents": 0, "truncated": False}
    candidates = min(n, max(32, top_k * 4))
    with index.lock:
        vector = _encode(index.embedder, ["query: " + query])
        _, positions = index.vector_index.search(vector, candidates)
    semantic = [int(p) for p in positions[0] if p >= 0]
    lexical = _lexical(index, query, candidates)
    scores = Counter()
    for ranking in (semantic, lexical):
        for rank, position in enumerate(ranking, 1):
            scores[position] += 1 / (RRF_K + rank)
    ordered = sorted(scores, key=lambda p: (-scores[p], index.documents[p].id))[:top_k]
    hits = [{"id": index.documents[p].id, "text": index.documents[p].text,
             "source": index.documents[p].source, "sheet": index.documents[p].sheet,
             "row": index.documents[p].row, "score": scores[p]} for p in ordered]
    return {"hits": hits, "fingerprint": index.fingerprint, "total_documents": n,
            "truncated": n > len(hits)}


def search(input_dir, query, top_k=8, embedder=None):
    """Search all supported exact files inside a project input directory locally."""
    return query_index(get_index(input_dir, embedder=embedder), query, top_k=top_k)

