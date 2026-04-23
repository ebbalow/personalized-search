

from elasticsearch import Elasticsearch
from user_profile import register_or_load, log_click, get_profile_boost


client = Elasticsearch("http://localhost:9200")


def search(query, profile,currentsearch_boost,bio_weight,search_weight,history_weight,session_weight,pagerank_weight, n=10):
    #the document MUST match the users typed query
    must_clauses = [
        {
            "match": {
                "body": {
                    "query": query,
                    "boost": currentsearch_boost
                }
            }
        }
    ]

    # Personalization: the document SHOULD match profile terms for bonus points
    should_clauses = []

    # Bio/Seed terms
    for term in profile.get("seed_terms", [])[:5]:
        should_clauses.append({"term": {"body": {"value": term, "boost": bio_weight}}})

    #Query terms get a boost of 2.0
    for term in profile.get("query_terms", [])[:5]:
        should_clauses.append({"term": {"body": {"value": term, "boost": search_weight}}})

    # Long-term click interests get a boost of 3.0
    for term in profile.get("long_term_terms", [])[:5]:
        should_clauses.append({"term": {"body": {"value": term, "boost": history_weight}}})

    # Session (immediate) click interests get a strong boost of 5.0
    for term in profile.get("session_terms", [])[:5]:
        should_clauses.append({"term": {"body": {"value": term, "boost": session_weight}}})


    results = client.search(index="wikipedia", body={
        "query": {
            "script_score": {
                "query": {
                    "bool": {
                        "must": must_clauses,
                        "should": should_clauses,
                        # This ensures documents don't HAVE to match profile terms to be returned
                        "minimum_should_match": 0
                    }
                },
                "script": {

                    "source": "_score * (1 + params.alpha * doc['pagerank'].value)",
                    "params": {"alpha": pagerank_weight}
                }
            }
        },
        "size": n
    })

    return results["hits"]["hits"]


def run(profile,currentsearch_boost,bio_weight,search_weight,history_weight,session_weight,pagerank_weight):
    print(f"\nLogged in as: {profile['username']}")

    seed = profile.get("seed_terms", [])
    long_term = profile.get("long_term_terms", [])
    session = profile.get("session_terms", [])

    print(f"Seed Interests:      {seed if seed else 'none'}")
    print(f"Long-term Interests: {long_term if long_term else 'none'}")
    print(f"Session Interests:   {session if session else 'none'}\n")
    print(f"past querys: {profile.get('query_terms', []) or 'none'}\n")

    while True:
        query = input("Search (or 'quit'): ").strip()
        if query.lower() == "quit":
            break
        from user_profile import log_search_query
        log_search_query(profile, query)

        hits = search(query, profile,currentsearch_boost,bio_weight,search_weight,history_weight,session_weight,pagerank_weight)

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
                print("Updated profile:")
                print(f"Seed Interests:      {profile.get('seed_terms', []) or 'none'}")
                print(f"Long-term Interests: {profile.get('long_term_terms', []) or 'none'}")
                print(f"Session Interests:   {profile.get('session_terms', []) or 'none'}")
                print(f"past querys: {profile.get('query_terms', []) or 'none'}\n")

if __name__ == "__main__":
    currentsearch_boost = 10.0
    bio_weight=0.1
    search_weight=0.2
    history_weight=0.1
    session_weight=0.5
    pagerank_weight=0.1
    username = input("Enter username: ").strip()
    profile = register_or_load(username)
    run(profile,currentsearch_boost,bio_weight,search_weight,history_weight,session_weight,pagerank_weight)
