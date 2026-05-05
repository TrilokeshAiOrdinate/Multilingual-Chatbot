import json
from sentence_transformers import SentenceTransformer


# Load model (384-dim vectors)
model = SentenceTransformer("all-MiniLM-L6-v2")

input_file = "legal_dictionary_fixed_issue_1_2.json"
output_file = "legal_dictionary_with_embeddings.json"


# Load cleaned legal dictionary
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)


# Combine term + definition for embedding ONLY
def build_embedding_input(term, entry):
    definition = entry.get("definition", "").strip()
    return f"{term}. {definition}".strip()


terms = list(data.keys())
texts = [build_embedding_input(term, data[term]) for term in terms]

print(f"Generating embeddings for {len(texts)} legal terms...")


# Generate embeddings
embeddings = model.encode(
    texts,
    batch_size=32,
    show_progress_bar=True,
    convert_to_numpy=True,
    normalize_embeddings=True
)


# Attach embeddings back to dictionary entries
for term, emb in zip(terms, embeddings):
    data[term]["embedding"] = emb.tolist()


# Save
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)


print("Embeddings generated using term + definition and saved.")
