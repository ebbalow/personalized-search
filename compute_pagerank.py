import networkx as nx
from elasticsearch import Elasticsearch
import math

client = Elasticsearch("http://localhost:9200")

def compute_and_store_pagerank():

    results = client.search(index="wikipedia", query={"match_all": {}}, size=10000)
    docs = results["hits"]["hits"]
    print(f"Loaded {len(docs)} articles from ES")

    title_to_id = {doc["_source"]["title"]: doc["_id"] for doc in docs}

    G = nx.DiGraph()

    for doc in docs:
        G.add_node(doc["_source"]["title"])


    for doc in docs:
        src = doc["_source"]["title"]
        for link in doc["_source"].get("links", []):
            if link in title_to_id:  # only edges to articles we have
                G.add_edge(src, link)

    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    pagerank = nx.pagerank(G, alpha=0.85)

    # --- NEW LOG-SCALING LOGIC ---
    # 1. PageRank scores are tiny decimals. We multiply by 1,000,000 so they
    #    become whole numbers, and add 1 so we never try to calculate log(0).
    log_scaled = {
        title: math.log10((score * 1000000) + 1)
        for title, score in pagerank.items()
    }

    # 2. (Optional but recommended) We do a Min-Max on the LOG scores.
    #    This safely bounds the PageRank influence between 0.0 and 1.0,
    #    making it much easier to balance with BM25 in your search.py script.
    max_log = max(log_scaled.values()) if log_scaled else 1.0
    min_log = min(log_scaled.values()) if log_scaled else 0.0

    normalized = {
        title: (score - min_log) / (max_log - min_log) if max_log > min_log else 0.0
        for title, score in log_scaled.items()
    }
    # -----------------------------

    for doc in docs:
        title = doc["_source"]["title"]
        score = normalized.get(title, 0.0)

        # Updating the document in Elasticsearch.
        # (Note: if this throws an error depending on your ES python client version,
        # change `doc=...` to `body={"doc": ...}`)
        client.update(index="wikipedia", id=doc["_id"], doc={"pagerank": score})



    client.indices.refresh(index="wikipedia")
    print("PageRank scores stored!")


    top = sorted(normalized.items(), key=lambda x: x[1], reverse=True)[:10]
    print("\nTop 10 articles by PageRank:")
    for i, (title, score) in enumerate(top):
        print(f"{i+1}. {score:.4f} — {title}")

if __name__ == "__main__":
    compute_and_store_pagerank()

"""max_score = max(pagerank.values())
    min_score = min(pagerank.values())
    normalized = {
        title: (score - min_score) / (max_score - min_score)
        for title, score in pagerank.items()
    }

    for doc in docs:
        title = doc["_source"]["title"]
        score = normalized.get(title, 0.0)
        client.update(index="wikipedia", id=doc["_id"], doc={"pagerank": score})"""
