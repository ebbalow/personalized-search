import re
import requests
from collections import Counter
from datetime import datetime
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch
import math
from datetime import datetime

# Initialize Elasticsearch Client
client = Elasticsearch("http://localhost:9200")

PROFILE_INDEX = "user_profiles"


def ensure_profile_index():
    if not client.indices.exists(index=PROFILE_INDEX):
        client.indices.create(index=PROFILE_INDEX, mappings={
            "properties": {
                "username": {"type": "keyword"},
                "searches": {"type": "object"},
                "seed_terms": {"type": "keyword"},
                "query_terms": {"type": "keyword"},
                "long_term_terms": {"type": "keyword"},
                "session_terms": {"type": "keyword"},
                "session_clicks": {"type": "keyword"}
            }
        })


def clean_and_extract(text):
    """
    Passes raw text to Elasticsearch to natively remove Swedish stop words
    and apply stemming, returning the most frequent meaningful terms.
    """
    if not text or not text.strip():
        return []

    try:
        # Ask Elasticsearch to analyze the text using its native Swedish rules
        response = client.indices.analyze(
            body={
                "analyzer": "swedish",
                "text": text
            }
        )

        # Extract the tokens (words) returned by ES
        # We can also add a quick length filter to drop single characters
        tokens = [token["token"] for token in response.get("tokens", []) if len(token["token"]) > 2]

        # Count and return the top 20
        return [word for word, count in Counter(tokens).most_common(20)]

    except Exception as e:
        print(f"Error analyzing text with ES: {e}")
        return []


def seed_profile_logic(username):
    """Internal helper to ask user for seeding data."""
    print(f"\n--- New User Setup: {username} ---")
    print("Would you like to seed your profile with interests?")
    choice = input("Enter '1' for Bio/Text, '2' for URL, or press Enter to skip: ").strip()

    raw_text = ""
    if choice == "1":
        raw_text = input("Paste your bio/interests text: ")
    elif choice == "2":
        url = input("Enter URL: ")
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for s in soup(["script", "style", "nav", "header", "footer"]):
                s.extract()
            raw_text = soup.get_text(separator=' ')
        except Exception as e:
            print(f"Error fetching URL: {e}")

    if raw_text:
        return clean_and_extract(raw_text)
    return []


def register_or_load(username):
    ensure_profile_index()
    try:
        doc = client.get(index=PROFILE_INDEX, id=username)
        profile = doc["_source"]

        profile.setdefault("seed_terms", [])
        profile.setdefault("query_terms", [])
        profile.setdefault("long_term_terms", [])
        profile.setdefault("session_terms", [])
        profile.setdefault("session_clicks", [])
        profile.setdefault("searches", [])

        return profile
    except Exception:
        initial_terms = seed_profile_logic(username)
        profile = {
            "username": username,
            "searches": [],
            "seed_terms": initial_terms,
            "query_terms": [],
            "long_term_terms": [],
            "session_terms": [],
            "session_clicks": []
        }
        client.index(index=PROFILE_INDEX, id=username, document=profile)
        return profile



def extract_top_terms(doc_ids, top_n=20):
    """
    Fetches term vectors from Elasticsearch and calculates TF-IDF
    to find the most statistically significant words in a set of documents.
    """
    if not doc_ids:
        return []

    try:
        # mtermvectors fetches statistics for multiple documents at once
        response = client.mtermvectors(
            index="wikipedia",
            ids=list(set(doc_ids)), # Use set() to avoid processing duplicates
            term_statistics=True,
            field_statistics=True,
            fields=["body"]
        )
    except Exception as e:
        print(f"Error fetching term vectors: {e}")
        return []

    term_scores = {}
    total_docs = None

    # Loop through the documents returned by Elasticsearch
    for doc in response.get("docs", []):
        if "term_vectors" not in doc or "body" not in doc["term_vectors"]:
            continue

        # Get the total number of documents in the index (used for IDF)
        field_stats = doc["term_vectors"]["body"]["field_statistics"]
        if total_docs is None:
            total_docs = field_stats["doc_count"]

        terms = doc["term_vectors"]["body"]["terms"]

        # Calculate TF-IDF for each term
        for term, stats in terms.items():
            # Basic cleanup: ignore short words or numbers
            if len(term) < 2 or not term.isalpha():
                continue

            tf = stats["term_freq"]    # How many times it appears in THIS document
            df = stats["doc_freq"]     # How many documents it appears in ACROSS THE INDEX

            # Standard TF-IDF calculation
            idf = math.log(total_docs / (df + 1)) + 1
            tfidf_score = tf * idf

            # Sum scores across all the clicked documents in this batch
            term_scores[term] = term_scores.get(term, 0.0) + tfidf_score

    # Sort terms by their highest accumulated TF-IDF score
    sorted_terms = sorted(term_scores.items(), key=lambda x: x[1], reverse=True)
    return [term for term, score in sorted_terms[:top_n]]


