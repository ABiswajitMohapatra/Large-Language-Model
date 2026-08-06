"""
rag_store.py
============
Production-grade retrieval layer for USER-UPLOADED documents only.

Why a separate module instead of editing engine.py's existing `index`/
`build_index`/`retrieve` functions: those already serve the folder-based
knowledge base on every /chat call and must keep working byte-for-byte the
same (zero risk, zero latency change). This module is purely additive and
is only ever touched when `uploaded_docs` is non-empty.

Design:
- FAISS (IndexIDMap2 over IndexFlatIP, cosine via L2-normalized vectors) is
  the primary vector store -> fast ANN search, scales comfortably to
  300-500 page PDFs (tens of thousands of chunks).
- BM25 (rank_bm25) runs alongside for lexical/keyword recall (hybrid
  search), fused with embedding results via Reciprocal Rank Fusion (RRF).
- Everything is persisted to disk (./rag_index/) so embeddings are never
  recomputed on server restart - only newly uploaded/changed files get
  (re)indexed, tracked via a per-file content hash in manifest.json.
- Indexing runs in a background thread so /upload returns immediately;
  progress is queryable via get_progress().
- Chunks carry filename + page number + chunk id metadata for citations.
- Near-duplicate chunks (e.g. repeated headers/footers) are skipped at
  chunk time via a normalized-text hash set, per document.
"""

import concurrent.futures
import hashlib
import json
import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

import engine  # reuse existing embedder, chunker constants, file loaders

# ---------------------------------------------------------------------------
# Persistence paths
# ---------------------------------------------------------------------------
INDEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_index")
FAISS_PATH = os.path.join(INDEX_DIR, "faiss.index")
META_PATH = os.path.join(INDEX_DIR, "metadata.json")
MANIFEST_PATH = os.path.join(INDEX_DIR, "manifest.json")

os.makedirs(INDEX_DIR, exist_ok=True)

EMBED_DIM = engine.EMBED_DIM
CHUNK_SIZE = engine.CHUNK_SIZE
CHUNK_OVERLAP = engine.CHUNK_OVERLAP
EMBED_BATCH_SIZE = 64  # bounds peak memory when indexing large documents

# Relevance floor for hybrid_search: candidates below this are dropped
# BEFORE RRF fusion (rather than always returning top_k regardless of how
# weak the match is), so genuinely irrelevant chunks never reach the LLM.
# Embedding vectors are L2-normalized and FAISS is IndexFlatIP, so this is
# a plain cosine-similarity threshold (0.0-1.0 scale). BM25 has no fixed
# scale, so its filter is simply "score > 0" (zero = no lexical overlap
# with the query at all).
MIN_EMBED_SIMILARITY = 0.35

_lock = threading.Lock()

# Bounded worker pool for background indexing (extraction + embedding).
# Replaces the previous unbounded `threading.Thread(...).start()` per
# upload - under many simultaneous uploads that could spawn dozens of
# concurrent CPU-heavy embedding threads at once and starve the machine;
# a small fixed pool queues extra jobs instead, which keeps the server
# responsive under load while still processing every upload. Purely an
# internal scheduling change - index_document_background()'s signature,
# return value (None / fire-and-forget), and get_progress() polling
# contract are all unchanged.
_index_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="rag-index")

# In-memory mirrors of the on-disk index, loaded once at import time.
_index = None                # faiss.IndexIDMap2
_metadata = {}                # {str(chunk_id): {filename, page, text, hash}}
_manifest = {}                # {filename: {"hash":..., "num_chunks":..., "status":...}}
_next_id = 0
_bm25 = None                  # rebuilt lazily whenever metadata changes
_bm25_ids = []                # chunk ids in the order fed to BM25

_progress = {}                # {filename: {"status": "queued|indexing|done|error", "percent": int, "message": str}}


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------
def _load():
    global _index, _metadata, _manifest, _next_id
    if os.path.exists(FAISS_PATH) and os.path.exists(META_PATH):
        try:
            _index = faiss.read_index(FAISS_PATH)
            with open(META_PATH, "r", encoding="utf-8") as f:
                _metadata = json.load(f)
            _next_id = (max((int(k) for k in _metadata), default=-1)) + 1
        except Exception as e:
            print(f"[RAG-STORE] Failed to load existing index, starting fresh: {e}")
            _index = None
            _metadata = {}
    if _index is None:
        _index = faiss.IndexIDMap2(faiss.IndexFlatIP(EMBED_DIM))
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                _manifest = json.load(f)
        except Exception:
            _manifest = {}


def _save():
    faiss.write_index(_index, FAISS_PATH)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(_metadata, f)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(_manifest, f)


