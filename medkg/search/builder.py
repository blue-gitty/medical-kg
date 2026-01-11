import concurrent.futures
from typing import List, Dict, Set, Any, Optional

from ..api.umls_client import UMLSAPIClient

# Stop words for n-gram extraction
STOP_WORDS: Set[str] = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'can', 'and', 'or', 'but', 'not',
    'in', 'on', 'at', 'by', 'for', 'with', 'to', 'from', 'of', 'as',
    'what', 'which', 'who', 'when', 'where', 'why', 'how', 'this', 'that',
    'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
}

def remove_stop_words(tokens: List[str]) -> List[str]:
    """Remove stop words from a list of tokens."""
    return [token for token in tokens if token not in STOP_WORDS]

def tokenize(text: str, remove_stopwords: bool = True) -> List[str]:
    """Simple tokenization - split on whitespace, clean, and optionally remove stop words."""
    tokens = text.split()
    cleaned = []
    for token in tokens:
        token = token.strip('.,;:!?()[]{}"\'-')
        if token:
            cleaned.append(token.lower())
    
    if remove_stopwords:
        cleaned = remove_stop_words(cleaned)
    
    return cleaned

def get_ngrams_by_size(text: str, n: int, remove_stopwords: bool = True) -> List[str]:
    """Get n-grams of a specific size only."""
    tokens = tokenize(text, remove_stopwords=remove_stopwords)
    return [' '.join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]

def process_umls_match(term: str, client: UMLSAPIClient) -> tuple:
    """Helper function to fetch match for a single term."""
    best = client.search_best_match(term, threshold=0.6)
    formatted_data = None
    
    if best and best.get('allowed_type_tuis'):
        formatted_data = {
            'cui': best['cui'],
            'name': best['name'],
            'combined_score': best['combined_score'],
            'mesh_term': best['mesh_term'],
            'semantic_type_names': best.get('semantic_type_names', []),
            'allowed_type_names': best.get('allowed_type_names', []),
            'allowed_type_tuis': best.get('allowed_type_tuis', [])
        }
    return term, formatted_data

def build_pubmed_query_unigram_bigram(unigram_matches, bigram_matches, score_threshold=0.8):
    """
    Smart query with proper CUI deduplication.
    (Logic preserved exactly as requested)
    """
    # Get perfect unigram matches
    core_unigrams = []
    core_cui_set = set()
    
    for unigram, data in unigram_matches.items():
        score = data.get('score', data.get('combined_score', 0))
        if score == 1.0:
            cui = data['cui']
            core_unigrams.append({
                'term': unigram,
                'cui': cui,
                'name': data['name'],
                'mesh': data['mesh_term'],
                'score': score,
                'related_bigrams': []
            })
            core_cui_set.add(cui)
    
    # Process bigrams - avoid CUI duplication
    standalone_bigrams = []
    used_bigram_cuis = set()
    
    for bigram, data in bigram_matches.items():
        score = data.get('score', data.get('combined_score', 0))
        
        if score < score_threshold:
            continue
        
        bigram_cui = data['cui']
        
        # Skip if bigram's CUI is already a core unigram
        if bigram_cui in core_cui_set:
            continue
        
        # Skip if already used
        if bigram_cui in used_bigram_cuis:
            continue
        
        bigram_concept = {
            'term': bigram,
            'cui': bigram_cui,
            'name': data['name'],
            'mesh': data['mesh_term'],
            'score': score
        }
        
        # Match bigram to unigram groups
        matched = False
        bigram_words = set(bigram.lower().split())
        
        for unigram_group in core_unigrams:
            unigram_word = unigram_group['term'].lower()
            
            if unigram_word in bigram_words and bigram_cui != unigram_group['cui']:
                unigram_group['related_bigrams'].append(bigram_concept)
                used_bigram_cuis.add(bigram_cui)
                matched = True
                break
        
        if not matched:
            standalone_bigrams.append(bigram_concept)
            used_bigram_cuis.add(bigram_cui)
    
    # Build query clauses
    clauses = []
    
    for group in core_unigrams:
        or_parts = []
        
        # Add core unigram
        if group['mesh'] and group['mesh'] != 'None':
            or_parts.append(f'"{group["mesh"]}"[MeSH Terms]')
            or_parts.append(f'"{group["name"].lower()}"[Title/Abstract]')
        else:
            or_parts.append(f'"{group["name"].lower()}"[Title/Abstract]')
        
        # Add related bigrams
        for bigram in group['related_bigrams']:
            if bigram['mesh'] and bigram['mesh'] != 'None':
                or_parts.append(f'"{bigram["mesh"]}"[MeSH Terms]')
                or_parts.append(f'"{bigram["name"].lower()}"[Title/Abstract]')
            else:
                or_parts.append(f'"{bigram["name"].lower()}"[Title/Abstract]')
        
        if len(or_parts) == 1:
            clauses.append(or_parts[0])
        else:
            clauses.append("(" + " OR ".join(or_parts) + ")")
    
    # Add standalone bigrams
    for bigram in standalone_bigrams:
        if bigram['mesh'] and bigram['mesh'] != 'None':
            clause = f'("{bigram["mesh"]}"[MeSH Terms] OR "{bigram["name"].lower()}"[Title/Abstract])'
        else:
            clause = f'"{bigram["name"].lower()}"[Title/Abstract]'
        clauses.append(clause)
    
    return " AND ".join(clauses), {
        'core_unigrams': len(core_unigrams),
        'standalone_bigrams': len(standalone_bigrams)
    }

def query_to_pubmed_query(query: str, score_threshold: float = 0.8) -> str:
    """
    Optimized conversion of natural language query to PubMed query string.
    Uses concurrent execution for UMLS lookups.
    """
    client = UMLSAPIClient()
    
    # 1. Extract raw n-grams
    unigrams = get_ngrams_by_size(query, n=1, remove_stopwords=True)
    bigrams = get_ngrams_by_size(query, n=2, remove_stopwords=True)
    
    # 2. Identify unique terms to query (deduplication)
    # We use sets to avoid redundant API calls for repeated words
    unique_unigrams = set(unigrams)
    unique_bigrams = set(bigrams)
    
    unigram_matches = {}
    bigram_matches = {}
    
    # 3. Execute UMLS lookups in parallel
    # Adjust max_workers based on your API rate limits; 10 is usually safe for UMLS
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Submit unigram tasks
        future_to_unigram = {
            executor.submit(process_umls_match, term, client): term 
            for term in unique_unigrams
        }
        # Submit bigram tasks
        future_to_bigram = {
            executor.submit(process_umls_match, term, client): term 
            for term in unique_bigrams
        }
        
        # Process unigram results
        for future in concurrent.futures.as_completed(future_to_unigram):
            term, data = future.result()
            if data:
                unigram_matches[term] = data
                
        # Process bigram results
        for future in concurrent.futures.as_completed(future_to_bigram):
            term, data = future.result()
            if data:
                bigram_matches[term] = data

    # 4. Build PubMed query (logic unchanged)
    pubmed_query, metadata = build_pubmed_query_unigram_bigram(
        unigram_matches, 
        bigram_matches, 
        score_threshold
    )
    
    return pubmed_query

# Alias for backward compatibility
def build_pubmed_query(query: str, score_threshold: float = 0.8) -> str:
    """Alias for query_to_pubmed_query for backward compatibility."""
    return query_to_pubmed_query(query, score_threshold)
