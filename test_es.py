from elasticsearch import Elasticsearch

client = Elasticsearch("http://localhost:9200")

alpha = float(input("Choose alpha (higher = more PR influence): "))
search_word = input ("Choose search word: ")

results = client.search(index="wikipedia",query={
    "match": { "body": search_word }
}, size=10,sort=[{"pagerank": "desc"}])

print("Top 10 articles by stored PageRank score:")
for hit in results["hits"]["hits"]:
    print(f"  {hit['_source']['pagerank']:.4f} — {hit['_source']['title']}")

print("\n--- Search WITHOUT PageRank ---")
results_bm25 = client.search(index="wikipedia", query={
    "match": { "body": search_word }
}, size=10)
for hit in results_bm25["hits"]["hits"]:
    print(f"  score={hit['_score']:.4f} pr={hit['_source']['pagerank']:.4f} — {hit['_source']['title']}")

print("\n--- Search WITH PageRank ---")
results_pr = client.search(index="wikipedia", body={
    "query": {
        "script_score": {
            "query": {
                "match": { "body": search_word } #BM25base
            },
            "script": {
                "source": "_score * (1 + params.alpha * doc['pagerank'].value)",
                "params": {
                    "alpha": alpha #higher = more PageRank influence
                }
            }
        }
    },
    "size": 10
})
for hit in results_pr["hits"]["hits"]:
    print(f"  score={hit['_score']:.4f} pr={hit['_source']['pagerank']:.4f} — {hit['_source']['title']}")