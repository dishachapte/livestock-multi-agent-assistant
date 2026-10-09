"""Farm memory search: finds past incidents that share words with the farmer's question.

Simple keyword matching on purpose. Keywords count double, so a match on
"milk" or "fever" ranks higher than a word that only appears in the summary.
"""
import re

from sqlalchemy.orm import Session

from backend import models as m

STOPWORDS = {
    "the", "and", "for", "with", "what", "why", "how", "is", "are", "was", "were",
    "this", "that", "our", "my", "has", "have", "had", "about", "should", "would",
    "could", "can", "any", "from", "after", "before", "who", "when", "where",
    "which", "there", "their", "them", "they", "cow", "cows", "farm", "does", "due",
}


def tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 3 and w not in STOPWORDS}


def search_memory(db: Session, query: str, limit: int = 3) -> list[dict]:
    query_terms = tokenize(query)
    if not query_terms:
        return []

    results = []
    for incident in db.query(m.FarmMemory).all():
        keywords = {k.strip().lower() for k in incident.keywords.split(",") if k.strip()}
        other_terms = tokenize(incident.title) | tokenize(incident.summary)

        keyword_hits = query_terms & keywords
        other_hits = query_terms & other_terms
        score = 2 * len(keyword_hits) + len(other_hits)

        if score > 0:
            results.append({
                "id": incident.id,
                "title": incident.title,
                "summary": incident.summary,
                "outcome": incident.outcome,
                "matched_terms": sorted(keyword_hits | other_hits),
                "score": score,
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]
