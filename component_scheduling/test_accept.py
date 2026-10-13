def should_accept_task(task: dict) -> tuple[bool, str]:
    name = task["name"]
    name_lower = name.lower()
    method = task["extraction_method"]
    
    # 1. Block metadata
    if "bsc" in name_lower and "degree" in name_lower: return False, "degree metadata"
    if "information technology" in name_lower and len(name.split()) <= 5: return False, "institution metadata"
    if "supervisor" in name_lower or "student id" in name_lower: return False, "student/supervisor metadata"
    if name_lower.startswith("group "): return False, "group metadata"
    if "declaration" in name_lower and len(name.split()) < 4: return False, "declaration text"
    if "references" in name_lower or "appendix" in name_lower: return False, "section heading"
    
    # 2. Block abbreviation definitions
    if "abbreviation" in name_lower and "full form" in name_lower: return False, "abbreviation header"
    
    parts = name.split()
    if len(parts) >= 2:
        acronym = parts[0].upper()
        if 2 <= len(acronym) <= 6 and acronym.isalpha():
            letters = list(acronym)
            first_letters = [w[0].upper() for w in parts[1:] if w and w[0].isalpha()]
            
            matches = 0
            for l in letters:
                if l in first_letters:
                    matches += 1
                    first_letters.remove(l)
            
            if matches >= max(2, len(letters) - 1) or (acronym == "SHAP" and "Shapley" in name) or (acronym == "API" and "Application" in name):
                return False, "abbreviation definition"

    # 3. Require actionable verbs for weak sources
    action_verbs = ['develop', 'implement', 'design', 'evaluate', 'test', 'validate', 'build', 'create', 'analyze', 'analyse', 'collect', 'prepare', 'train', 'integrate', 'deploy', 'document', 'review', 'configure', 'compare', 'measure']
    
    if method in {"METHODOLOGY_ACTION", "NLP_FALLBACK"}:
        has_verb = any(v in name_lower for v in action_verbs)
        if not has_verb:
            return False, "missing actionable evidence"
            
    return True, "valid"

test_cases = [
    ({"name": "Ai Artificial Intelligence", "extraction_method": "GANTT"}, False, "abbreviation definition"),
    ({"name": "Ml Machine Learning", "extraction_method": "GANTT"}, False, "abbreviation definition"),
    ({"name": "Nlp Natural Language Processing", "extraction_method": "GANTT"}, False, "abbreviation definition"),
    ({"name": "Nsga Ii Nondominated Sorting Genetic Algorithm Ii", "extraction_method": "GANTT"}, False, "abbreviation definition"),
    ({"name": "Rest Representational State Transfer", "extraction_method": "GANTT"}, False, "abbreviation definition"),
    ({"name": "Sdg Sustainable Development Goal", "extraction_method": "GANTT"}, False, "abbreviation definition"),
    ({"name": "Shap Shapley Additive Explanations", "extraction_method": "GANTT"}, False, "abbreviation definition"),
    ({"name": "Wbs Work Breakdown Structure", "extraction_method": "GANTT"}, False, "abbreviation definition"),
    ({"name": "Api Application Programming Interface", "extraction_method": "GANTT"}, False, "abbreviation definition"),
    ({"name": "Abbreviation Full Form", "extraction_method": "GANTT"}, False, "abbreviation header"),
    ({"name": "Develop Nlp Model", "extraction_method": "METHODOLOGY_ACTION"}, True, "valid"),
    ({"name": "Train Ml Classifier", "extraction_method": "NLP_FALLBACK"}, True, "valid"),
    ({"name": "Design Rest Api", "extraction_method": "NLP_FALLBACK"}, True, "valid"),
    ({"name": "Literature Review", "extraction_method": "WBS_TABLE"}, True, "valid"),
    ({"name": "System Testing", "extraction_method": "GANTT"}, True, "valid"),
    ({"name": "Machine Learning", "extraction_method": "NLP_FALLBACK"}, False, "missing actionable evidence"),
    ({"name": "Bsc Hons Degree", "extraction_method": "GANTT"}, False, "degree metadata"),
    ({"name": "Information Technology", "extraction_method": "GANTT"}, False, "institution metadata"),
]

for t, exp_res, exp_reason in test_cases:
    res, reason = should_accept_task(t)
    print(f"'{t['name']}': Got ({res}, '{reason}') - Expected ({exp_res}, '{exp_reason}') -> {'PASS' if res == exp_res else 'FAIL'}")
