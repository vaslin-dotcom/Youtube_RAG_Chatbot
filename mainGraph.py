from langgraph.graph import StateGraph,END
from schemas import *
from langchain_text_splitters import RecursiveCharacterTextSplitter
from vectorSubgraph import vectorGraph
from neo4jSubgraph import neo4jGraph
from supervisorSubgraph import supervisorGraph
import os
import assemblyai as aai



import time
from functools import wraps


def time_it(func):
     @wraps(func)
     def wrapper(*args, **kwargs):
        start_time = time.perf_counter()  # Start the clock
        result = func(*args, **kwargs)  # Run the actual function
        end_time = time.perf_counter()  # Stop the clock

        duration = end_time - start_time
        print(f"⏱️  [{func.__name__}] took {duration:.4f} seconds")
        return result

     return wrapper


@time_it
def transcript_retriever(state: mainState):
    print("transcribing")
    audio_path = state['audio_path']

    # 1. Configure AssemblyAI
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise ValueError("Missing 'ASSEMBLYAI_API_KEY' environment variable.")

    aai.settings.api_key = api_key

    # Using 'best' ensures high accuracy/speed and passes Pydantic validation
    config = aai.TranscriptionConfig(
        speech_models=["universal-3-pro", "universal-2"]
    )
    transcriber = aai.Transcriber()

    # 2. Transcribe (SDK handles file opening automatically)
    transcript = transcriber.transcribe(audio_path, config=config)

    if transcript.error:
        raise RuntimeError(f"AssemblyAI Error: {transcript.error}")

    transcript_text = transcript.text
    print(f"Transcription done! ({len(transcript_text):,} characters)")


    try:
        if os.path.exists(audio_path):
            os.remove(audio_path)
            print(f"[CLEANUP] Deleted: {audio_path}")
    except Exception as e:
        print(f"[CLEANUP WARNING] {e}")
    print('completed transcription')
    return {'transcript': [transcript_text]}

@time_it
def chunker(state:mainState):
    transcripts=state['transcript']
    splitter=RecursiveCharacterTextSplitter(
        chunk_size=1800,
        chunk_overlap=300
    )
    chunks=[]
    for transcript in transcripts:
        chunks.extend(splitter.split_text(transcript))

    return{
        'chunks': chunks
    }

@time_it
def run_vector(state:mainState):
    print("Running vector subgraph...")
    vector_write=vectorGraph.invoke({
        'chunks':state['chunks'],
        'status':False
    })
    return{
        'vector_status':vector_write['status'],
    }

@time_it
def run_neo4j(state:mainState):
    print("Running neo4j subgraph...")
    neo4j_write=neo4jGraph.invoke({
        'chunks':state['chunks'],
        'status':False,
        'graphs':[]
    })
    return{
        'graph_status':neo4j_write['status'],
    }

@time_it
def DB_check(state:mainState):
    if state['graph_status']==False:
        print("Graph creation_failed")
    if state['vector_status']==False:
        print("Vector creation_failed")
    return{
    }

@time_it
def run_chatbot(state: mainState):
    supervisorGraph.invoke({
        'query': '',
        'original_query': '',
        'answer': '',
        'chat_history': []
    })
    return {}




graph=StateGraph(mainState)
graph.add_node('transcript_retriever',transcript_retriever)
graph.set_entry_point('transcript_retriever')
graph.add_node('chunker',chunker)
graph.add_node('run_neo4j',run_neo4j)
graph.add_node('DB_check',DB_check)
graph.add_node('run_vector',run_vector)
graph.add_node('chatbot', run_chatbot)
graph.add_edge('transcript_retriever','chunker')
graph.add_edge('run_neo4j','DB_check')
graph.add_edge('run_vector','DB_check')
graph.add_edge('chunker','run_vector')
graph.add_edge('chunker','run_neo4j')
graph.add_edge('DB_check', 'chatbot')
graph.add_edge('chatbot', END)

youtube_rag=graph.compile()

# if __name__ == '__main__':
#     dummy_state = {
#         "audio_path": r"D:\data\The COMPLETE Game of Thrones Recap  CRAM IT - Screen Junkies (1).mp3",  # ← point to a real file
#         "transcript": [],
#         "chunks": [],
#         "vector_status": False,
#         "graph_status": False,
#         "add_more": False
#     }
#     result = youtube_rag.invoke(dummy_state)
#     print(f"Vector status: {result['vector_status']}")
#     print(f"Graph status: {result['graph_status']}")
#     print(f"Total chunks processed: {len(result['chunks'])}")


if __name__ == '__main__':
    img = youtube_rag.get_graph(xray=True).draw_mermaid_png()
    with open("mainGraph_xray.png", "wb") as f:
        f.write(img)
    print("Saved mainGraph_xray.png")