_load()


def _rebuild_bm25():
    """Lazily rebuilt whenever metadata changes. Cheap relative to
    embedding, so simplest-correct approach rather than incremental."""
    global _bm25, _bm25_ids
    if not _metadata:
        _bm25, _bm25_ids = None, []
        return
    _bm25_ids = list(_metadata.keys())
    tokenized = [_metadata[cid]["text"].lower().split() for cid in _bm25_ids]
    _bm25 = BM25Okapi(tokenized)


_rebuild_bm25()
print(f"[RAG-STORE] Startup: {_index.ntotal} vector(s), {len(_metadata)} chunk(s) "
      f"across {len(_manifest)} file(s): {list(_manifest.keys())}")


# ---------------------------------------------------------------------------
# Hashing / dedup helpers
# ---------------------------------------------------------------------------
def _file_hash(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def _norm_text_hash(text: str) -> str:
    return hashlib.md5(" ".join(text.lower().split()).encode("utf-8")).hexdigest()


def _chunk_pages(pages, filename):
    """Chunk (page_num, text) pairs with overlap, tagging each chunk with
    its page number, and drop near-duplicate chunks (repeated boilerplate
    like headers/footers) within this document."""
    seen_hashes = set()
    chunks = []
    for page_num, text in pages:
        for raw_chunk in engine.chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP):
            h = _norm_text_hash(raw_chunk)
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
            chunks.append({"filename": filename, "page": page_num, "text": raw_chunk})
    return chunks


# ---------------------------------------------------------------------------
# Hard timeouts for indexing stages
# ---------------------------------------------------------------------------
# Without these, a stuck call (embedding-model download hanging on a
# slow/blocked network on first use, or OCR looping on a malformed/huge
# scanned PDF) never raises an exception - it just blocks the worker
# thread indefinitely, which is what left documents parked at "indexing"
# forever with no error surfaced anywhere. Every call to these two stages
# now runs through _call_with_timeout() so a hang becomes a caught,
# logged TimeoutError -> status "error" -within a bounded time, instead
# of an invisible, permanent hang.
EXTRACTION_TIMEOUT_SECONDS = 180     # generous for large/scanned+OCR PDFs
EMBED_BATCH_TIMEOUT_SECONDS = 90     # per embedding batch (incl. first-use model load)


def _call_with_timeout(fn, timeout_seconds, *args, **kwargs):
    """
    Runs fn(*args, **kwargs) with a hard wall-clock deadline. Raises
    concurrent.futures.TimeoutError (a subclass of Exception, so existing
    `except Exception` blocks around extraction/embedding already catch
    it) if the deadline is exceeded. Python can't force-kill a thread, so
    a genuinely hung call keeps running in the background after this
    returns - but the document being indexed is immediately marked
    "error" instead of the caller (and its progress status) blocking
    forever.
    """
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout_seconds)
    finally:
        ex.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------
def get_progress(filename: str | None = None):
    if filename:
        return _progress.get(filename, {"status": "not_indexed", "percent": 0})
    return dict(_progress)


def _set_progress(filename, status, percent, message=""):
    _progress[filename] = {"status": status, "percent": percent, "message": message}


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------
def remove_document(filename: str):
    """Removes all chunks/vectors belonging to a file (used on delete and
    before re-indexing)."""
    global _metadata
    with _lock:
        ids_to_remove = [int(cid) for cid, m in _metadata.items() if m["filename"] == filename]
        if ids_to_remove:
            _index.remove_ids(np.array(ids_to_remove, dtype=np.int64))
            _metadata = {cid: m for cid, m in _metadata.items() if int(cid) not in ids_to_remove}
        _manifest.pop(filename, None)
        _save()
        _rebuild_bm25()
    _progress.pop(filename, None)


