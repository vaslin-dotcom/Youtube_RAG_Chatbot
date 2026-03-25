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

# from pinecone import Pinecone
#
# pc = Pinecone(api_key=PINECONE_API_KEY)
# index = pc.Index("youtube-rag")
#
# query = "What are the main topics covered?"
#
# # Step 1 — embed the query
# query_embedding = embeddings.embed_query(query)
#
# # Step 2 — search Pinecone
# results = index.query(
#     vector=query_embedding,
#     top_k=5,
#     include_metadata=True
# )
#
# # Step 3 — print results
# for match in results['matches']:
#     print("========================")
#     print(f"Score : {match['score']:.4f}")
#     print(f"Text  : {match['metadata']['text']}")


import os
import assemblyai as aai


def transcript_retriever(state: dict):
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise ValueError("ASSEMBLYAI_API_KEY not found.")

    aai.settings.api_key = api_key

    # --- NEW: Add this configuration ---
    config = aai.TranscriptionConfig(
        speech_models=["universal-3-pro", "universal-2"]
    )

    transcriber = aai.Transcriber()

    print(f"Transcribing: {os.path.basename(state['audio_path'])}...")

    # Pass the config here
    transcript = transcriber.transcribe(state['audio_path'], config=config)

    if transcript.error:
        raise RuntimeError(f"Transcription failed: {transcript.error}")

    return {"transcript": [transcript.text]}


if __name__ == "__main__":
    # Ensure you keep the 'r' for Windows paths!
    path = r"D:\data\MCP vs RAG Which AI Technique Should You Use - CodeCraft Academy.mp3"

    dummy_state = {"audio_path": path}

    if os.path.exists(path):
        try:
            results = transcript_retriever(dummy_state)
            print("\n✅ Success! First 200 chars:")
            print(results['transcript'][0][:200])
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("File not found.")