
from fastapi import FastAPI, Query
from hybrid_search import hybrid_search

app = FastAPI(title="Legal Dictionary API")


@app.get("/")
def home():
    return {"message": "API running 🚀"}


@app.get("/search")
def search_endpoint(
    q: str = Query(..., description="Search query"),
    top_k: int = 3
):
    results = hybrid_search(q, top_k)

    return {
        "query": q,
        "count": len(results),
        "results": results
    }
