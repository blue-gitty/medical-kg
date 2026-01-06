"""
Northstar Question Analysis using UMLS API
What biological pathways link intracranial aneurysm rupture risk to inflammation and hemodynamics?
"""
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.umls_client import UMLSAPIClient
from typing import Dict, List, Set, Any

# Hard-coded allowed entity types and their semantic group mappings
ALLOWED_ENTITY_TYPES = {
    'Disease',
    'Biological Process',
    'Biomarker',
    'Molecular',
    'Anatomical',
    'Biomechanical'
}

# Hard-coded allowed relationship types
ALLOWED_RELATIONSHIP_TYPES = {
    'INFLUENCES',
    'MECHANISTIC_LINK',
    'BIOMARKER_FOR'
}

# Stricter filtering for aneurysm-inflammation-hemodynamics question
# Only allow specific semantic types relevant to the research question
ALLOWED_SEMANTIC_TYPES = {
    # Disease - only vascular/neurological
    'T047',  # Disease or Syndrome
    'T046',  # Pathologic Function
    'T049',  # Cell or Molecular Dysfunction
    
    # Biological Process - only physiological
    'T039',  # Physiologic Function
    'T040',  # Organism Function  
    'T042',  # Organ or Tissue Function
    'T043',  # Cell Function
    
    # Molecular - inflammatory mediators only
    'T116',  # Amino Acid, Peptide, or Protein
    'T123',  # Biologically Active Substance
    'T129',  # Immunologic Factor
    
    # Anatomical - vascular structures only
    'T023',  # Body Part, Organ, or Organ Component
    'T024',  # Tissue
    'T030',  # Body Space or Junction
    
    # Biomarker
    'T034',  # Laboratory or Test Result
    'T201',  # Clinical Attribute
}

# Mapping of UMLS Semantic Types (TUI) to Semantic Groups
# Based on UMLS Semantic Network - mapping TUI codes to our entity types
SEMANTIC_TYPE_TO_GROUP = {
    # Disease-related (Disorders)
    'T047': 'Disease',  # Disease or Syndrome
    'T048': 'Disease',  # Mental or Behavioral Dysfunction
    'T049': 'Disease',  # Cell or Molecular Dysfunction
    'T050': 'Disease',  # Experimental Model of Disease
    'T191': 'Disease',  # Neoplastic Process
    'T019': 'Disease',  # Congenital Abnormality
    'T020': 'Disease',  # Acquired Abnormality
    'T190': 'Disease',  # Anatomical Abnormality
    'T037': 'Disease',  # Injury or Poisoning
    'T046': 'Disease',  # Pathologic Function
    
    # Biological Process (Activities & Behaviors, Phenomena, Concepts)
    'T062': 'Biological Process',  # Research Activity
    'T063': 'Biological Process',  # Molecular Function
    'T064': 'Biological Process',  # Gene or Genome
    'T065': 'Biological Process',  # Biologic Function
    'T066': 'Biological Process',  # Mental Process
    'T067': 'Biological Process',  # Phenomenon or Process
    'T068': 'Biological Process',  # Human-caused Phenomenon or Process
    'T069': 'Biological Process',  # Environmental Effect of Humans
    'T070': 'Biological Process',  # Natural Phenomenon or Process
    'T078': 'Biological Process',  # Health Care Activity
    'T051': 'Biological Process',  # Event
    'T052': 'Biological Process',  # Activity
    
    # Molecular (Chemicals & Drugs)
    'T116': 'Molecular',  # Amino Acid, Peptide, or Protein
    'T123': 'Molecular',  # Biologically Active Substance
    'T125': 'Molecular',  # Hormone
    'T126': 'Molecular',  # Enzyme
    'T127': 'Molecular',  # Vitamin
    'T129': 'Molecular',  # Immunologic Factor
    'T130': 'Molecular',  # Receptor
    'T131': 'Molecular',  # Antibiotic
    'T192': 'Molecular',  # Pharmacologic Substance
    'T195': 'Molecular',  # Antibiotic
    'T196': 'Molecular',  # Clinical Drug
    'T197': 'Molecular',  # Inorganic Chemical
    'T200': 'Molecular',  # Clinical Drug
    'T202': 'Molecular',  # Clinical Drug
    
    # Anatomical (Anatomy)
    'T017': 'Anatomical',  # Anatomical Structure
    'T018': 'Anatomical',  # Embryonic Structure
    'T021': 'Anatomical',  # Fully Formed Anatomical Structure
    'T022': 'Anatomical',  # Body System
    'T023': 'Anatomical',  # Body Part, Organ, or Organ Component
    'T024': 'Anatomical',  # Tissue
    'T025': 'Anatomical',  # Cell
    'T026': 'Anatomical',  # Cell Component
    'T029': 'Anatomical',  # Body Location or Region
    'T030': 'Anatomical',  # Body Space or Junction
    'T031': 'Anatomical',  # Body Substance
    
    # Biomarker (Clinical Attributes, Findings, Lab Results)
    'T034': 'Biomarker',  # Laboratory or Test Result
    'T201': 'Biomarker',  # Clinical Attribute
    'T033': 'Biomarker',  # Finding
    
    # Biomechanical (Physiologic Functions)
    'T039': 'Biological Process',  # Physiologic Function
    'T040': 'Biological Process',  # Organism Function
    'T042': 'Biomechanical',  # Organ or Tissue Function
    'T043': 'Biomechanical',  # Cell Function
    'T044': 'Biomechanical',  # Molecular Function
    'T045': 'Biomechanical',  # Genetic Function
    'T065': 'Biomechanical',  # Biologic Function
}

