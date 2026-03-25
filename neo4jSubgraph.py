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
            sleep(RATE_LIMIT_DELAY / MAX_WORKERS)  # 1.5/8 = 0.187s stagger

        for future in as_completed(futures):
            index, kg, error = future.result()
            if kg is not None:
                results[index] = kg
            else:
                print(f"[SKIP] Chunk {index + 1} skipped: {error}")

    kg_list = [kg for kg in results if kg is not None]
    print(f"Extraction done: {len(kg_list)}/{total} successful")
    return {'graphs': kg_list}



def graph_builder(state: neo4jState):
    kg = state['graphs']
    total = len(kg)

    # create indexes first — single session, must be sequential
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

    # parallel writes
    success = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(store_with_retry, connection): i
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
graph.set_entry_point('entity_extractor')
graph.add_node('graph_builder', graph_builder)
graph.add_edge('entity_extractor', 'graph_builder')
graph.add_edge('graph_builder', END)

neo4jGraph = graph.compile()


