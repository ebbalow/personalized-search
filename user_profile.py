import re
import requests
from collections import Counter
from datetime import datetime
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch

# Initialize Elasticsearch Client
client = Elasticsearch("http://localhost:9200")


PROFILE_INDEX = "user_profiles"

def ensure_profile_index():
    if not client.indices.exists(index=PROFILE_INDEX):
        client.indices.create(index=PROFILE_INDEX, mappings={
            "properties": {
                "username":  {"type": "keyword"},
                "searches":  {"type": "object"},
                "seed_terms": {"type": "keyword"},
                "query_terms": {"type": "keyword"},
                "long_term_terms": {"type": "keyword"},
                "session_terms": {"type": "keyword"},
                "session_clicks": {"type": "keyword"}
            }
        })

def clean_and_extract(text):
    """Turns raw text into the top 20 meaningful terms."""
    words = re.findall(r'\b[a-zA-ZåäöÅÄÖ]{4,}\b', text.lower())
    stopwords = {
        "som", "och", "den", "det", "att", "inte", "för", "med", "från",
        "till", "även", "samt", "utan", "under", "över", "eller", "också",
        "hade", "vara", "denna", "detta", "efter", "inom", "sedan", "många",
        "andra", "vilka", "ville", "bland", "deras", "hans", "hennes", "stor",
        "jag", "mig", "min", "mitt", "mina", "du", "dig", "din", "ditt", "dina",
        "han", "honom", "hon", "henne", "denne", "denna", "dem", "oss", "vi",
        "er", "ert", "era", "ni", "sig", "sin", "sitt", "sina", "var", "vid",
        "vidare", "vår", "vårt", "våra", "vad", "vem", "vilken", "vilket",
        "vars", "där", "då", "här", "varför", "hur", "nu", "när", "därför",
        "ju", "så", "ut", "in", "på", "av", "om", "mot", "hos", "genom",
        "bakom", "mellan", "före", "emot", "trots", "blir", "blev", "blivit",
        "bli", "är", "varit", "ha", "har", "hade", "haft", "skulle", "skall",
        "ska", "måste", "kunde", "kunna", "kan", "man", "alla", "allt",
        "någon", "något", "några", "inget", "inga", "ingen", "ett", "en",
        "idag", "mycket", "mer", "mest", "bara", "lite", "få", "än", "men", 
        "dessa", "själv", "redan", "just", "inför", "alltid", "aldrig", 
        "ofta", "kanske", "ens", "heller"
    }
    filtered = [w for w in words if w not in stopwords]
    return [word for word, count in Counter(filtered).most_common(20)]

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

def log_click(profile, query, clicked_title, clicked_id, clicked_body):
    profile["searches"].append({ 
        "query": query,
        "clicked_id": clicked_id,
        "timestamp": datetime.now().isoformat()
    })
    profile["searches"] = profile["searches"][-20:]  

    # 2. Extract terms from the current query and save them
    query_terms = clean_and_extract(query)
    profile.setdefault("query_terms", [])
    profile["query_terms"].extend(query_terms)
    profile["query_terms"] = profile["query_terms"][-20:]

    profile.setdefault("session_clicks", [])
    profile["session_clicks"].append(clicked_id)
    profile["session_clicks"] = profile["session_clicks"][-5:]
    
    long_text = ""
    for search in profile["searches"]:
        try:
            doc = client.get(index="wikipedia", id=search["clicked_id"])
            long_text += " " + doc["_source"]["body"]
        except: pass

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
    client.index(index=PROFILE_INDEX, id=profile["username"], document=profile)





def get_profile_boost(profile):
    """
    Builds a weighted boost string from:
    - seed_terms: initial interests
    - long_term_terms: stable interests over time
    - session_terms: current short-term interests
    """
    BIO_WEIGHT = 3    # How many times to repeat bio words
    QUERY_WEIGHT = 2
    LONG_TERM_WEIGHT = 3
    SESSION_WEIGHT = 5
    
    boost_parts = []
    
    # Add Bio terms
    for term in profile.get("seed_terms", []):
        boost_parts.extend([term] * BIO_WEIGHT)
    
    # Query terms
    for term in profile.get("query_terms", []):
        boost_parts.extend([term] * QUERY_WEIGHT)
        
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