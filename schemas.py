from typing import TypedDict, List, Optional,Literal,Annotated
from pydantic import BaseModel, Field

class mainState(TypedDict):
    transcript: List[str]
    audio_path:str
    chunks: List[str]
    vector_status: bool
    graph_status: bool
    add_more: bool

class vectorState(TypedDict):
    chunks: List[str]
    status: bool

class NodeProperty(BaseModel):
    key: str = Field(description="Property key e.g. 'founded_year'")
    value: str = Field(description="Property value e.g. '1998'")

class Node(BaseModel):
    name: str = Field(description="Canonical name e.g. 'Saad Khan'")
    type: str = Field(description="Label e.g. 'PERSON', 'COMPANY'")
    properties: Optional[List[NodeProperty]] = Field(default_factory=list)

class Relationship(BaseModel):
    source: str = Field(description="Name of source node")
    target: str = Field(description="Name of target node")
    type: str = Field(description="Relationship type e.g. 'WORKS_AT'")
    properties: Optional[List[NodeProperty]] = Field(default_factory=list)

class KnowledgeGraph(BaseModel):
    nodes: List[Node] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)

class neo4jState(TypedDict):
    chunks: List[str]
    graphs: List[KnowledgeGraph]
    embedding_map: dict        # ✅ new
    status: bool

class RouteDecision(BaseModel):
    route: Literal["direct", "graph"]=Field(description="Say the mode of answering for the question")
    reason: str=Field(description="Reason for the decision")

class chatState(TypedDict):
    query: str
    route: str
    pinecone_context: List[str]
    neo4j_context: List[str]
    context_quality: bool
    answer: str
    retry_count: int

class GradeDecision(BaseModel):
    pinecone_relevant: bool = Field(
        description="Is pinecone context relevant and specific to the query?"
    )
    neo4j_relevant: bool = Field(
        description="Is neo4j context relevant and specific to the query?"
    )
    reason: str = Field(description="Reason for the decision")


def limit_chat_history(current: List[dict], new: List[dict]) -> List[dict]:
    full_history = current + new
    return full_history[-3:]

class supervisorState(TypedDict):
    query: str
    answer: str
    chat_history: Annotated[List[dict], limit_chat_history]