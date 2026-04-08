import networkx as nx
from elasticsearch import Elasticsearch

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

    max_score = max(pagerank.values())
    min_score = min(pagerank.values())
    normalized = {
        title: (score - min_score) / (max_score - min_score)
        for title, score in pagerank.items()
    }

    for doc in docs:
        title = doc["_source"]["title"]
        score = normalized.get(title, 0.0)
        client.update(index="wikipedia", id=doc["_id"], doc={"pagerank": score})

    client.indices.refresh(index="wikipedia")
    print("PageRank scores stored!")


    top = sorted(normalized.items(), key=lambda x: x[1], reverse=True)[:10]
    print("\nTop 10 articles by PageRank:")
    for i, (title, score) in enumerate(top):
        print(f"{i+1}. {score:.4f} — {title}")

if __name__ == "__main__":
    compute_and_store_pagerank()