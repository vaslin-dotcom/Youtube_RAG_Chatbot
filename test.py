from config import *

# query = "jon snow"
#
# query_embedding = embeddings.embed_query(query)
#
# with driver.session() as session:
#     results = session.run("""
#         CALL db.index.vector.queryNodes('node_embeddings', 2, $query_embedding)
#         YIELD node, score
#         OPTIONAL MATCH (node)-[r]->(related)
#         RETURN
#             node.name as entity,
#             labels(node) as type,
#             score,
#             collect({
#                 relationship: type(r),
#                 related_entity: related.name
#             }) as connections
#         ORDER BY score DESC
#     """, query_embedding=query_embedding)
#
#     for record in results:
#         print("========================")
#         print(f"Entity    : {record['entity']}")
#         print(f"Type      : {record['type']}")
#         print(f"Score     : {record['score']:.4f}")
#         print(f"Connections: {record['connections']}")
#
# driver.close()

from pinecone import Pinecone

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index("youtube-rag")

query = "What are the main topics covered?"

# Step 1 — embed the query
query_embedding = embeddings.embed_query(query)

# Step 2 — search Pinecone
results = index.query(
    vector=query_embedding,
    top_k=5,
    include_metadata=True
)

# Step 3 — print results
for match in results['matches']:
    print("========================")
    print(f"Score : {match['score']:.4f}")
    print(f"Text  : {match['metadata']['text']}")