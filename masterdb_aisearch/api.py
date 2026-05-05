from fastapi import FastAPI, Query, HTTPException
from typing import Optional
import time

try:
    from .embeddings import get_embedding
    from .azure_search import hybrid_search
except ImportError:
    from embeddings import get_embedding
    from azure_search import hybrid_search


app = FastAPI(
    title="LexAIO Legal Search India state and central acts API",
    description="Hybrid + Vector Search over Legal Documents",
    version="1.0"
)

@app.get("/search")
def search(
    query: str = Query(..., min_length=3, description="Enter your legal question"),
    top_k: Optional[int] = Query(
        default=None,
        ge=1,
        le=20,
        description="Optional number of search results to return"
    )
):
    try:
        start = time.time()

        embedding = get_embedding(query)

        # ✅ let search decide top_k
        results = hybrid_search(query, embedding, top_k=top_k)

        end = time.time()

        return {
            "query": query,
            "num_results": len(results),
            "search_time_sec": round(end - start, 3),
            "results": results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
