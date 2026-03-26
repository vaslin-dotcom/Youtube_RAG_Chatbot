from schemas import *
from adaptiveRagSubgraph import adaptiveRag
from langgraph.graph import StateGraph,END
from prompts import *
from llm import get_llm

query_llm=get_llm()
def context_manager(state: supervisorState):
    history = state['chat_history']

    if history:
        prev_chats=history
        enriched_query = query_llm.invoke(generate_query_from_context_prompt.format(
                    prev_chats=prev_chats,
                    query=state['query']
        )).content
        print(f"Enriched query: {enriched_query}")
    else:
        enriched_query = state['query']
    return {'query': enriched_query}

def run_subgraph(state: supervisorState):
    result = adaptiveRag.invoke({
        "query": state['query'],
        "route": "",
        "pinecone_context": [],
        "neo4j_context": [],
        "context_quality": False,
        "answer": "",
        "retry_count": 0,
        "chat_history": []
    })
    return {
        'answer': result['answer'],
        'chat_history': [{'user': state['query'], 'AI': result['answer']}]
    }

def get_input(state: supervisorState):
    query = input("\nYou: ").strip()
    return {'query': query}

def should_continue(state: supervisorState):
    if state['answer']:  # after first answer is generated
        print(f"\nBot: {state['answer']}")
    if state['query'].lower() in ['exit', 'quit', 'bye']:
        return END
    return 'get_input'
supervisor = StateGraph(supervisorState)
supervisor.add_node('context_manager', context_manager)
supervisor.add_node('run_subgraph', run_subgraph)
supervisor.add_node('get_input', get_input)

supervisor.set_entry_point('get_input')
supervisor.add_edge('get_input', 'context_manager')
supervisor.add_edge('context_manager', 'run_subgraph')
supervisor.add_conditional_edges('run_subgraph', should_continue, {
    'get_input': 'get_input',
    END: END
})

supervisorGraph = supervisor.compile()

# if __name__=='__main__':
#     test_state={
#         'query':'',
#         'answer': '',
#         'chat_history': []
#     }
#     supervisor=supervisorGraph.invoke(test_state)
#     print(supervisor)
if __name__ == '__main__':
    img = supervisorGraph.get_graph(xray=True).draw_mermaid_png()
    with open("supervisorSubgraph_xray.png", "wb") as f:
        f.write(img)
    print("Saved supervisorSubgraph_xray.png")