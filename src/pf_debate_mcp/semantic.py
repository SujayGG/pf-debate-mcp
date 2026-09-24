"""Plain-English search and auto-cut suggestions, with no LLM and no per-query cost.

Uses static embeddings (model2vec potion-retrieval-32M, MIT, CPU-only, ~1 ms per query):

  query ──▶ BM25 top 100 (library.search) ─┐
        └─▶ embedding top 100 (this file) ─┴─▶ reciprocal-rank fusion ──▶ filters ──▶ results

Card vectors live next to the active library file (<library>.emb.npy + .ids.npy, float16) and are
built on first use in about 15 seconds, so a library update never needs a second download.
Until they exist, search quietly falls back to keywords.
"""

import re
import threading

import numpy as np

from . import library
from .cards import CutError, cut, paragraph_spans

MODEL = "minishlab/potion-retrieval-32M"
# ponytail: static embeddings handle phrasing, not deep synonyms ("server farms" != "data centers");
# swap in a small transformer (e.g. bge-small ONNX) if students report misses, at ~10x CPU per query.
_lock = threading.Lock()
_state: dict = {"model": None, "path": None, "ids": None, "vecs": None, "building": False}


def _model():
    if _state["model"] is None:
        from model2vec import StaticModel  # heavy import only when semantic features are used

        _state["model"] = StaticModel.from_pretrained(MODEL)
    return _state["model"]


def embed(texts: list[str]) -> np.ndarray:
    v = _model().encode(texts)
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)


def _files():
    lib = library.db_path()
    return lib, lib.with_suffix(".emb.npy"), lib.with_suffix(".ids.npy")


def build_index(log=print) -> None:
    """Embed every library card (tag + headings + highlighted text) and save next to the library."""
    lib, emb_f, ids_f = _files()
    con = library._connect(lib)
    rows = con.execute("select id, tag, coalesce(heads,''), coalesce(spoken,'') from cards").fetchall()
    con.close()
    ids = np.array([r[0] for r in rows], dtype=np.int64)
    texts = [f"{r[1]}. {r[2]}. {r[3][:400]}" for r in rows]
    vecs = np.concatenate([embed(texts[i:i + 20_000]) for i in range(0, len(texts), 20_000)]) if texts else \
        np.zeros((0, 512), dtype=np.float32)
    np.save(ids_f, ids)
    np.save(emb_f, vecs.astype(np.float16))
    log(f"Semantic index built for {len(ids)} cards.")


def _loaded() -> bool:
    """Load vectors for the active library; start a background build if they don't exist yet."""
    lib, emb_f, ids_f = _files()
    if _state["path"] == lib and _state["vecs"] is not None:
        return True
    with _lock:
        if emb_f.exists() and ids_f.exists():
            # float16 on disk (half the download/disk), float32 in RAM (~350 MB) so a query is one fast matmul
            _state.update(path=lib, ids=np.load(ids_f), vecs=np.load(emb_f).astype(np.float32))
            return True
        if not _state["building"] and library.ready():
            _state["building"] = True

            def run():
                try:
                    build_index(log=lambda m: None)
                finally:
                    _state["building"] = False

            threading.Thread(target=run, daemon=True).start()
    return False


def semantic_ids(query: str, k: int = 100) -> list[int]:
    if not _loaded():
        return []
    scores = _state["vecs"] @ embed([query])[0].astype(np.float32)
    top = np.argpartition(-scores, min(k, len(scores) - 1))[:k] if len(scores) else []
    return [int(_state["ids"][i]) for i in sorted(top, key=lambda i: -scores[i])]


def hybrid_search(query: str, limit: int = 10, year_from=None, side=None, event=None,
                  sort: str = "relevance") -> list[dict]:
    """Keyword and meaning search fused, so plain-English questions and debate shorthand both work."""
    # Strict (all-words) keyword hits only: an any-word fallback lets one common word ("power", "war")
    # outvote meaning on plain-English questions. Meaning-based recall comes from the embeddings.
    keyword = library.search(query, 100, year_from, side, event, "relevance", strict=True)
    fused: dict[str, float] = {}
    for rank, hit in enumerate(keyword):
        fused[hit["id"]] = fused.get(hit["id"], 0) + 1 / (60 + rank)
    sem = [f"lib:{i}" for i in semantic_ids(query)]
    for rank, cid in enumerate(sem):
        fused[cid] = fused.get(cid, 0) + 1 / (60 + rank)
    if not sem:
        return library.search(query, limit, year_from, side, event, sort)
    rows = {h["id"]: h for h in keyword}
    rows.update({h["id"]: h for h in library.rows([c for c in fused if c not in rows], year_from, side, event)})
    ranked = sorted((c for c in fused if c in rows), key=lambda c: -fused[c])[:max(limit * 3, 30)]
    if sort == "popular":  # among the relevant set, most-read first
        ranked.sort(key=lambda c: -(rows[c]["times_read"] or 0))
    return [rows[c] for c in ranked[:limit]]


_CLAUSE = re.compile(r"[^.!?;:,—]+[.!?;:,—]?")


def suggest(text: str, claim: str) -> dict:
    """Pick the passage that best supports `claim` and propose highlights (clauses most similar to it).
    Everything is an exact slice of the source, and the result is checked with the real cutter."""
    spans = paragraph_spans(text)[:600]
    if not spans:
        raise CutError("The source has no text to cut.")
    claim_v = embed([claim])[0]
    sims = embed([t for _, t in spans]) @ claim_v
    # Headlines and captions echo the claim but make useless cards: prefer paragraphs with real sentences.
    weight = np.array([min(1.0, len(t) / 200) for _, t in spans])
    p = int(np.argmax(sims * weight))
    lo = hi = p  # widen a short best paragraph with neighbors, but only neighbors that are also on point
    while len("\n".join(t for _, t in spans[lo:hi + 1])) < 400:
        options = [i for i in (lo - 1, hi + 1) if 0 <= i < len(spans) and sims[i] >= 0.6 * sims[p]]
        if not options:
            break
        best = max(options, key=lambda i: sims[i])
        lo, hi = min(lo, best), max(hi, best)
    p = lo
    body = "\n".join(t for _, t in spans[lo:hi + 1])
    clauses = [m.group().strip() for m in _CLAUSE.finditer(body) if len(m.group().split()) >= 4]
    if not clauses:
        clauses = [body]
    cv = embed(clauses) @ claim_v
    order = sorted(range(len(clauses)), key=lambda i: -cv[i])
    hl_idx = sorted(order[:3])  # the 3 closest clauses, kept in reading order
    ul_idx = sorted(set(order[:6]))
    highlight = [clauses[i].rstrip(",;:—") for i in hl_idx]
    underline = [clauses[i].rstrip(",;:—") for i in ul_idx]
    words = body.split()
    start, end = " ".join(words[:8]), " ".join(words[-8:])
    card = cut(text, start, end, underline, highlight, paragraph=p)  # raises CutError if anything drifts
    return {"paragraph": p, "start_quote": start, "end_quote": end, "highlight": highlight,
            "underline": underline, "score": round(float(sims[p]), 3), "warnings": card["warnings"]}
