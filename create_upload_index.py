
import os
import json
import uuid
import sys
from dotenv import load_dotenv

from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile
)
from azure.core.credentials import AzureKeyCredential

# =========================
# LOAD ENV
# =========================
load_dotenv()

SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("SEARCH_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

if not SEARCH_ENDPOINT or not SEARCH_KEY or not INDEX_NAME:
    raise ValueError("❌ Missing environment variables in .env")

# =========================
# CREATE INDEX
# =========================
def create_index():
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=AzureKeyCredential(SEARCH_KEY)
    )

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),

        SearchField(name="term", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="part_of_speech", type=SearchFieldDataType.String, filterable=True),
        SearchField(name="definition", type=SearchFieldDataType.String, searchable=True),

        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=384,
            vector_search_profile_name="vector-profile"
        )
    ]

    vector_search = VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-config"
            )
        ],
        algorithms=[
            HnswAlgorithmConfiguration(name="hnsw-config")
        ]
    )

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search
    )

    index_client.create_or_update_index(index)
    print("✅ Index created/updated")


# =========================
# LOAD DATA
# =========================
def load_data(json_file):
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"❌ File not found: {json_file}")

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = []

    for term, value in data.items():
        documents.append({
            "id": str(uuid.uuid4()),
            "term": term,
            "part_of_speech": value.get("part_of_speech", ""),
            "definition": value.get("definition", ""),
            "embedding": value.get("embedding", [])
        })

    print(f"📦 Loaded {len(documents)} documents")
    return documents


# =========================
# UPLOAD DATA
# =========================
def upload_documents(json_file):
    client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )

    documents = load_data(json_file)

    batch_size = 500

    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        result = client.upload_documents(documents=batch)

        success = sum([1 for r in result if r.succeeded])
        print(f"✅ Uploaded {success}/{len(batch)} (Total: {i + len(batch)})")


# =========================
# MAIN CLI
# =========================
def main():
    if len(sys.argv) < 2:
        print("""
Usage:
  python script.py create-index
  python script.py upload <json_file>
  python script.py all <json_file>
""")
        return

    command = sys.argv[1]

    if command == "create-index":
        create_index()

    elif command == "upload":
        if len(sys.argv) < 3:
            print("❌ Provide JSON file")
            return
        upload_documents(sys.argv[2])

    elif command == "all":
        if len(sys.argv) < 3:
            print("❌ Provide JSON file")
            return
        create_index()
        upload_documents(sys.argv[2])

    else:
        print("❌ Unknown command")


if __name__ == "__main__":
    main()