def index_document(filename: str, raw_bytes: bytes):
    """
    Synchronous indexing of one file: extract page-aware text, chunk,
    batch-embed, and add to FAISS + persist. Skips re-embedding if the
    file's content hash hasn't changed since last time (handles server
    restarts and duplicate uploads cheaply).
    """
    global _next_id
    file_hash = _file_hash(raw_bytes)
    if _manifest.get(filename, {}).get("hash") == file_hash:
        print(f"[RAG-STORE] '{filename}' unchanged (hash match) - skipping re-embedding. "
              f"{_manifest[filename].get('num_chunks', 0)} chunks already indexed.")
        _set_progress(filename, "done", 100, "Already indexed (unchanged).")
        return

    print(f"[RAG-STORE] Indexing '{filename}' ({len(raw_bytes)} bytes)...")
    _set_progress(filename, "indexing", 5, "Extracting text...")
    extract_start = time.monotonic()
    try:
        pages = _call_with_timeout(engine.load_file_pages, EXTRACTION_TIMEOUT_SECONDS, raw_bytes, filename)
    except concurrent.futures.TimeoutError:
        print(f"[RAG-STORE] '{filename}' extraction TIMED OUT after "
              f"{EXTRACTION_TIMEOUT_SECONDS}s (stuck extraction/OCR call) - marking failed.")
        _set_progress(filename, "error", 0,
                      f"Extraction timed out after {EXTRACTION_TIMEOUT_SECONDS}s.")
        return
    except engine.UnsupportedFileError as e:
        print(f"[RAG-STORE] '{filename}' extraction unsupported: {e}")
        _set_progress(filename, "error", 0, str(e))
        return
    except Exception as e:
        print(f"[RAG-STORE] '{filename}' extraction FAILED: {e}\n{traceback.format_exc()}")
        _set_progress(filename, "error", 0, f"Extraction failed: {e}")
        return
    print(f"[RAG-STORE] '{filename}': extraction took {time.monotonic() - extract_start:.1f}s.")

    print(f"[RAG-STORE] '{filename}': extracted {len(pages)} page(s) total "
          f"(pages with no extractable text are dropped upstream).")
    if pages:
        page_nums = [p for p, _ in pages if p is not None]
        if page_nums:
            print(f"[RAG-STORE] '{filename}': page numbers range {min(page_nums)}-{max(page_nums)}.")

    # Remove any previous version of this file first (re-index case).
    remove_document(filename)

    chunks = _chunk_pages(pages, filename)
    if not chunks:
        print(f"[RAG-STORE] '{filename}': 0 chunks produced (no extractable text) - aborting index.")
        _set_progress(filename, "error", 0, "No extractable text found.")
        return

    chunks_missing_page = sum(1 for c in chunks if c["page"] is None)
    print(f"[RAG-STORE] '{filename}': {len(chunks)} chunk(s) created "
          f"({len(chunks) - chunks_missing_page} with page numbers, {chunks_missing_page} without).")

    _set_progress(filename, "indexing", 20, f"Embedding {len(chunks)} chunks...")
    texts = [c["text"] for c in chunks]
    vectors = np.zeros((len(texts), EMBED_DIM), dtype=np.float32)
    embed_start = time.monotonic()
    start = 0
    try:
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start:start + EMBED_BATCH_SIZE]
            emb = _call_with_timeout(engine.embed_texts, EMBED_BATCH_TIMEOUT_SECONDS, batch).astype(np.float32)
            # L2-normalize so FAISS inner product == cosine similarity.
            norms = np.linalg.norm(emb, axis=1, keepdims=True)
            norms[norms == 0] = 1e-8
            vectors[start:start + len(batch)] = emb / norms
            done = start + len(batch)
            pct = 20 + int(70 * done / len(texts))
            print(f"[RAG-STORE] '{filename}': embedded {done}/{len(texts)} chunks ({pct}%).")
            _set_progress(filename, "indexing", pct, f"Embedding {done}/{len(texts)} chunks...")
    except concurrent.futures.TimeoutError:
        print(f"[RAG-STORE] '{filename}': embedding TIMED OUT after "
              f"{EMBED_BATCH_TIMEOUT_SECONDS}s on batch starting at chunk {start} "
              f"(stuck embedding call, e.g. model download hanging) - marking failed.")
        _set_progress(filename, "error", 0,
                      f"Embedding timed out after {EMBED_BATCH_TIMEOUT_SECONDS}s on batch starting {start}.")
        return
    except Exception as e:
        # Previously this exception would only be caught by the background
        # wrapper's generic try/except with no detail printed anywhere,
        # so a mid-document embedding failure looked identical to "0
        # chunks indexed" with nothing in the server logs to explain why.
        print(f"[RAG-STORE] '{filename}': embedding FAILED at chunk batch starting {start}: "
              f"{e}\n{traceback.format_exc()}")
        _set_progress(filename, "error", 0, f"Embedding failed: {e}")
        return
    print(f"[RAG-STORE] '{filename}': embedding of {len(texts)} chunks took "
          f"{time.monotonic() - embed_start:.1f}s.")

    _set_progress(filename, "indexing", 92, "Saving to FAISS/BM25 index...")
    try:
        with _lock:
            ids = np.arange(_next_id, _next_id + len(chunks), dtype=np.int64)
            _next_id += len(chunks)
            _index.add_with_ids(vectors, ids)
            for cid, c in zip(ids, chunks):
                _metadata[str(int(cid))] = c
            _manifest[filename] = {
                "hash": file_hash,
                "num_chunks": len(chunks),
            }
            _save()
            _rebuild_bm25()
    except Exception as e:
        print(f"[RAG-STORE] '{filename}': FAISS/BM25 save FAILED: {e}\n{traceback.format_exc()}")
        _set_progress(filename, "error", 0, f"Failed to save index: {e}")
        return

    print(f"[RAG-STORE] '{filename}': FAISS save completed. {len(chunks)} vectors added "
          f"(index.ntotal={_index.ntotal} total across all files). Saved to {FAISS_PATH}.")
    _set_progress(filename, "done", 100, f"Indexed {len(chunks)} chunks.")


