from schemas import *
from helper_functions import *
from time import sleep
from langgraph.graph import StateGraph, END
from config import *
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ── Thread-safe progress counter ──────────────────────────────────────────────
_lock = threading.Lock()

def _notify(message: str, percent: int):
    print(f"[{percent}%] {message}")
    try:
        import mainGraph
        if mainGraph._progress_cb:
            mainGraph._progress_cb(message, percent)
    except Exception:
        pass


# ── Node 1: parallel entity extraction ───────────────────────────────────────
def entity_extractor(state: neo4jState):
    chunks = state['chunks']
    total = len(chunks)
    results = [None] * total
    completed = [0]  # mutable counter for closure

    _notify(f" Starting parallel extraction ({total} chunks, {MAX_WORKERS} workers)...", 52)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for i, chunk in enumerate(chunks):
            future = executor.submit(extract_single_chunk, (i, chunk, total))
            futures[future] = i
            sleep(RATE_LIMIT_DELAY / MAX_WORKERS)   # stagger submits: 1.5/8 = 0.19s

        for future in as_completed(futures):
            index, kg, error = future.result()
            if kg is not None:
                results[index] = kg
            else:
                print(f"[SKIP] Chunk {index + 1} skipped: {error}")

            with _lock:
                completed[0] += 1
                # Progress: 52% → 78% during extraction
                pct = 52 + int((completed[0] / total) * 26)
                _notify(f"🧠 Extracted {completed[0]}/{total} chunks", pct)

    kg_list = [kg for kg in results if kg is not None]
    _notify(f"✅ Extraction done: {len(kg_list)}/{total} successful", 78)
    return {'graphs': kg_list}


# ── Node 2: batch embed all unique nodes in one shot ─────────────────────────
def batch_embedder(state: neo4jState):
    kg_list = state['graphs']

    unique_names = list({
        node.name
        for kg in kg_list
        for node in kg.nodes
    })
    total = len(unique_names)
    _notify(f"⚡ Batch embedding {total} unique nodes...", 80)

    EMBED_BATCH_SIZE = 100
    all_embeddings = []

    for i in range(0, total, EMBED_BATCH_SIZE):
        batch = unique_names[i: i + EMBED_BATCH_SIZE]
        batch_vecs = embeddings.embed_documents(batch)   # 1 API call per batch
        all_embeddings.extend(batch_vecs)
        done = min(i + EMBED_BATCH_SIZE, total)
        pct = 80 + int((done / total) * 4)              # Progress: 80% → 84%
        _notify(f"⚡ Embedded {done}/{total} nodes", pct)
        if i + EMBED_BATCH_SIZE < total:
            sleep(1.0)

    embedding_map = dict(zip(unique_names, all_embeddings))
    _notify(f"✅ Embeddings ready: {len(embedding_map)} vectors", 84)
    return {'embedding_map': embedding_map}


# ── Node 3: parallel graph writes ────────────────────────────────────────────
def graph_builder(state: neo4jState):
    kg = state['graphs']
    embedding_map = state['embedding_map']   # ✅ pre-computed, no API calls here
    total = len(kg)
    saved = [0]

    # Create indexes first — must be sequential, single session
    with driver.session() as session:
        session.run("""
            CREATE INDEX entity_name IF NOT EXISTS
            FOR (n:__Entity__) ON (n.name)
        """)
        session.run("""
            CREATE VECTOR INDEX node_embeddings IF NOT EXISTS
            FOR (n:__Entity__) ON n.embedding
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1024,
                `vector.similarity_function`: 'cosine'
            }}
        """)
    _notify("📋 Indexes ready — saving to Neo4j in parallel...", 86)

    # Now parallel writes — each worker gets its own session via store_with_retry
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(store_with_retry, connection, embedding_map): i
            for i, connection in enumerate(kg)
        }
        for future in as_completed(futures):
            i = futures[future]
            if future.result():
                with _lock:
                    saved[0] += 1
                    # Progress: 86% → 95%
                    pct = 86 + int((saved[0] / total) * 9)
                    _notify(f"💾 Saved {saved[0]}/{total} graphs", pct)

    _notify(f"✅ Graph build done: {saved[0]}/{total} successful", 95)
    return {'status': True, 'graphs': []}


# ── Graph wiring ──────────────────────────────────────────────────────────────
graph = StateGraph(neo4jState)
graph.add_node('entity_extractor', entity_extractor)
graph.add_node('batch_embedder', batch_embedder)
graph.add_node('graph_builder', graph_builder)

graph.set_entry_point('entity_extractor')
graph.add_edge('entity_extractor', 'batch_embedder')  # ✅ extract → embed → build
graph.add_edge('batch_embedder', 'graph_builder')
graph.add_edge('graph_builder', END)

neo4jGraph = graph.compile()