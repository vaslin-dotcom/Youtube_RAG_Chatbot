from langgraph.graph import StateGraph, END
from schemas import *
from langchain_text_splitters import RecursiveCharacterTextSplitter
from vectorSubgraph import vectorGraph
from neo4jSubgraph import neo4jGraph
from groq import Groq
import os
import assemblyai as aai

# ── Global progress callback ───────────────────────────────────────────────────
_progress_cb = None

def set_progress_callback(cb):
    global _progress_cb
    _progress_cb = cb

def _notify(message: str, percent: int):
    print(f"[{percent}%] {message}")
    if _progress_cb:
        _progress_cb(message, percent)


# ── Nodes ──────────────────────────────────────────────────────────────────────

def transcript_retriever(state: mainState):
    audio_path = state['audio_path']
    _notify("🎙️ Transcribing audio...", 5)

    # Configure AssemblyAI
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise ValueError("Missing 'ASSEMBLYAI_API_KEY' environment variable.")

    aai.settings.api_key = api_key

    config = aai.TranscriptionConfig(
        speech_models=["universal-3-pro", "universal-2"]
    )

    transcriber = aai.Transcriber()

    # The SDK handles the file opening and uploading automatically
    transcript = transcriber.transcribe(audio_path, config=config)

    if transcript.error:
        raise RuntimeError(f"AssemblyAI Error: {transcript.error}")

    transcript_text = transcript.text

    # --- Cleanup & Notifications (Same as original) ---
    try:
        if os.path.exists(audio_path):
            os.remove(audio_path)
            print(f"[CLEANUP] Deleted: {audio_path}")
    except Exception as e:
        print(f"[CLEANUP WARNING] {e}")

    _notify(f"✅ Transcription done! ({len(transcript_text):,} characters)", 20)

    return {'transcript': [transcript_text]}


def chunker(state: mainState):
    _notify("✂️ Chunking transcript...", 25)
    transcripts = state['transcript']
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1800,
        chunk_overlap=300,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    for transcript in transcripts:
        chunks.extend(splitter.split_text(transcript))
    _notify(f"✅ Chunking done! {len(chunks)} chunks created", 30)
    return {'chunks': chunks}


def run_vector(state: mainState):
    _notify("📦 Saving chunks to vector store...", 35)
    vector_write = vectorGraph.invoke({'chunks': state['chunks'], 'status': False})
    if vector_write['status']:
        _notify("✅ Vector store ready", 55)
    else:
        _notify("❌ Vector store failed", 55)
    return {'vector_status': vector_write['status']}


def run_neo4j(state: mainState):
    chunks = state['chunks']
    _notify(f"🧠 Starting knowledge graph pipeline ({len(chunks)} chunks)...", 35)
    neo4j_write = neo4jGraph.invoke({
        'chunks': chunks,
        'status': False,
        'graphs': [],
        'embedding_map': {}    # ✅ initialise new field
    })
    if neo4j_write['status']:
        _notify("✅ Knowledge graph ready", 95)
    else:
        _notify("❌ Knowledge graph failed", 95)
    return {'graph_status': neo4j_write['status']}

def DB_check(state: mainState):
    if not state['graph_status']:
        _notify("❌ Graph creation failed!", 97)
    if not state['vector_status']:
        _notify("❌ Vector store creation failed!", 97)
    if state['graph_status'] and state['vector_status']:
        _notify("✅ Both databases are ready! You can now chat.", 100)
    return {}


# ── Graph — restore parallel vector + neo4j ───────────────────────────────────
graph = StateGraph(mainState)
graph.add_node('transcript_retriever', transcript_retriever)
graph.add_node('chunker', chunker)
graph.add_node('run_vector', run_vector)
graph.add_node('run_neo4j', run_neo4j)
graph.add_node('DB_check', DB_check)

graph.set_entry_point('transcript_retriever')
graph.add_edge('transcript_retriever', 'chunker')
graph.add_edge('chunker', 'run_vector')    # ✅ both fire from chunker
graph.add_edge('chunker', 'run_neo4j')    # ✅ in parallel
graph.add_edge('run_vector', 'DB_check')
graph.add_edge('run_neo4j', 'DB_check')
graph.add_edge('DB_check', END)

ingestion_graph = graph.compile()


def run_ingestion(audio_path: str, progress_cb=None):
    set_progress_callback(progress_cb)
    result = ingestion_graph.invoke({
        "audio_path": audio_path,
        "transcript": [],
        "chunks": [],
        "vector_status": False,
        "graph_status": False,
        "add_more": False,
    })
    set_progress_callback(None)
    return result


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    def my_cb(msg, pct):
        print(f"  → {pct}% | {msg}")

    result = run_ingestion(
        audio_path=r"D:\data\MCP vs RAG Which AI Technique Should You Use - CodeCraft Academy.mp3",
        progress_cb=my_cb
    )
    print(f"Vector status: {result['vector_status']}")
    print(f"Graph status:  {result['graph_status']}")
    print(f"Chunks:        {len(result['chunks'])}")