def index_document_background(filename: str, raw_bytes: bytes):
    """Fire-and-forget background indexing so /upload doesn't block on
    embedding large documents. Progress is pollable via get_progress().
    Runs on a small bounded worker pool (not an unbounded thread-per-call)
    so many simultaneous uploads queue safely instead of spawning unlimited
    concurrent CPU-heavy embedding threads."""
    _set_progress(filename, "queued", 0, "Queued for indexing.")

    def _run():
        try:
            index_document(filename, raw_bytes)
        except Exception as e:
            # Defense-in-depth: index_document() now handles/logs every
            # known failure point (extraction, embedding, FAISS save)
            # internally with its own status update, so reaching here
            # means something truly unanticipated happened. Still make
            # sure it's fully logged and status is set to "error" rather
            # than left parked at "queued"/"indexing".
            print(f"[RAG-STORE] '{filename}': indexing FAILED with an unhandled "
                  f"error: {e}\n{traceback.format_exc()}")
            _set_progress(filename, "error", 0, f"Indexing failed: {e}")

    _index_executor.submit(_run)


def clear_all():
    global _index, _metadata, _manifest, _next_id, _bm25, _bm25_ids
    with _lock:
        _index = faiss.IndexIDMap2(faiss.IndexFlatIP(EMBED_DIM))
        _metadata = {}
        _manifest = {}
        _next_id = 0
        _bm25, _bm25_ids = None, []
        _save()
    _progress.clear()


def list_indexed():
    return dict(_manifest)


# ---------------------------------------------------------------------------
# Hybrid retrieval
# ---------------------------------------------------------------------------
def _rrf_fuse(rank_lists, k=60):
    """Reciprocal Rank Fusion: combines multiple ranked id lists into one
    score per id without needing comparable raw scores across BM25 and
    cosine similarity - the standard, simple way to do hybrid search."""
    scores = {}
    for ranked_ids in rank_lists:
        for rank, cid in enumerate(ranked_ids):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return scores


