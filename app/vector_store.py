import numpy as np

VECTOR_DB = []


def reset(version=None):
    if version is None:
        VECTOR_DB.clear()
        return

    VECTOR_DB[:] = [item for item in VECTOR_DB if item["version"] != version]


def store(chunks, embeddings, version, replace=False):
    if replace:
        reset(version)

    for i in range(len(chunks)):
        VECTOR_DB.append({
            "text": chunks[i],
            "embedding": embeddings[i],
            "version": version
        })


def cosine_similarity(a, b):
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0

    return np.dot(a, b) / (norm_a * norm_b)


def search(query_embedding, version, top_k=5):
    results = []

    for item in VECTOR_DB:
        if item["version"] != version:
            continue

        score = cosine_similarity(query_embedding, item["embedding"])
        results.append((score, item["text"]))

    results.sort(reverse=True)
    return [r[1] for r in results[:top_k]]
