
import os
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from sentence_transformers import SentenceTransformer, CrossEncoder

# Load env
load_dotenv()

SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("SEARCH_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

# Init client
client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)

# Load models once
model = SentenceTransformer("all-MiniLM-L6-v2")
cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")



def hybrid_search(query: str, top_k: int = 3):
    query_embedding = model.encode(query).tolist()

    # 🔥 Fetch MORE results for reranking
    results = client.search(
        search_text=query,
        vector_queries=[
            {
                "kind": "vector",
                "vector": query_embedding,
                "k": 30,   # 🔥 increase
                "fields": "embedding"
            }
        ],
        top=30,  # 🔥 increase
        select=["term", "definition", "part_of_speech"]
    )

    output = []

    for r in results:
        output.append({
            "term": r["term"],
            "part_of_speech": r.get("part_of_speech", ""),
            "definition": r["definition"]
        })

    # 🔥 Cross-encoder reranking
    if output:
        # 🔥 Include term + definition (IMPORTANT FIX)
        query_doc_pairs = [
            [query, f"{item['term']} {item['definition']}"]
            for item in output
        ]

        rerank_scores = cross_encoder.predict(query_doc_pairs)

        for i, item in enumerate(output):
            item["confidence_score"] = float(rerank_scores[i])

        # 🔥 TERM BOOST (CRITICAL FOR LEGAL SEARCH)
        query_lower = query.strip().lower()

        for item in output:
            term_lower = item["term"].lower()

            if term_lower == query_lower:
                item["confidence_score"] += 10   # exact match boost
            elif query_lower in term_lower:
                item["confidence_score"] += 3

        # 🔥 Final sort
        output = sorted(output, key=lambda x: x["confidence_score"], reverse=True)

    return output[:top_k]

