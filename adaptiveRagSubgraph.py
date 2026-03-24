from schemas import *
from config import *
from llm import get_llm
from prompts import *
from helper_functions import *
from langgraph.graph import StateGraph,END

route_selection_llm = get_llm(output_schema=RouteDecision)
answer_llm=get_llm(mode='generation')
grader_llm=get_llm(output_schema=GradeDecision)
query_transformer_llm=get_llm()

def classifier(state:chatState):
    query=state['query']
    route=route_selection_llm.invoke(route_selection_prompt.format(
        query=query
    ))
    return{
        'route':route.route
    }

def after_classification(state: chatState):
    if state['route'] == 'direct':
        return 'direct_answer'
    else:
        return 'graph_retriever'

def graph_retriever(state: chatState):
    query=state['query']
    query_embedding = embeddings.embed_query(query)
    results = index.query(
        vector=query_embedding,
        top_k=5,
        include_metadata=True
    )
    pinecone_context = [match['metadata']['text'] for match in results['matches']]

    neo4j_context = []
    with driver.session() as session:
        # In graph_retriever
        results = session.run("""
            CALL db.index.vector.queryNodes('node_embeddings', 2, $query_embedding)
YIELD node, score
OPTIONAL MATCH path = (node)-[*1..2]-(related)
WHERE related <> node AND path IS NOT NULL
WITH node, score, path,
     nodes(path) as path_nodes,
     relationships(path) as rels
WHERE path_nodes IS NOT NULL AND size(path_nodes) >= 2
WITH node, score,
     [i in range(0, size(path_nodes)-2) |
         CASE
             WHEN startNode(rels[i]) = path_nodes[i]
             THEN {
                 from_node: path_nodes[i].name,
                 relation: type(rels[i]),
                 to_node: path_nodes[i+1].name
             }
             ELSE {
                 from_node: path_nodes[i+1].name,
                 relation: type(rels[i]),
                 to_node: path_nodes[i].name
             }
         END
     ] as triples
WHERE triples IS NOT NULL AND size(triples) > 0
UNWIND triples as triple
RETURN
    node.name as entity,
    labels(node) as type,
    score,
    collect(DISTINCT triple) as connections
ORDER BY score DESC
        """, query_embedding=query_embedding)

        neo4j_context = format_neo4j_context(results)
    return {
        'pinecone_context': pinecone_context,
        'neo4j_context': neo4j_context
    }

def doc_grader(state: chatState):
    vector_context=state['pinecone_context']
    graph_context=state['neo4j_context']
    grade=grader_llm.invoke(grader_prompt.format(
        vector_context=vector_context,
        graph_context=graph_context,
        query=state['query']
    ))
    if grade.pinecone_relevant or grade.neo4j_relevant:
        return{
            'context_quality':True
        }
    return{
        'context_quality':False
    }

def after_grading(state: chatState):
    if state['context_quality']:
        return 'answer_generator'
    elif state['retry_count'] >= 3:
        print("Max retries reached — answering with available context")
        return 'answer_generator'
    else:
        return 'transform_query'

def transform_query(state: chatState):
    query = state['query']
    new_query = query_transformer_llm.invoke(
        query_transformer_prompt.format(query=query)
    )
    return {
        'query': new_query.content,
        'retry_count': state['retry_count'] + 1,
        'pinecone_context': [],
        'neo4j_context': []
    }

def answer_generator(state: chatState):
    query = state['query']
    pinecone_context = '\n'.join(state['pinecone_context'])
    neo4j_context = '\n'.join(state['neo4j_context'])

    if not pinecone_context and not neo4j_context:
        answer = answer_llm.invoke(direct_answer_prompt.format(query=query))
    else:
        answer = answer_llm.invoke(
            answer_generation_prompt.format(
                query=query,
                pinecone_context=pinecone_context,
                neo4j_context=neo4j_context
            )
        )
    return {'answer': answer.content
            }

graph=StateGraph(chatState)
graph.add_node('classifier',classifier)
graph.set_entry_point('classifier')
graph.add_node('graph_retriever',graph_retriever)
graph.add_node('doc_grader',doc_grader)
graph.add_node('answer_generator',answer_generator)
graph.add_node('transform_query',transform_query)
graph.add_edge('graph_retriever', 'doc_grader')
graph.add_edge('transform_query', 'classifier')
graph.add_conditional_edges('classifier',after_classification,{
    'direct_answer':'answer_generator',
    'graph_retriever':'graph_retriever'
})
graph.add_conditional_edges('doc_grader',after_grading,{
    'answer_generator':'answer_generator',
    'transform_query':'transform_query'
})
graph.add_edge('answer_generator', END)

adaptiveRag=graph.compile()


if __name__ == '__main__':
    test_state = {
        "query": "What did the director say about season 8 budget?",
        "route": "",
        "pinecone_context": [],
        "neo4j_context": [],
        "context_quality": False,
        "answer": "",
        "retry_count": 0,
        "chat_history": []
    }

    result = adaptiveRag.invoke(test_state)
    print(f"Route taken : {result['route']}")
    print(f"Retry count : {result['retry_count']}")
    print(f"Answer      : {result['answer']}")
    print(f"Chat history: {result['chat_history']}")
