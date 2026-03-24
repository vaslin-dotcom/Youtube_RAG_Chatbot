from langgraph.graph import StateGraph,END
from helper_functions import extract_video_id
from schemas import *
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from langchain_text_splitters import RecursiveCharacterTextSplitter
from vectorSubgraph import vectorGraph
from neo4jSubgraph import neo4jGraph
from supervisorSubgraph import supervisorGraph

def transcript_retriever(state: mainState):
    links = 'https://youtu.be/fE50xrnJnR8?si=RpJwEL8cS9dwbZQu'
    links = links.split(',')
    transcripts = []

    ytt_api = YouTubeTranscriptApi()

    for link in links:
        video_id = extract_video_id(link.strip())
        try:
            transcript_list = ytt_api.fetch(video_id)
            full_text = " ".join([entry.text for entry in transcript_list])
            transcripts.append(full_text)
        except (TranscriptsDisabled, NoTranscriptFound):
            print(f"No transcript available for {link}, skipping...")

    return {
        'transcript': transcripts,
        'links': links
    }

def chunker(state:mainState):
    transcripts=state['transcript']
    splitter=RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunks=[]
    for transcript in transcripts:
        chunks.extend(splitter.split_text(transcript))

    return{
        'chunks': chunks
    }

def run_vector(state:mainState):
    print("Running vector subgraph...")
    vector_write=vectorGraph.invoke({
        'chunks':state['chunks'],
        'status':False
    })
    return{
        'vector_status':vector_write['status'],
    }

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

def DB_check(state:mainState):
    if state['graph_status']==False:
        print("Graph creation_failed")
    if state['vector_status']==False:
        print("Vector creation_failed")
    return{
    }

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

if __name__ == '__main__':
    dummy_state = {
        "transcript": [],
        "links": [],
        "chunks": [],
        "vector_status": False,
        "graph_status": False,
        "add_more": False
    }
    result = youtube_rag.invoke(dummy_state)
    print(f"Vector status: {result['vector_status']}")
    print(f"Graph status: {result['graph_status']}")
    print(f"Total chunks processed: {len(result['chunks'])}")


