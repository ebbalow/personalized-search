from elasticsearch import Elasticsearch
from datetime import datetime
from collections import Counter
import re

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

def register_or_load(username):

    ensure_profile_index()
    try:
        doc = client.get(index=PROFILE_INDEX, id=username)
        print(f"Welcome back, {username}!")
        return doc["_source"]
    except:
        print(f"New user '{username}' created.")
        profile = {
            "username": username,
            "searches": [],
            "top_terms": []
        }
        client.index(index=PROFILE_INDEX, id=username, document=profile)
        return profile

def log_click(profile, query, clicked_title, clicked_id, clicked_body):

    profile["searches"].append({
        "query": query,
        "clicked_title": clicked_title,
        "clicked_id": clicked_id,
        "timestamp": datetime.now().isoformat()
    })

    profile["searches"] = profile["searches"][-20:]
    profile["top_terms"] = extract_top_terms(profile)

    client.index(index=PROFILE_INDEX, id=profile["username"], document=profile)

def extract_top_terms(profile):
    # get chosen article and find the most common words in it
    all_text = ""
    for search in profile["searches"]:

        try:
            doc = client.get(index="wikipedia", id=search["clicked_id"])
            all_text += " " + doc["_source"]["body"]
        except:
            pass
    words = re.findall(r'\b[a-zA-ZåäöÅÄÖ]{4,}\b', all_text.lower())

    stopwords = {
        "som", "och", "den", "det", "att", "inte", "för", "med", "från",
        "till", "även", "samt", "utan", "under", "över", "eller", "också",
        "hade", "vara", "denna", "detta", "efter", "inom", "sedan", "många",
        "andra", "vilka", "ville", "bland", "deras", "hans", "hennes", "stor",
        "jag", "mig", "min", "mitt", "mina", "du", "dig", "din", "ditt", "dina",
        "han", "honom", "hon", "henne", "denne", "denna", "dem", "oss", "vi",
        "er", "ert", "era", "ni", "sig", "sin", "sitt", "sina", "var", "vid",
        "vidare", "vår", "vårt", "våra", "vad", "vem", "vilken", "vilket",
        "vars", "där", "då", "här", "varför", "hur", "nu", "då", "när", "därför",
        "ju", "så", "ut", "in", "på", "av", "om", "mot", "hos", "genom", "mot",
        "bakom", "mellan", "före", "emot", "trots", "blir", "blev", "blivit",
        "bli", "är", "varit", "ha", "har", "hade", "haft", "skulle", "skall",
        "ska", "måste", "kunde", "kunna", "kan", "man", "alla", "allt", "alla",
        "någon", "något", "några", "inget", "inga", "ingen", "ett", "en", "man",
        "blir", "idag", "mycket", "mer", "mest", "bara", "lite", "få", "mer",
        "än", "eller", "men", "dessa", "några", "mycket", "själv", "redan",
        "just", "inför", "alltid", "aldrig", "ofta", "kanske", "ens", "heller"
    }

    words = [w for w in words if w not in stopwords]

    top = [word for word, count in Counter(words).most_common(20)]
    return top

def get_profile_boost(profile):
    if not profile["top_terms"]:
        return None  # new user
    return " ".join(profile["top_terms"])