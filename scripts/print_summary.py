"""Print a summary of the northstar analysis results"""
import json
import os

# Load the results
data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
with open(os.path.join(data_dir, 'northstar_analysis_results.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)

print("="*80)
print("NORTHSTAR QUESTION ANALYSIS SUMMARY")
print("="*80)
print(f"\nQuestion: {data['northstar_question']}")
print(f"\nAllowed Entity Types: {', '.join(data['allowed_entity_types'])}")
print(f"Allowed Relationship Types: {', '.join(data['allowed_relationship_types'])}")
print(f"\nTotal Concepts Found: {len(data['concepts'])}")

# Group concepts by semantic group
by_group = {}
for cui, concept in data['concepts'].items():
    if 'details' in concept and 'semantic_types' in concept['details']:
        for st in concept['details']['semantic_types']:
            tui = st.get('tui', '')
            # Map TUI to group (simplified - using the mapping from the script)
            group = 'Unknown'
            if tui:
                # This is a simplified mapping - you'd need the full mapping
                if tui in ['T047', 'T048', 'T049', 'T050', 'T191', 'T019', 'T020', 'T190', 'T037', 'T046']:
                    group = 'Disease'
                elif tui in ['T042', 'T043', 'T044', 'T045', 'T065']:
                    group = 'Biomechanical'
                elif tui in ['T033', 'T201']:
                    group = 'Biomarker'
                elif tui in ['T070', 'T067', 'T062', 'T063', 'T064', 'T065', 'T066', 'T068', 'T069', 'T078', 'T051', 'T052']:
                    group = 'Biological Process'
                elif tui in ['T017', 'T018', 'T021', 'T022', 'T023', 'T024', 'T025', 'T026', 'T029', 'T030', 'T031']:
                    group = 'Anatomical'
                elif tui in ['T116', 'T123', 'T125', 'T126', 'T127', 'T129', 'T130', 'T131', 'T192', 'T195', 'T196', 'T197', 'T200', 'T202']:
                    group = 'Molecular'
            
            if group not in by_group:
                by_group[group] = []
            by_group[group].append({
                'cui': cui,
                'name': concept['name'],
                'source': concept.get('rootSource', 'Unknown')
            })
            break  # Use first matching group

print("\n" + "="*80)
print("CONCEPTS BY SEMANTIC GROUP")
print("="*80)

for group, concepts in sorted(by_group.items()):
    print(f"\n{group} ({len(concepts)} concepts):")
    for concept in concepts[:10]:  # Show first 10 per group
        print(f"  - {concept['name']} (CUI: {concept['cui']}, Source: {concept['source']})")
    if len(concepts) > 10:
        print(f"  ... and {len(concepts) - 10} more")

# Show relationships info
print("\n" + "="*80)
print("RELATIONSHIPS INFORMATION")
print("="*80)
print("\nNOTE: UMLS uses standard relationship types:")
print("  - RO = Related to")
print("  - RB = Broader")
print("  - RN = Narrower")
print("  - CHD = Child")
print("  - PAR = Parent")
print("\nYour custom relationship types (INFLUENCES, MECHANISTIC_LINK, BIOMARKER_FOR)")
print("may need to be mapped from UMLS relationship types or extracted from attributes.")

relationships_found = 0
for cui, concept in data['concepts'].items():
    if 'relations' in concept and concept['relations']:
        relationships_found += len(concept['relations'])

print(f"\nTotal relationships retrieved: {relationships_found}")
print("\nSample relationships (first 5 concepts with relations):")
count = 0
for cui, concept in data['concepts'].items():
    if 'relations' in concept and concept['relations'] and count < 5:
        print(f"\n  {concept['name']} (CUI: {cui}):")
        for rel in concept['relations'][:3]:  # First 3 relationships
            rel_label = rel.get('relationLabel', 'Unknown')
            additional = rel.get('additionalRelationLabel', '')
            related_name = rel.get('relatedIdName', 'Unknown')
            rel_str = f"    - {rel_label}"
            if additional:
                rel_str += f" ({additional})"
            rel_str += f": {related_name}"
            print(rel_str)
        count += 1

print("\n" + "="*80)
data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
print(f"Full results saved to: {os.path.join(data_dir, 'northstar_analysis_results.json')}")
print("="*80)

