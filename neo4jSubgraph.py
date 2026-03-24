from schemas import *
from helper_functions import *
from time import sleep
from langgraph.graph import StateGraph,END
from config import *

def entity_extractor(state: neo4jState):
    kg = []
    chunks = state['chunks']
    for i, chunk in enumerate(chunks):
        kg.append(extract_knowledgeGraph(chunk))
        print(f"Extracted {i+1}/{len(chunks)}")
        if len(chunks) >= 40:
            sleep(1.5)
    return {
        'graphs': kg
    }

def graph_builder(state: neo4jState):
    kg = state['graphs']
    with driver.session() as session:
        # Step 1 — create indexes first
        session.run("""
            CREATE INDEX entity_name IF NOT EXISTS
            FOR (n:__Entity__)
            ON (n.name)
        """)
        session.run("""
            CREATE VECTOR INDEX node_embeddings IF NOT EXISTS
            FOR (n:__Entity__)
            ON n.embedding
            OPTIONS {
                indexConfig: {
                    `vector.dimensions`: 1024,
                    `vector.similarity_function`: 'cosine'
                }
            }
        """)
        print("Indexes ready!")

        # Step 2 — write data
        for i,connection in enumerate(kg):
            store_in_graphDB(connection, session)
            print(f"saved {i + 1}/{len(kg)}")


    return {
        'status': True,
        'graphs': []
    }

graph=StateGraph(neo4jState)
graph.add_node('entity_extractor',entity_extractor)
graph.set_entry_point('entity_extractor')
graph.add_node('graph_builder',graph_builder)
graph.add_edge('entity_extractor','graph_builder')
graph.add_edge('graph_builder',END)

neo4jGraph=graph.compile()


