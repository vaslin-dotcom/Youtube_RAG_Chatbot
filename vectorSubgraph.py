from config import *
from schemas import *
from langgraph.graph import StateGraph,END
import time
from pinecone import Pinecone

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index("youtube-rag")

def vectorise(state: vectorState):
    chunks = state['chunks']
    batch_size = 50
    all_vectors = []

    if len(chunks) >= 40:
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            vectors = embeddings.embed_documents(batch)
            all_vectors.extend(vectors)
            time.sleep(1.5)
    else:
        all_vectors = embeddings.embed_documents(chunks)

    records = []
    for i, vector in enumerate(all_vectors):
        records.append({
            "id": f"chunk_{i}",
            "values": vector,
            "metadata": {"text": chunks[i]}
        })

    for i in range(0, len(records), 100):
        index.upsert(vectors=records[i:i+100])

    return {'status': True}

graph=StateGraph(vectorState)
graph.add_node('vectorise',vectorise)
graph.set_entry_point('vectorise')
graph.add_edge('vectorise',END)

vectorGraph=graph.compile()

if __name__ == '__main__':
    dummy_state = {

        "chunks": ["As we are entering a new era of AI, meet independent digital agents that can think, plan, and act on their own, like book a meeting, write a report, or plan your whole day without you having to lift a finger. This is called Agentic AI, and it's changing the way we work and even make decisions. In this video, we'll break down what Agentic AI is, how it works, where it's already being used, and what it means for all of us. Let's dive in. So, what is Agentic AI? Aentic AI refers to artificial intelligence systems that act autonomously, proactively, and with a certain level of goal-directed intelligence. Think of them like software agents, digital entities that can understand their environment, set goals, make decisions, take actions, and learn from results. In short, these aren't just tools. They're doers. They don't wait for commands. They act. Think of them as the AI version of an intern that learned how to run your company overnight. Now, let's break down how AI agents actually work.", "They're doers. They don't wait for commands. They act. Think of them as the AI version of an intern that learned how to run your company overnight. Now, let's break down how AI agents actually work. These systems operate in a loop that starts with a simple goal. From there, the AI creates a plan by breaking that goal into smaller tasks. It then chooses the best tools for the job. Maybe it browses the web, analyzes articles, or pulls data from different sources. Once ready, it gets to work, sending emails, updating spreadsheets, even coordinating with other apps or agents if needed. And here's the really smart part. After the task is done, it reviews the results, learns from what worked or didn't, and uses that knowledge to improve in future. In short, it's like giving a super assistant one sentence and watching it run an entire project from start to finish. Devon, for instance, can take a GitHub issue, research the problem, write the code, test it, and push it live autonomously.", "one sentence and watching it run an entire project from start to finish. Devon, for instance, can take a GitHub issue, research the problem, write the code, test it, and push it live autonomously. Similarly, Don Not pay is developing legal agents to contest parking tickets or negotiate bills. But with powerful new technology comes serious challenges we can't ignore. One major concern is loss of oversight. How do we ensure these agents don't make decisions that spiral out of control? Then there's goal misalignment. What if the AI misunderstands what we want and takes the wrong kind of action? Add to that the risk of security threats. These agents, like any software, can be hacked, manipulated, or used with bad intentions. And of course, there's the economic impact. As AI agents become capable of handling complex white collar tasks, what happens to the jobs they replace? These aren't just sci-fi scenarios or fear-mongering headlines. They're real issues we need to prepare for. We need", "of handling complex white collar tasks, what happens to the jobs they replace? These aren't just sci-fi scenarios or fear-mongering headlines. They're real issues we need to prepare for. We need to become smarter about how we guide them. setting clear boundaries, defining goals carefully, and making sure we stay in control of the technology we're building. In short, AI agents are already here, and in just a few years, these agents will be managing emails, running projects, even competing with you for the same clients. Scientists will test ideas faster. Entrepreneurs will scale without sleep, and teachers will personalize learning like never before. So, if this sparked your curiosity, hit like and subscribe button and tell us in the comments how would you use your own AI agent."],
        'status':False
    }
    result=vectorise(dummy_state)
    print(result['status'])