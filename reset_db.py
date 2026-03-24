from pinecone import Pinecone
from config import *
from neo4j import GraphDatabase

# Reset Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index("youtube-rag")
index.delete(delete_all=True)
print("Pinecone index cleared!")

# Reset Neo4j
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
with driver.session() as session:
    result = session.run("MATCH (n) DETACH DELETE n")
    print("Neo4j graph cleared!")
driver.close()
print("Done! Both databases reset.")