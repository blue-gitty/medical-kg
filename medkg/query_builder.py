"""
Lightweight query builder: User query → N-grams → UMLS → MeSH → PubMed query
Follows exact workflow from templates.py
"""
from typing import List, Dict, Set, Any, Optional

from api.umls_client import UMLSAPIClient

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


def build_pubmed_query_unigram_bigram(unigram_matches, bigram_matches, score_threshold=0.8):
    """
    Smart query with proper CUI deduplication.
    
    1. Take unigrams with score == 1.0 as base concepts
    2. Add related bigrams to unigram groups (OR clauses)
    3. Prevent CUI duplication across groups
    """
    
    # Get perfect unigram matches
    core_unigrams = []
    core_cui_set = set()  # Track to prevent duplication
    
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
                break  # Only add to first matching group
        
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
    Convert a natural language query to a PubMed query string.
    
    Process:
    1. Extract unigrams and bigrams (stop words removed)
    2. Find UMLS matches for each (with allowed semantic types)
    3. Build PubMed query grouping bigrams with related unigrams
    
    Args:
        query: Natural language query string
        score_threshold: Minimum score for bigrams (default: 0.8)
        
    Returns:
        PubMed query string ready to use
    """
    client = UMLSAPIClient()
    
    # Extract unigrams and bigrams
    unigrams = get_ngrams_by_size(query, n=1, remove_stopwords=True)
    bigrams = get_ngrams_by_size(query, n=2, remove_stopwords=True)
    
    # Get UMLS matches for unigrams
    unigram_matches = {}
    for unigram in unigrams:
        best = client.search_best_match(unigram, threshold=0.6)
        if best and best.get('allowed_type_tuis'):
            unigram_matches[unigram] = {
                'cui': best['cui'],
                'name': best['name'],
                'combined_score': best['combined_score'],
                'mesh_term': best['mesh_term'],
                'semantic_type_names': best.get('semantic_type_names', []),
                'allowed_type_names': best.get('allowed_type_names', []),
                'allowed_type_tuis': best.get('allowed_type_tuis', [])
            }
    
    # Get UMLS matches for bigrams
    bigram_matches = {}
    for bigram in bigrams:
        best = client.search_best_match(bigram, threshold=0.6)
        if best and best.get('allowed_type_tuis'):
            bigram_matches[bigram] = {
                'cui': best['cui'],
                'name': best['name'],
                'combined_score': best['combined_score'],
                'mesh_term': best['mesh_term'],
                'semantic_type_names': best.get('semantic_type_names', []),
                'allowed_type_names': best.get('allowed_type_names', []),
                'allowed_type_tuis': best.get('allowed_type_tuis', [])
            }
    
    # Build PubMed query
    pubmed_query, metadata = build_pubmed_query_unigram_bigram(unigram_matches, bigram_matches, score_threshold)
    
    return pubmed_query


# Alias for backward compatibility
def build_pubmed_query(query: str, score_threshold: float = 0.8) -> str:
    """Alias for query_to_pubmed_query for backward compatibility."""
    return query_to_pubmed_query(query, score_threshold)
