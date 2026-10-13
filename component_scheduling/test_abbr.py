import re

def looks_like_abbreviation_entry(name: str) -> bool:
    # E.g. "AI Artificial Intelligence", "ML Machine Learning", "NLP Natural Language Processing"
    # Usually starts with an acronym (2-5 uppercase letters), followed by the expanded words starting with the same letters,
    # OR just looks like a short capitalized string followed by longer words.
    
    parts = name.split()
    if len(parts) >= 2:
        first_word = parts[0].strip('.,;:-')
        # if the first word is fully capitalized (or just camelcase) and the rest are words
        # e.g., "Ai Artificial Intelligence", because we title-cased it!
        if len(first_word) >= 2 and len(first_word) <= 6:
            # check if it matches acronym pattern (e.g., A Artificial I Intelligence)
            # or just hardcode some common ones
            pass
            
    # Simpler pattern: "Acronym Expanded Form"
    # Because we title() the string earlier, it looks like "Ai Artificial Intelligence"
    # Let's match: Short word (2-5 chars), followed by words that start with those letters
    if len(parts) >= 2:
        acronym = parts[0].upper()
        # count how many letters of the acronym appear as first letters of subsequent words
        if len(acronym) >= 2 and len(acronym) <= 6:
            letters = [c for c in acronym if c.isalpha()]
            if letters:
                # Get the first letters of the remaining words
                first_letters = [w[0].upper() for w in parts[1:] if w[0].isalpha()]
                matches = 0
                for l in letters:
                    if l in first_letters:
                        matches += 1
                
                # If most letters match, it's an abbreviation
                if matches >= len(letters) - 1:
                    return True
                    
    # Also "Abbreviation Full Form"
    if "Abbreviation" in name and "Full" in name and "Form" in name:
        return True
        
    # Also Degree names
    if "Bsc" in name and "Degree" in name: return True
    if "Information Technology" in name: return True
    
    return False

test_cases = [
    "Ai Artificial Intelligence",
    "Ml Machine Learning",
    "Nlp Natural Language Processing",
    "Nsga Ii Nondominated Sorting Genetic Algorithm Ii",
    "Rest Representational State Transfer",
    "Sdg Sustainable Development Goal",
    "Shap Shapley Additive Explanations",
    "Wbs Work Breakdown Structure",
    "Abbreviation Full Form",
    "Develop Nlp Model",
    "Train Ml Classifier",
    "Design Rest Api",
    "Literature Review",
    "System Testing"
]

for t in test_cases:
    print(f"'{t}': {looks_like_abbreviation_entry(t)}")
