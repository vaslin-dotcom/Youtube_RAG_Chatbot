from schemas import *
from helper_functions import *
from time import sleep
from langgraph.graph import StateGraph, END
from config import *


def _notify(message: str, percent: int):
    """Forward to mainGraph's callback if set, always print."""
    print(f"[{percent}%] {message}")
    try:
        import mainGraph
        if mainGraph._progress_cb:
            mainGraph._progress_cb(message, percent)
    except Exception:
        pass


def entity_extractor(state: neo4jState):
    chunks = state['chunks']
    total = len(chunks)
    kg = []

    for i, chunk in enumerate(chunks):
        # Progress: 52% → 80% during extraction
        pct = 52 + int((i / total) * 28)
        _notify(f"🧠 Extracting entities {i+1}/{total}", pct)
        kg.append(extract_knowledgeGraph(chunk))
        if total >= 40:
            sleep(1.5)

    return {'graphs': kg}


def graph_builder(state: neo4jState):
    kg = state['graphs']
    total = len(kg)

    with driver.session() as session:
        session.run("""
            CREATE INDEX entity_name IF NOT EXISTS
            FOR (n:__Entity__) ON (n.name)
        """)
        session.run("""
            CREATE VECTOR INDEX node_embeddings IF NOT EXISTS
            FOR (n:__Entity__) ON n.embedding
            OPTIONS {
                indexConfig: {
                    `vector.dimensions`: 1024,
                    `vector.similarity_function`: 'cosine'
                }
            }
        """)
        _notify("📋 Indexes ready, saving graph nodes...", 82)

        for i, connection in enumerate(kg):
            # Progress: 82% → 94% during saving
            pct = 82 + int((i / total) * 12)
            _notify(f"💾 Saving graph {i+1}/{total}", pct)
            store_in_graphDB(connection, session)

    return {'status': True, 'graphs': []}


graph = StateGraph(neo4jState)
graph.add_node('entity_extractor', entity_extractor)
graph.add_node('graph_builder', graph_builder)
graph.set_entry_point('entity_extractor')
graph.add_edge('entity_extractor', 'graph_builder')
graph.add_edge('graph_builder', END)

neo4jGraph = graph.compile()