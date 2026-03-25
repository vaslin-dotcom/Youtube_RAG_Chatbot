from config import *
from neo4j import GraphDatabase
from pinecone import Pinecone

def reset_database():
    # ── Pinecone ───────────────────────────────────────────────────────────────
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index("youtube-rag")
    try:
        index.delete(delete_all=True)
        print("Pinecone index cleared!")
    except Exception as e:
        # 404 = namespace is already empty — treat as success
        if "404" in str(e) or "Namespace not found" in str(e) or "not found" in str(e).lower():
            print("Pinecone index already empty — nothing to delete.")
        else:
            raise  # re-raise unexpected errors

    # ── Neo4j ──────────────────────────────────────────────────────────────────
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Neo4j graph cleared!")
    finally:
        driver.close()

    print("Done! Both databases reset.")


if __name__ == '__main__':
    reset_database()