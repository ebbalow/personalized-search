"""from elasticsearch import Elasticsearch

client = Elasticsearch("http://localhost:9200")

def search(query, n=100):
    results = client.search(index="wikipedia", query={
        "match": { "body": query }
    }, size=n)

    hits = results["hits"]["hits"]
    print(f"\nTop {len(hits)} results for '{query}':\n")
    for i, hit in enumerate(hits):
        print(f"{i+1}. [{hit['_score']:.4f}] {hit['_source']['title']}")
        print(f"   {hit['_source']['body'][:100]}...")
        print()

if __name__ == "__main__":
    query = input("Enter search query: ")
    search(query)"""

from elasticsearch import Elasticsearch
from user_profile import register_or_load, log_click, get_profile_boost


client = Elasticsearch("http://localhost:9200")


def search(query, profile, n=10):
    boost_terms = get_profile_boost(profile)

    if boost_terms:
        # personalized search: BM25 + PageRank + profile boost
        results = client.search(index="wikipedia", body={
            "query": {
                "script_score": {
                    "query": {
                        "bool": {
                            "must": {
                                "match": {"body": query}
                            },
                            "should": {
                                "match": {
                                    "body": {
                                        "query": boost_terms,
                                        "boost": 1.5  # profile influence
                                    }
                                }
                            }
                        }
                    },
                    "script": {
                        "source": "_score * (1 + params.alpha * doc['pagerank'].value)",
                        "params": {"alpha": 0.5}
                    }
                }
            },
            "size": n
        })
    else:
        #new user: plain BM25 + PageRank
        results = client.search(index="wikipedia", body={
            "query": {
                "script_score": {
                    "query": {"match": {"body": query}},
                    "script": {
                        "source": "_score * (1 + params.alpha * doc['pagerank'].value)",
                        "params": {"alpha": 0.5}
                    }
                }
            },
            "size": n
        })

    return results["hits"]["hits"]

def run(profile):
    print(f"\nLogged in as: {profile['username']}")
    
    bio = profile.get('seed_terms', [])
    clicks = profile.get('click_terms', [])
    print(f"Bio Interests:   {bio if bio else 'none'}")
    print(f"Click Interests: {clicks if clicks else 'none'}\n")

    while True:
        query = input("Search (or 'quit'): ").strip()
        if query.lower() == "quit":
            break

        hits = search(query, profile)

        if not hits:
            print("No results found.\n")
            continue

        # Show results
        print(f"\nTop {len(hits)} results:\n")
        for i, hit in enumerate(hits):
            print(f"  {i+1}. {hit['_source']['title']} (score={hit['_score']:.4f}, pr={hit['_source']['pagerank']:.4f})")


        print()
        choice = input("Click a result (1-10) or press Enter to skip: ").strip()

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(hits):
                clicked = hits[idx]
                log_click(
                    profile,
                    query,
                    clicked["_source"]["title"],
                    clicked["_id"],
                    clicked["_source"]["body"]
                )
                print(f"Logged click: {clicked['_source']['title']}\n")

if __name__ == "__main__":
    username = input("Enter username: ").strip()
    profile = register_or_load(username)
    run(profile)