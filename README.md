# Personalized information retrieval 

A personalized search engine which builds and maintains user profiles, and retrives Wikipedia articles and ranks search results based on the user profile. The user profile contains previous searches, links the user has interacted with as well as self-reported interest from the user when user is created. Search result are ranked based on BM25, PageRank and user profile boosting. 


### Requirements 

* Python 3.12 (?) 
* Python packages *collections*, *datetime*, *bs4*, *elasticsearch* eller *elasticsearch*, *requests*, *beautifulsoup4*, *networkx*
* Elasticsearch 8.x - [Install and run locally](https://github.com/elastic/start-local)


## Set up the program
Install the required python packages:

```bash
pip install elasticsearch requests beautifulsoup4 networkx
```

Make sure to configure your Elasticsearch password: 

```python 
client = Elasticsearch("http://localhost:9200", basic_auth=("elastic", "YOUR_PASSWORD"))
```
in the following files: `user_profile.py`, `search.py`, `fetch_wikipedia.py`, `compute_pagerank.py` 

## Run the program
To run the program, run `main.py`. If it is the first time running the code, the program will automatically run `fetch_wikipedia.py`to fetch and index the 1000 Swedish Wikipedia-articles. `compute_pagerank.py`is also runned, to compute PageRank-score for every article. The program will store the articles and their PageRank-score in an indice "Wikipedia" in your local elasticsearch. Once done, the PIR-system is ready for use. 


## How it works 
Once having run the program, running `main.py` will skip fetching the wikipedia articles and computing PageRank, and instead ask the user to enter their username. 

### New user 
If you're creating a new user-profile, simply writing your username will create a user profile. The program will ask *optionally* ask the user to:

- Insert cathagorical interest
- Insert a URL (can be any type of website of the users interests) 

This seeds the user profile with interest terms (`seed_terms`).

### Old user 

If the user in signing in again by using an old username, and their Bio interest together with Long-term Interests (20 searches bakåt 
20 vabligaste orden för 20 senaste sökningarna)
session 20 valigaste för 5 senastse sökningarna 


### Profile building 
As the user searches and clicks results, the system continuously updates:
- `searches` — Query terms the user has previously searched for,  and if the user clicks on a document the clicked document ID is also saved together with timestamps. 
- `long_term` — top 20 terms extracted from the bodies of clicked articles
- `query_terms` — top terms extracted from the user's past search queries

### Personalized Ranking
Search results are ranked using three signals combined:
1. **BM25** — standard term-based relevance (handled by Elasticsearch)
2. **PageRank** — importance of the article based on its links
3. **Profile boost** — terms from the user's profile are added as a `should` clause to boost relevant results

The weight of each signal can be tuned in `search.py` (alpha for PageRank) and `user_profile.py` (BIO_WEIGHT, CLICK_WEIGHT, QUERY_WEIGHT).

---
## Elasticsearch Indices

| Index | Description |
|---|---|
| `wikipedia` | Wikipedia articles with title, body, links, url, and pagerank |
| `user_profiles` | User profiles with seed_terms, click_terms, query_terms, and searches |