def log_search_query(profile, query):
    """
    Saves the typed query terms to the user profile immediately,
    so they influence subsequent searches even if no links are clicked.
    """
    # Use your Elasticsearch text analyzer to strip stop words from the query
    new_query_terms = clean_and_extract(query)

    if new_query_terms:
        profile.setdefault("query_terms", [])
        profile["query_terms"].extend(new_query_terms)
        profile["query_terms"] = profile["query_terms"][-20:]  # Keep the last 20 words

        # Save the updated profile to Elasticsearch
        client.index(index=PROFILE_INDEX, id=profile["username"], document=profile)

def log_click(profile, query, clicked_title, clicked_id, clicked_body):
    # 1. Update searches (Long-term profile)
    profile.setdefault("searches", [])
    profile["searches"].append({
        "query": query,
        "clicked_id": clicked_id,
        "timestamp": datetime.now().isoformat()
    })
    profile["searches"] = profile["searches"][-20:]



    # 3. Update session clicks (Short-term profile)
    profile.setdefault("session_clicks", [])
    profile["session_clicks"].append(clicked_id)
    profile["session_clicks"] = profile["session_clicks"][-5:]

    # 4. Extract IDs for ES Term Vectors
    long_term_ids = [s["clicked_id"] for s in profile["searches"]]
    session_ids = profile["session_clicks"]

    # 5. Use Elasticsearch for heavy text extraction (Our new logic)
    profile["long_term_terms"] = extract_top_terms(long_term_ids, top_n=20)
    profile["session_terms"] = extract_top_terms(session_ids, top_n=10)

    # 6. Save back to the index
    client.index(index=PROFILE_INDEX, id=profile["username"], document=profile)


"""def log_click(profile, query, clicked_title, clicked_id, clicked_body):
    profile["searches"].append({
        "query": query,
        "clicked_id": clicked_id,
        "timestamp": datetime.now().isoformat()
    })
    profile["searches"] = profile["searches"][-20:]

    profile.setdefault("session_clicks", [])
    profile["session_clicks"].append(clicked_id)
    profile["session_clicks"] = profile["session_clicks"][-5:]

    long_text = ""
    for search in profile["searches"]:
        try:
            doc = client.get(index="wikipedia", id=search["clicked_id"])
            long_text += " " + doc["_source"]["body"]
        except:
            pass

    session_text = ""
    for doc_id in profile["session_clicks"]:
        try:
            doc = client.get(index="wikipedia", id=doc_id)
            session_text += " " + doc["_source"]["body"]
        except:
            pass

    # Update long-term and session-based interest terms
    profile["long_term_terms"] = clean_and_extract(long_text)
    profile["session_terms"] = clean_and_extract(session_text)
    client.index(index=PROFILE_INDEX, id=profile["username"], document=profile)"""


def get_profile_boost(profile):
    """
    Builds a weighted boost string from:
    - seed_terms: initial interests
    - long_term_terms: stable interests over time
    - session_terms: current short-term interests
    """
    BIO_WEIGHT = 3  # How many times to repeat bio words
    LONG_TERM_WEIGHT = 3
    SESSION_WEIGHT = 5

    boost_parts = []

    # Add Bio terms
    for term in profile.get("seed_terms", []):
        boost_parts.extend([term] * BIO_WEIGHT)

    # Add Click terms
    # Long-term terms: what the user often clicks on over time
    for term in profile.get("long_term_terms", []):
        boost_parts.extend([term] * LONG_TERM_WEIGHT)

    # Session terms: what the user seems interested in right now
    for term in profile.get("session_terms", []):
        boost_parts.extend([term] * SESSION_WEIGHT)

    if not boost_parts:
        return None

    return " ".join(boost_parts)
