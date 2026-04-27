import faiss
import numpy as np

index = None
texts = []
versions = []

def init(dim=1536):
    global index
    index = faiss.IndexFlatL2(dim)

def store(chunks, embeddings, version):
    global texts, versions

    vecs = np.array(embeddings).astype("float32")
    index.add(vecs)

    texts.extend(chunks)
    versions.extend([version] * len(chunks))

def search(query_embedding, version, top_k=5):
    vec = np.array([query_embedding]).astype("float32")

    D, I = index.search(vec, top_k)

    results = []
    for i in I[0]:
        if i < len(texts) and versions[i] == version:
            results.append(texts[i])

    return results