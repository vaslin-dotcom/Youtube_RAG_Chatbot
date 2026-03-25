from typing import TypedDict, List, Optional
from schemas import *
from helper_functions import *
from time import sleep
from langgraph.graph import StateGraph, END
from config import *
from concurrent.futures import ThreadPoolExecutor, as_completed


def entity_extractor(state: neo4jState):
    chunks = state['chunks']
    total = len(chunks)
    results = [None] * total
    print(f"Starting parallel extraction: {total} chunks, {MAX_WORKERS} workers")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for i, chunk in enumerate(chunks):
            future = executor.submit(extract_single_chunk, (i, chunk, total))
            futures[future] = i
            sleep(RATE_LIMIT_DELAY / MAX_WORKERS)

        for future in as_completed(futures):
            index, kg, error = future.result()
            if kg is not None:
                results[index] = kg
            else:
                print(f"[SKIP] Chunk {index + 1} skipped: {error}")

    kg_list = [kg for kg in results if kg is not None]
    print(f"Extraction done: {len(kg_list)}/{total} successful")
    return {'graphs': kg_list}


# ✅ NEW NODE — batch embed all unique node names at once
def batch_embedder(state: neo4jState):
    kg_list = state['graphs']

    # 1. Collect all unique node names across every KG
    unique_names = list({
        node.name
        for kg in kg_list
        for node in kg.nodes
    })
    total = len(unique_names)
    print(f"Batch embedding {total} unique nodes...")

    # 2. Embed in batches of 100 (safe for most APIs)
    EMBED_BATCH_SIZE = 100
    all_embeddings = []

    for i in range(0, total, EMBED_BATCH_SIZE):
        batch = unique_names[i : i + EMBED_BATCH_SIZE]
        batch_vecs = embeddings.embed_documents(batch)  # single API call per batch
        all_embeddings.extend(batch_vecs)
        print(f"  Embedded {min(i + EMBED_BATCH_SIZE, total)}/{total}")

        # small delay to respect rate limits
        if i + EMBED_BATCH_SIZE < total:
            sleep(1.0)

    # 3. Build lookup dict  {node_name -> embedding_vector}
    embedding_map = dict(zip(unique_names, all_embeddings))
    print(f"Batch embedding complete: {len(embedding_map)} embeddings ready")

    return {'embedding_map': embedding_map}


def graph_builder(state: neo4jState):
    kg = state['graphs']
    embedding_map = state['embedding_map']   # ✅ use pre-computed map
    total = len(kg)

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
        print("Indexes ready!")

    success = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            # ✅ pass embedding_map into each parallel write
            executor.submit(store_with_retry, connection, embedding_map): i
            for i, connection in enumerate(kg)
        }
        for future in as_completed(futures):
            i = futures[future]
            if future.result():
                success += 1
                print(f"Saved {success}/{total}")

    print(f"Graph build done: {success}/{total} successful")
    return {'status': True, 'graphs': []}


graph = StateGraph(neo4jState)
graph.add_node('entity_extractor', entity_extractor)
graph.add_node('batch_embedder', batch_embedder)      # ✅ new node
graph.add_node('graph_builder', graph_builder)

graph.set_entry_point('entity_extractor')
graph.add_edge('entity_extractor', 'batch_embedder')  # ✅ extract → embed → build
graph.add_edge('batch_embedder', 'graph_builder')
graph.add_edge('graph_builder', END)

neo4jGraph = graph.compile()