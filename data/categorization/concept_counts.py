import json

# List of concepts to check
concepts = [
    # General
    "fuzzy-trace theory", "source misattribution", "presupposition", "incorporation of misinformation",
    "strength hypothesis", "construction hypothesis", "acquisition processes", "retrieval processes",
    "memory regeneration", "linking", "creative imagination", "dissociation", "social desirability",
    "perceived social pressure", "individual difference factors", "metamemory beliefs", "trauma history",
    "attachment styles", "sleep deprivation", "false memory syndrome", "repressed memory therapy",
    "therapy-induced memory recovery", "memory enhancement techniques", "implications of false memories",
    "research methodologies", "cognitive neuroscience", "memory distortion", "emotional trauma",
    "recovered memories", "eyewitness testimony", "therapeutic strategies", "psychological implications",

    # Computer Science (P vs NP)
    "complexity relationship", "confidence in p ≠ np", "computational complexity", "proof techniques",
    "theoretical advancement",

    # History (Roanoke Colony)
    "base camp establishment", "aftermath and consequences", "expedition timeline", "voyage details",
    "colonial relocation", "colonization", "abandonment of the colony", "disappearance", "cultural symbolism",

    # Philosophy (Epistemic Injustice)
    "epistemicide", "epistemic exploitation",

    # Political Science (Consociationalism)
    "internal divisions",

    # Arts (Fluxus)
    "shock factor", "performative essence", "discourse on failure", "shift towards publication",
    "artistic representation", "cultural representation", "cultural significance", "inclusivity of fluxus",
    "unity in fluxus", "lack of leadership", "accusations against maciunas", "collaboration in creation",
    "lack of consistent identity", "cultural influence", "artistic production process"
]

# Path to the JSON file
file_path = '/Users/mollyhan/PycharmProjects/Cognitext/data/entities/cleaned_entity_section_results.json'

# Load the JSON file
with open(file_path, 'r') as file:
    data = json.load(file)


# Function to check if a concept is in the entities
def check_concepts_in_file(concepts, data):
    found_concepts = []
    missing_concepts = []

    # Flatten the list of entities
    entities = [entity['id'] for category in data.values() if isinstance(category, dict) for entity in
                category.get('entities', [])]

    # Check each concept
    for concept in concepts:
        if concept in entities:
            found_concepts.append(concept)
        else:
            missing_concepts.append(concept)

    return found_concepts, missing_concepts


# Check concepts in the JSON data
found_concepts, missing_concepts = check_concepts_in_file(concepts, data)

# Output the results
print("\nMissing Concepts:")
print(missing_concepts)

