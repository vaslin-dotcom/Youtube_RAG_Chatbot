from urllib.parse import urlparse, parse_qs
from llm import get_llm
from schemas import KnowledgeGraph
from config import *
from prompts import entity_extraction_prompt
import threading
from neo4j.exceptions import TransientError
from time import sleep
entity_extractor_llm=get_llm(output_schema=KnowledgeGraph)

MAX_WORKERS = 8
RATE_LIMIT_DELAY = 1.5
_rate_semaphore = threading.Semaphore(MAX_WORKERS)

# def extract_video_id(url: str) -> str:
#     parsed = urlparse(url)
#     if parsed.netloc == "youtu.be":
#         return parsed.path[1:]
#     else:
#         return parse_qs(parsed.query)["v"][0]

def extract_knowledgeGraph(chunk:str) -> KnowledgeGraph:
    kg=entity_extractor_llm.invoke(entity_extraction_prompt.format(
        chunk=chunk,
    ))
    return kg

def property_to_dict(properties):
    return {p.key: p.value for p in properties} if properties else {}

def _sanitize_label(text: str) -> str:
    return text.strip().upper().replace(" ", "_").replace("-", "_")


# ── 1. Remove per-node embedding from store_in_graphDB, accept map instead ──
def store_in_graphDB(kg: KnowledgeGraph, session, embedding_map: dict):
    for node in kg.nodes:
        props = property_to_dict(node.properties)
        label = _sanitize_label(node.type)
        node_embedding = embedding_map.get(node.name)

        query = f"""
            MERGE (n {{name: $name}})
            SET n:{label}
            SET n:__Entity__
            SET n += $props
            {'SET n.embedding = $embedding' if node_embedding else ''}
        """
        params = dict(name=node.name, props=props)
        if node_embedding:
            params['embedding'] = node_embedding
        session.run(query, **params)

    for relation in kg.relationships:
        props = property_to_dict(relation.properties)
        rel_type = _sanitize_label(relation.type)
        session.run(
            f"""
            MERGE (a {{name: $source}})
            MERGE (b {{name: $target}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += $props
            """,
            source=relation.source,
            target=relation.target,
            props=props
        )

# ── 2. store_with_retry now accepts embedding_map ──────────────────────────
def store_with_retry(kg, embedding_map: dict, max_retries=3):
    for attempt in range(max_retries):
        try:
            with driver.session() as session:
                store_in_graphDB(kg, session, embedding_map)   # ✅ pass map
            return True
        except TransientError as e:
            if attempt < max_retries - 1:
                sleep(0.5 * (attempt + 1))
                continue
            print(f"[SKIP] Failed after {max_retries} attempts: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] {e}")
            return False

def close_driver():
    driver.close()
    print("Terminating connection with DB")


def format_neo4j_context(records):
    formatted = []
    for record in records:
        entity = record['entity']
        entity_type = [l for l in record['type'] if l != '__Entity__'][0]
        connections = record['connections']

        # deduplicate triples
        seen = set()
        conn_strings = []

        for conn in connections:
            if conn['from_node'] and conn['to_node']:
                triple = (
                    f"{conn['from_node']} "
                    f"{conn['relation']} "
                    f"{conn['to_node']}"
                )
                if triple not in seen:
                    seen.add(triple)
                    conn_strings.append(triple)

        if conn_strings:
            context = (
                    f"{entity} is a {entity_type}:\n" +
                    '\n'.join(conn_strings)
            )
        else:
            context = f"{entity} is a {entity_type}"

        formatted.append(context)
    return formatted


def extract_single_chunk(args):
    index, chunk, total = args
    with _rate_semaphore:
        try:
            kg = extract_knowledgeGraph(chunk)
            print(f"Extracted {index + 1}/{total}")
            return index, kg, None
        except Exception as e:
            print(f"[ERROR] Chunk {index + 1}/{total} failed: {e}")
            return index, None, str(e)


