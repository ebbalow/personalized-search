import subprocess
from elasticsearch import Elasticsearch


def setup_and_run():
    try:
        client = Elasticsearch("http://localhost:9200")

        # 1. Check if the index exists. If not, fetch articles.
        if not client.indices.exists(index="wikipedia"):
            print("Index missing. Running fetch_wikipedia.py...")
            subprocess.run(["python", "fetch_wikipedia.py"], check=True)
        else:
            print("Index found. Skipping fetch.")

        # 2. Check if PageRank is calculated.
        res = client.search(index="wikipedia", size=1, sort=[{"pagerank": "desc"}])

        if res["hits"]["hits"]:
            highest_pr = res["hits"]["hits"][0]["_source"].get("pagerank", 0.0)

            # If the highest score is still 0.0, it definitely hasn't run yet.
            if highest_pr == 0.0:
                print("PageRank is 0.0. Running compute_pagerank.py...")
                subprocess.run(["python", "compute_pagerank.py"], check=True)
            else:
                print(f"PageRank already computed (Max score: {highest_pr}). Skipping calculation.")

        # 3. Always launch the search interface.
        print("\nLaunching search...")
        subprocess.run(["python", "search.py"])

    except Exception as e:
        print(f"Error connecting to Elasticsearch or running scripts: {e}")
        print("Make sure Elasticsearch is running on localhost:9200.")


if __name__ == "__main__":
    setup_and_run()