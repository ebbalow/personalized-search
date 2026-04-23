import requests
from elasticsearch import Elasticsearch

client = Elasticsearch("http://localhost:9200")

session = requests.Session()
session.headers.update({
    "User-Agent": "SearchEngineProject/1.0 (hugoan@kth.se)"
})


def get_top_swedish_titles(n=3000):
    titles = set()


    months = ["01", "02", "03", "04", "05", "06", "07","08","09","10","11","12"]

    for month in months:
        url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/sv.wikipedia/all-access/2024/{month}/all-days"

        try:
            response = session.get(url).json()
            articles = response["items"][0]["articles"]

            for a in articles:
                title = a["article"].replace("_", " ")
                if ":" not in title and title != "Huvudsida":
                    titles.add(title)

                # Stop as soon as we hit our target goal
                if len(titles) >= n:
                    print(f"Got {len(titles)} titles")
                    return list(titles)

        except Exception as e:
            print(f"Error fetching month {month}: {e}")

    # If we run out of months before hitting the target, just return what we have
    print(f"Got {len(titles)} unique titles from the API")
    return list(titles)

def fetch_article_content(titles):
    wiki_url = "https://sv.wikipedia.org/w/api.php"
    articles = []

    for i, title in enumerate(titles):
        try:
            params = {
                "action": "query",
                "format": "json",
                "titles": title,
                "prop": "extracts|info|links",
                "explaintext": True,
                "inprop": "url",
                "pllimit": 100
            }

            response = session.get(wiki_url, params=params).json()
            pages = response["query"]["pages"]

            for page_id, page in pages.items():
                if page_id == "-1":
                    continue
                if "extract" not in page or not page["extract"].strip():
                    continue

                links = [l["title"] for l in page.get("links", [])]

                articles.append({
                    "id": page_id,
                    "title": page["title"],
                    "body": page["extract"],
                    "url": page.get("fullurl", ""),
                    "links": links,
                    "pagerank": 0.0
                })

        except Exception as e:
            print(f"  Error fetching '{title}': {e}")

        if (i + 1) % 50 == 0:
            print(f"  Fetched {i+1}/{len(titles)} — indexed so far: {len(articles)}")

    return articles

def index_articles(articles):
    if client.indices.exists(index="wikipedia"):
        client.indices.delete(index="wikipedia")

    client.indices.create(index="wikipedia", mappings={
        "properties": {
            "title":    {"type": "text"},
            "body":     {"type": "text", "analyzer": "swedish"},
            "url":      {"type": "keyword"},
            "links":    {"type": "keyword"},
            "pagerank": {"type": "float"}
        }
    })

    for article in articles:
        client.index(index="wikipedia", id=article["id"], document=article)

    client.indices.refresh(index="wikipedia")
    print(f"\nDone! Indexed {len(articles)} articles.")

if __name__ == "__main__":
    titles = get_top_swedish_titles(3000)
    articles = fetch_article_content(titles)
    index_articles(articles)