def hybrid_search(filenames, query: str, top_k: int = 5):
    """
    Returns up to top_k chunks most relevant to `query`, restricted to the
    given filenames, fusing FAISS embedding search with BM25 keyword
    search, then deduplicating near-identical results.

    Output: list of dicts {text, filename, page, score}, best first.
    """
    if not query.strip() or _index.ntotal == 0 or not _metadata:
        print(f"[RAG-STORE] hybrid_search('{query[:60]}'): index empty "
              f"(ntotal={_index.ntotal}, metadata={len(_metadata)}) - nothing to search.")
        return []

    allowed = set(filenames)
    files_available = {m["filename"] for m in _metadata.values()}
    missing = allowed - files_available
    if missing:
        # This is the exact symptom of "asked about a file that isn't
        # actually in the index yet" - e.g. background indexing hasn't
        # finished, or it errored out silently. Surfacing it here means
        # it shows up in server logs instead of just as a vague "I don't
        # have that" from the LLM with no trace of why.
        print(f"[RAG-STORE] WARNING: hybrid_search requested file(s) {missing} "
              f"not present in the index. Indexed files: {sorted(files_available)}. "
              f"Progress: {_progress.get(next(iter(missing)))}")

    # Over-fetch since FAISS has no native metadata filter here; we filter
    # by filename after the ANN search. IMPORTANT: this search always runs
    # against the FULL index (_index.search covers all _index.ntotal
    # vectors, not just recently-added ones - FAISS has no concept of
    # "recent"), so results are never limited to only the newest upload.
    #
    # THREAD SAFETY: _index.search() and reading _bm25/_bm25_ids are done
    # under the same _lock used by index_document()'s writes. FAISS index
    # objects aren't safe for concurrent read-while-mutate, and _bm25 /
    # _bm25_ids are two separate globals swapped together on rebuild - 
    # reading them one at a time without a lock could observe a stale
    # _bm25 paired with a just-updated _bm25_ids (or vice versa) if a
    # concurrent upload's _rebuild_bm25() lands in between. embed_texts()
    # (CPU-bound but touches no shared index state) stays outside the lock
    # so it doesn't serialize concurrent searches against each other.
    q_vec = engine.embed_texts([query]).astype(np.float32)
    q_vec = q_vec / max(np.linalg.norm(q_vec), 1e-8)

    with _lock:
        fetch_k = min(max(top_k * 10, 50), _index.ntotal)
        ann_scores, ann_ids = _index.search(q_vec, fetch_k)
        emb_ranked = [
            str(i) for i, score in zip(ann_ids[0], ann_scores[0])
            if i != -1
            and score >= MIN_EMBED_SIMILARITY
            and _metadata.get(str(i), {}).get("filename") in allowed
        ]

        # --- BM25 search (snapshot taken inside the same lock) ---
        bm25_ranked = []
        bm25, bm25_ids = _bm25, _bm25_ids
    if bm25 is not None:
        scores = bm25.get_scores(query.lower().split())
        order = np.argsort(scores)[::-1]
        for idx in order:
            if scores[idx] <= 0:
                # Scores are sorted descending, so once we hit zero (no
                # lexical term overlap with the query at all) everything
                # after this is equally irrelevant - stop here.
                break
            cid = bm25_ids[idx]
            if _metadata.get(cid, {}).get("filename") in allowed:
                bm25_ranked.append(cid)
            if len(bm25_ranked) >= fetch_k:
                break

    print(f"[RAG-STORE] hybrid_search('{query[:60]}'): searched full index "
          f"(ntotal={_index.ntotal}, fetch_k={fetch_k}) restricted to {sorted(allowed)}, "
          f"min_embed_sim={MIN_EMBED_SIMILARITY} -> "
          f"{len(emb_ranked)} embedding hit(s), {len(bm25_ranked)} BM25 hit(s) after relevance + filename filter.")

    fused = _rrf_fuse([emb_ranked, bm25_ranked])
    ordered_ids = sorted(fused.keys(), key=lambda cid: fused[cid], reverse=True)

    # --- dedupe near-identical chunks among the fused results ---
    results = []
    seen_hashes = set()
    for cid in ordered_ids:
        meta = _metadata.get(cid)
        if not meta:
            continue
        h = _norm_text_hash(meta["text"])
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        results.append({
            "text": meta["text"],
            "filename": meta["filename"],
            "page": meta["page"],
            "score": fused[cid],
        })
        if len(results) >= top_k:
            break

    debug_n = min(10, len(results))
    print(f"[RAG-STORE] hybrid_search('{query[:60]}'): top {debug_n} of {len(results)} returned chunk(s):")
    for i, r in enumerate(results[:debug_n], start=1):
        print(f"    #{i}  file={r['filename']}  page={r['page']}  score={r['score']:.4f}  "
              f"text={r['text'][:80]!r}...")

    return results


def get_chunks_by_page(filename: str, page_num: int):
    """
    Direct metadata lookup for 'what's on page N' style queries. These
    fail (or return unrelated content) under embedding/BM25 search
    because the literal page number rarely appears meaningfully inside
    the chunk text itself - this bypasses semantic search entirely and
    just filters the store by (filename, page).
    """
    return [
        {"text": m["text"], "filename": m["filename"], "page": m["page"]}
        for m in _metadata.values()
        if m["filename"] == filename and m["page"] == page_num
    ]


def get_page_range(filename: str):
    """Returns (min_page, max_page) indexed for a file, or (None, None) if
    the file has no page-numbered chunks (e.g. non-paginated formats)."""
    pages = [m["page"] for m in _metadata.values() if m["filename"] == filename and m["page"] is not None]
    return (min(pages), max(pages)) if pages else (None, None)


def sample_document_chunks(filename: str, max_chunks: int = 12):
    """Evenly-spaced sample of a document's chunks across its full length,
    used for summary/overview requests on large documents instead of
    blindly truncating to the first N characters (which misses everything
    past the cut-off in a 300-500 page PDF)."""
    ids = [cid for cid, m in _metadata.items() if m["filename"] == filename]
    if not ids:
        return []
    ids.sort(key=lambda cid: int(cid))  # chunk ids were assigned in document order
    if len(ids) <= max_chunks:
        picked = ids
    else:
        step = len(ids) / max_chunks
        picked = [ids[int(i * step)] for i in range(max_chunks)]
    return [{"text": _metadata[cid]["text"], "filename": filename, "page": _metadata[cid]["page"]} for cid in picked]