class NorthstarAnalyzer:
    """Analyzer for the northstar question about intracranial aneurysm"""
    
    def __init__(self):
        self.client = UMLSAPIClient()
        self.concepts = {}  # Store concept information
        self.relationships = []  # Store relationships
    
    def search_concepts(self, search_terms: List[str]) -> Dict[str, Any]:
        """Search for concepts related to the northstar question"""
        all_results = {}
        
        for term in search_terms:
            print(f"\n{'='*60}")
            print(f"Searching for: {term}")
            print('='*60)
            
            try:
                result = self.client.search(term, partial_search=True, page_size=25)
                all_results[term] = result
                
                if 'result' in result and 'results' in result['result']:
                    results = result['result']['results']
                    print(f"Found {len(results)} results (Total: {result['result'].get('recCount', 0)})")
                    
                    # Store top results
                    for item in results[:10]:  # Top 10 per term
                        cui = item.get('ui')
                        if cui:
                            self.concepts[cui] = {
                                'name': item.get('name'),
                                'rootSource': item.get('rootSource'),
                                'uri': item.get('uri'),
                                'search_term': term
                            }
            except Exception as e:
                print(f"Error searching for '{term}': {e}")
        
        return all_results
    
    def get_concept_details(self, cui: str) -> Dict[str, Any]:
        """Get detailed information about a concept including semantic types"""
        try:
            info = self.client.get_cui_info(cui)
            
            # Extract semantic types - TUI is in the URI
            semantic_types = []
            if 'result' in info:
                result = info['result']
                if 'semanticTypes' in result:
                    for st in result['semanticTypes']:
                        # Extract TUI from URI: .../TUI/T190 -> T190
                        tui = None
                        uri = st.get('uri', '')
                        if '/TUI/' in uri:
                            tui = uri.split('/TUI/')[-1]
                        
                        semantic_types.append({
                            'tui': tui,
                            'name': st.get('name'),
                            'uri': uri
                        })
            
            return {
                'cui': cui,
                'info': info,
                'semantic_types': semantic_types
            }
        except Exception as e:
            print(f"Error getting details for {cui}: {e}")
            return None
    
    def get_concept_relations(self, cui: str) -> List[Dict[str, Any]]:
        """Get relationships for a concept"""
        try:
            relations_result = self.client.get_cui_relations(cui, page_size=100)
            
            relations = []
            # Check if result is a list (direct result) or dict with 'result' key
            if isinstance(relations_result, list):
                relations = relations_result
            elif 'result' in relations_result:
                if isinstance(relations_result['result'], list):
                    relations = relations_result['result']
                elif 'results' in relations_result['result']:
                    relations = relations_result['result']['results']
            
            return relations
        except Exception as e:
            print(f"Error getting relations for {cui}: {e}")
            return []
    
    def map_semantic_type_to_group(self, tui: str) -> str:
        """Map semantic type TUI to semantic group"""
        return SEMANTIC_TYPE_TO_GROUP.get(tui, 'Unknown')
    
    def filter_by_entity_type(self, concept_details: Dict[str, Any]) -> bool:
        """
        Check if concept matches allowed semantic types (stricter filtering)
        Uses specific TUI codes instead of broad semantic groups
        """
        if not concept_details or 'semantic_types' not in concept_details:
            return False
        
        semantic_types = concept_details['semantic_types']
        for st in semantic_types:
            tui = st.get('tui')
            if tui and tui in ALLOWED_SEMANTIC_TYPES:
                return True
        
        return False
    
    def analyze_northstar_question(self):
        """Main analysis function for the northstar question"""
        print("\n" + "="*80)
        print("NORTHSTAR QUESTION ANALYSIS")
        print("="*80)
        print("Question: What biological pathways link intracranial aneurysm rupture")
        print("          risk to inflammation and hemodynamics?")
        print("="*80)
        
        # Search terms related to the question
        search_terms = [
            'intracranial aneurysm',
            'aneurysm rupture',
            'hemodynamics',
            'vascular inflammation'
        ]
        
        # Step 1: Search for concepts
        print("\n[STEP 1] Searching for relevant concepts...")
        search_results = self.search_concepts(search_terms)
        
        # Step 2: Get detailed information for each concept
        print("\n[STEP 2] Retrieving concept details and semantic types...")
        concept_details_map = {}
        filtered_concepts = {}
        
        for cui, concept_info in list(self.concepts.items())[:50]:  # Limit to 50 for now
            print(f"\nProcessing CUI: {cui} - {concept_info['name']}")
            details = self.get_concept_details(cui)
            
            if details:
                concept_details_map[cui] = details
                
                # Check if it matches allowed semantic types (stricter filtering)
                if self.filter_by_entity_type(details):
                    filtered_concepts[cui] = {
                        **concept_info,
                        'details': details
                    }
                    # Find which semantic type(s) matched
                    matched_tuis = []
                    for st in details['semantic_types']:
                        tui = st.get('tui')
                        if tui and tui in ALLOWED_SEMANTIC_TYPES:
                            matched_tuis.append(tui)
                    print(f"  [MATCH] Matches allowed semantic type(s): {', '.join(matched_tuis)}")
                    
                    # Print semantic types
                    if details['semantic_types']:
                        print(f"  Semantic Types:")
                        for st in details['semantic_types']:
                            tui = st.get('tui', '')
                            group = self.map_semantic_type_to_group(tui)
                            is_allowed = tui in ALLOWED_SEMANTIC_TYPES
                            status = "[ALLOWED]" if is_allowed else "[FILTERED OUT]"
                            print(f"    - {st.get('name')} (TUI: {tui}) -> Group: {group} {status}")
                else:
                    print(f"  [FILTERED] Does not match allowed semantic types")
        
        # Step 3: Get relationships for filtered concepts
        print("\n[STEP 3] Retrieving relationships...")
        print("NOTE: UMLS uses standard relationship types (RO=related to, RB=broader, etc.)")
        print("      Custom types (INFLUENCES, MECHANISTIC_LINK, BIOMARKER_FOR) may need mapping")
        print()
        
        for cui, concept in list(filtered_concepts.items())[:20]:  # Limit to 20 for now
            print(f"\nGetting relations for: {concept['name']} ({cui})")
            try:
                relations = self.get_concept_relations(cui)
                
                if relations:
                    print(f"  Found {len(relations)} relationships")
                    # Store relations in the concept dictionary
                    filtered_concepts[cui]['relations'] = relations
                    
                    # Print sample relationships with more details
                    for rel in relations[:5]:
                        rel_label = rel.get('relationLabel', 'Unknown')
                        additional_label = rel.get('additionalRelationLabel', '')
                        related_name = rel.get('relatedIdName', 'Unknown')
                        related_id = rel.get('relatedId', '')
                        
                        # Extract CUI from related_id if it's a URI
                        related_cui = 'N/A'
                        if '/CUI/' in related_id:
                            related_cui = related_id.split('/CUI/')[-1].split('/')[0]
                        elif related_id:
                            # Try to extract from source format
                            parts = related_id.split('/')
                            if len(parts) > 0:
                                related_cui = parts[-1]
                        
                        rel_str = f"    - {rel_label}"
                        if additional_label:
                            rel_str += f" ({additional_label})"
                        rel_str += f": {related_name}"
                        if related_cui != 'N/A':
                            rel_str += f" [CUI: {related_cui}]"
                        print(rel_str)
                else:
                    print(f"  No relationships found")
                    filtered_concepts[cui]['relations'] = []
            except Exception as e:
                print(f"  Error retrieving relationships: {e}")
                filtered_concepts[cui]['relations'] = []
        
        # Step 4: Print summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total concepts found: {len(self.concepts)}")
        print(f"Concepts matching allowed semantic types: {len(filtered_concepts)}")
        print(f"Allowed semantic types (TUI): {sorted(ALLOWED_SEMANTIC_TYPES)}")
        print("\nFiltered Concepts:")
        for cui, concept in filtered_concepts.items():
            print(f"\n  CUI: {cui}")
            print(f"  Name: {concept['name']}")
            print(f"  Source: {concept['rootSource']}")
            if 'semantic_types' in concept.get('details', {}):
                st_list = concept['details']['semantic_types']
                matched_tuis = []
                groups = set()
                for st in st_list:
                    tui = st.get('tui', '')
                    if tui in ALLOWED_SEMANTIC_TYPES:
                        matched_tuis.append(tui)
                    group = self.map_semantic_type_to_group(tui)
                    if group in ALLOWED_ENTITY_TYPES:
                        groups.add(group)
                print(f"  Matched Semantic Types (TUI): {', '.join(matched_tuis)}")
                print(f"  Semantic Groups: {', '.join(groups)}")
            if 'relations' in concept:
                print(f"  Relationships: {len(concept['relations'])}")
        
        # Save results to JSON
        output_data = {
            'northstar_question': 'What biological pathways link intracranial aneurysm rupture risk to inflammation and hemodynamics?',
            'allowed_entity_types': list(ALLOWED_ENTITY_TYPES),
            'allowed_semantic_types': sorted(list(ALLOWED_SEMANTIC_TYPES)),
            'allowed_relationship_types': list(ALLOWED_RELATIONSHIP_TYPES),
            'concepts': filtered_concepts
        }
        
        # Save to data directory
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        os.makedirs(data_dir, exist_ok=True)
        output_file = os.path.join(data_dir, 'northstar_analysis_results.json')
        
        # Custom JSON serializer to handle complex objects
        def json_serializer(obj):
            if isinstance(obj, dict):
                return {k: json_serializer(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [json_serializer(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return json_serializer(obj.__dict__)
            else:
                return str(obj) if not isinstance(obj, (str, int, float, bool, type(None))) else obj
        
        # Clean the data before saving
        cleaned_data = json.loads(json.dumps(output_data, default=str))
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults saved to: {output_file}")
        
        return filtered_concepts

if __name__ == "__main__":
    analyzer = NorthstarAnalyzer()
    results = analyzer.analyze_northstar_question()

