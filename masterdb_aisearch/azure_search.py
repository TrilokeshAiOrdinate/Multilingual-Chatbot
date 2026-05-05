import os
import re
from functools import lru_cache
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from dotenv import dotenv_values

try:
    from .filters import extract_filters, build_azure_filter
except ImportError:
    from filters import extract_filters, build_azure_filter


ENV_PATH = Path(__file__).with_name(".env")


def _get_config():
    file_config = dotenv_values(ENV_PATH)

    endpoint = (
        file_config.get("SEARCH_ENDPOINT")
        or file_config.get("MASTERDB_ENDPOINT")
        or os.getenv("MASTERDB_SEARCH_ENDPOINT")
        or os.getenv("MASTERDB_ENDPOINT")
        or os.getenv("SEARCH_ENDPOINT")
    )
    api_key = (
        file_config.get("SEARCH_KEY")
        or file_config.get("MASTERDB_API_KEY")
        or os.getenv("MASTERDB_SEARCH_KEY")
        or os.getenv("MASTERDB_API_KEY")
        or os.getenv("SEARCH_KEY")
    )
    index_name = (
        file_config.get("INDEX_NAME")
        or file_config.get("MASTERDB_INDEX_NAME")
        or os.getenv("MASTERDB_INDEX_NAME")
        or os.getenv("INDEX_NAME")
    )

    missing = [
        name
        for name, value in {
            "SEARCH_ENDPOINT": endpoint,
            "SEARCH_KEY": api_key,
            "INDEX_NAME": index_name,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(
            "Missing MasterDB Azure Search configuration: "
            + ", ".join(missing)
        )

    return endpoint, api_key, index_name


@lru_cache(maxsize=1)
def get_search_client():
    endpoint, api_key, index_name = _get_config()
    return SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(api_key)
    )


def extract_top_k(query, default_k=5, max_k=20):
    """
    Dynamically detect requested result count.

    Supports:
    - top 8 laws
    - list top 10 acts
    - give me 6 sections
    - show 7 laws
    - provide 12 acts
    """
    query = query.lower()

    patterns = [
        r"top\s+(\d+)",
        r"list\s+(?:top\s+)?(\d+)",
        r"give\s+(?:me\s+)?(\d+)",
        r"show\s+(?:me\s+)?(\d+)",
        r"provide\s+(\d+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            k = int(match.group(1))
            return min(k, max_k)

    return default_k


def hybrid_search(user_query, query_embedding, top_k=None, use_filters=True):
    if top_k is None:
        top_k = extract_top_k(user_query)

    filters, clean_query = extract_filters(user_query)
    azure_filter = build_azure_filter(filters)
    search_text = clean_query if clean_query else user_query

    vector_query = VectorizedQuery(
        vector=query_embedding,
        k_nearest_neighbors=top_k,
        fields="embedding"
    )

    results = get_search_client().search(
        search_text=search_text,
        search_fields=["act", "text"],
        vector_queries=[vector_query],
        filter=azure_filter if use_filters else None,
        top=top_k
    )

    output = []
    for result in results:
        output.append({
            "id": result["id"],
            "act": result.get("act"),
            "jurisdiction": result.get("jurisdiction"),
            "doc_id": result.get("doc_id"),
            "date": result.get("date"),
            "translated": result.get("translated"),
            "score": result.get("@search.score"),
            "text": result.get("text")
        })

    return output
