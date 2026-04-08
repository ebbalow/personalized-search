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
                "top_terms": {"type": "keyword"}
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
        return doc["_source"]
    except Exception:
        initial_terms = seed_profile_logic(username)
        profile = {
            "username": username,
            "searches": [],
            "seed_terms": initial_terms,  
            "click_terms": []            
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
    
    all_text = ""
    for search in profile["searches"]:
        try:
            doc = client.get(index="wikipedia", id=search["clicked_id"])
            all_text += " " + doc["_source"]["body"]
        except: pass
    
    # Update ONLY the click_terms bucket
    profile["click_terms"] = clean_and_extract(all_text)
    client.index(index=PROFILE_INDEX, id=profile["username"], document=profile)





def get_profile_boost(profile):
    """
    Returns a weighted boost string. 
    Terms from the bio are repeated more often if BIO_WEIGHT is higher.
    """
    BIO_WEIGHT = 3    # How many times to repeat bio words
    CLICK_WEIGHT = 1  # How many times to repeat click words
    
    boost_parts = []
    
    # Add Bio terms
    for term in profile.get("seed_terms", []):
        boost_parts.extend([term] * BIO_WEIGHT)
        
    # Add Click terms
    for term in profile.get("click_terms", []):
        boost_parts.extend([term] * CLICK_WEIGHT)
        
    if not boost_parts:
        return None
        
    return " ".join(boost_parts)