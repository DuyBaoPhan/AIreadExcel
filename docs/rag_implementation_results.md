# Hybrid Excel RAG implementation

## Goal and architecture

Local intfloat/multilingual-e5-large sentence embeddings + FAISS dense retrieval + BM25 lexical search, combined with reciprocal rank fusion. Chat routing separates retrieval lookups from deterministic full-table calculations. Evidence-bound OpenAI responses contain only short cited claims, source/sheet/row provenance and an explicit retrieval-scope limitation. Queries and updates retain their deterministic engine/confirmation paths.

## Privacy and correctness boundaries

All input files belong to the current project input directory. Other-sheet records are searchable. Embedding runs locally; model download may require normal network access. Retrieved cell excerpts are transmitted to OpenAI for synthesis; metadata-only statements in older docs apply only to structured planning, not RAG answer generation. Protect sensitive cells and require authorization before deploying to untrusted users.

No top-k arithmetic: whole-table totals, ranking and exhaustive lists must execute on full relevant snapshots. Hybrid search improves recall but cannot guarantee zero missing facts. Citations are validated against retrieved document IDs, not a formal proof of entailment. Model semantic accuracy requires a separate live evaluation. Workbook instructions never grant execution or writes; update confirmation remains mandatory.

## Operations

Install root requirements. The default model is large and loads lazily; provide enough RAM/disk/time. Every lookup fingerprints source bytes and rebuilds changed project indices. The in-memory cache does not deserialize pickle. Deployment on low-RAM Streamlit Cloud may need a separate backend; no silent model substitution is allowed.

See README for activation and practical limitations. Test results will be recorded after verification.

## Reproduction and model validation

```powershell
.\excel_rule_engine\venv\Scripts\python.exe -m pip install -r requirements.txt
.\excel_rule_engine\venv\Scripts\python.exe -m pytest -q
# Optional real multilingual-e5-large + FAISS evaluation (downloads model; no OpenAI call)
.\excel_rule_engine\venv\Scripts\python.exe .\excel_rule_engine\tests\rag_live_smoke.py
```

The normal unit tests use deterministic injected embeddings with genuine FAISS, and mocked OpenAI synthesis. The optional real-model smoke evaluates cross-language/identifier recall at 2 on three synthetic records, not production semantic accuracy. BM25 normalizes Vietnamese accents and preserves complete identifiers. Source and sheet names are included in both lexical and semantic document text.

No source rows are silently truncated: oversized records/token counts cause an explicit error. Top-k result limiting is disclosed. RAG currently indexes every sheet with first-row header assumption; legacy XLS must be converted. An explicit source-upload UI now adds XLSX/CSV to project inputs without overwrite. RAG/index has bounded CPU/memory inputs but multilingual-e5-large itself requires substantial memory. Current index is in-memory; restart rebuilds it.

## Regression findings

The first full regression run found two navigation failures after adding the source uploader (uploader rendered in unrelated workspaces). Fixed by making upload opt-in and Chatbot-only. Targeted workspace rerun: 3 passed. Latest focused retrieval/answer/chat/upload run: 40 passed using real FAISS and injected deterministic embeddings. Full final regression and dependency installation outcomes are pending.

## Verified local results

- Full regression after navigation fix: **1,141 tests passed; 73 subtests passed**. Two existing FastAPI startup deprecation warnings remain.
- Final retrieval module tests after model-configuration invalidation coverage: **21 passed** (real FAISS, deterministic injected embeddings).
- Final navigation tests: **4 passed**. Final focused retrieval/answer/chat/upload suite: **40 passed** before the last additional edge-case tests.
- Compilation succeeded. A trailing-whitespace issue found by the combined command was removed; subsequent `git diff --check` succeeded.
- Real multilingual-e5-large inference and OpenAI answer quality are not yet verified. SentenceTransformers/PyTorch installation is still running; do not interpret injected-embedding tests as real semantic retrieval evaluation.

## Actual model smoke result

Dependency installation completed successfully. Ran `rag_live_smoke.py` with the real **intfloat/multilingual-e5-large** model and genuine FAISS on three synthetic records (no personal data, no OpenAI API call): **recall@2 = 3/3; top-1 = 2/3**. The Vietnamese unaccented warranty question retrieved the correct printer policy second, behind an unrelated warehouse row. This small smoke demonstrates working inference/integration, not production relevance or a completeness guarantee. No thresholds were tuned on this fixture and no alternate model was substituted.

Non-failing Hugging Face warnings reported anonymous download rate limits and Windows cache symlink limitations (extra disk use). No administrator elevation or configuration bypass was performed. Full regression is being rerun after dependency installation and final additional test cases.

## Final acceptance

After installing the actual retrieval dependencies and all final changes: **1,143 tests passed; 73 subtests passed**. Compilation and git diff --check succeeded. Two pre-existing FastAPI deprecation warnings and non-failing Git line-ending notices remain. Real E5 + FAISS smoke: recall@2 3/3, top-1 2/3 on synthetic data. OpenAI synthesis tests remain mocked; no live end-to-end answer-quality evaluation or Cloud deployment was performed.
