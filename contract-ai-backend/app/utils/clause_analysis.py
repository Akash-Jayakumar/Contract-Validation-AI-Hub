def analyze_contract(text: str):
    """Very simple rule-based contract checklist (extendable with LLMs later)"""
    checklist = {
        "confidentiality_clause": "confidentiality" in text.lower(),
        "liability_clause": "liability" in text.lower(),
        "payment_terms": "payment" in text.lower(),
        "intellectual_property": "intellectual property" in text.lower(),
        "termination_clause": "termination" in text.lower(),
    }
    return checklist