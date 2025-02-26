import json
from transformers import pipeline

# Initialize zero-shot classification pipeline
classifier = pipeline("text2text-generation", model="t5-base", device=0)

# Load the JSON data
def load_json(file_path):
    with open(file_path, "r") as file:
        return json.load(file)


# Define the candidate labels
candidate_labels = """
ANIMAL: Living beings (excluding humans) with the ability to move and perceive their surroundings. (e.g., dog, cat, mammal)
ARTIFACT: All the objects, artifacts, tools, products, and items. (e.g., vehicle, software, mouse)
ASSET: Assets, resources, or possessions with economic or intrinsic value. (e.g., capital, stock, wealth)
BIOLOGY: Biological entities, including living organisms, cells, or biological components. (e.g., protein, cell, Herpes Simplex Virus)
CELESTIAL: Celestial bodies as Planets, stars, asteroids, galaxies, and other astronomical objects. (e.g., comet, nebulae, Sun)
CULTURE: Cultural aspects, traditions, customs, and practices associated with specific groups or societies. (e.g., religion, feminism, socialism)
DATETIME: Dates and times. (e.g., 18 March, Saturday, 1979, the evening of 19 November)
DISEASE: Medical conditions, illnesses, disorders, and health-related issues affecting living organisms. (e.g., infection, allergy, metastasis)
DISCIPLINE: Specific fields of study, knowledge, or expertise. (e.g., discipline, sport, football, computer science)
EVENT: Events, phenomenon, or activities that occur at specific times or places. (e.g., crime, professorship, temperature change)
FEELING: Emotions, sensations, and subjective experiences related to human or animal consciousness. (e.g., affection, attachment, agitation)
FOOD: Edible items, dishes, beverages, and culinary products that are consumed for nourishment or enjoyment. (e.g., beverage, dish, lasagna)
GROUP: Group of people or animals. (e.g., staff, social group, panel)
LANGUAGE: Individual language-related items, such as words, phrases, or idiomatic expressions. (e.g., discourse, context, lexeme)
LAW: Legal principles, regulations, and rules governing society and various aspects of life. (e.g., law, civil law, administrative law)
LOC: Geographical locations, such as villages, towns, cities, regions, countries, continents, landmarks, or natural features. (e.g., space, surface, street, road)
MEASURE: Units of measurement and quantification used to determine the size, quantity, or quality of various objects or phenomena. (e.g., day, microsecond, millisecond)
MEDIA: Various forms of communication and entertainment media, such as newspapers, television shows, movies. (e.g., soundtrack, report, publication)
MONEY: Monetary units, currencies, and financial values used in different contexts. (e.g., dollar, 15 euros, 1116 CHF)
ORG: Organizations, institutions, and companies involved in diverse sectors or activities. (e.g., Industry, commercial enterprise, San Francisco Giants)
PART: Individual components or sections of larger entities or objects. (e.g., finger, chin, head)
PER: Individuals or persons, including real people and historical figures. (e.g., doctor, historian, professor)
PLANT: Types of trees, flowers, and other plants, including their scientific names. (e.g., grass, peach tree, Forsythia)
PROPERTY: Properties or attributes of objects, entities, or concepts. (e.g., thickness, height, dimension)
PSYCH: Psychological concepts, mental states, and phenomena related to the human mind and behavior. (e.g., psychological feature, cognition, attention)
RELATION: Relationships, connections, and associations between entities or concepts. (e.g., apport, competition, comparison)
STRUCT: Physical structures, including buildings, architectural designs, and engineered constructions. (e.g., shelter, gravestone, refuge)
SUBSTANCE: Chemical substances. (e.g., acid, bactericide, carbonyl)
SUPER: Mythological and religious entities. (e.g., Apollo, Persephone, Aphrodite)
"""

# Convert candidate labels into a dictionary format for easy lookup
candidate_labels_dict = {}
for label in candidate_labels.strip().split("\n"):
    label, description = label.split(":", 1)
    candidate_labels_dict[label.strip()] = description.strip()


# Function to clean concept data by combining the contexts for each concept
def clean_concept_data(concept_data):
    cleaned_data = {}

    for article_name, article_info in concept_data.items():
        for entity in article_info["entities"]:
            concept_id = entity["id"]

            if concept_id not in cleaned_data:
                cleaned_data[concept_id] = {
                    "category": article_info["category"],
                    "description": "",
                    "total_entities": article_info["total_entities"]
                }

            combined_context = []
            for appearance in entity["appearances"]:
                context = appearance["context"]
                combined_context.append(context)

            cleaned_data[concept_id]["description"] = " ".join(combined_context)

    return cleaned_data


def classify_concepts(cleaned_data, candidate_labels):
    classification_results = {}

    for concept_id, details in cleaned_data.items():
        description = details["description"]

        # Create a prompt for T5
        prompt = f"Given the concept: '{concept_id} and it's context: {description}', categorize it into one of the types: {candidate_labels}"

        # Get the result from T5
        result = classifier(prompt)

        classification_results[concept_id] = {
            "predicted_type": result[0]['generated_text'].strip(),
            "score": None  # T5 doesn't return a score, you might use confidence scoring if needed
        }

    return classification_results


# Load the data from the provided path
file_path = '/Users/mollyhan/PycharmProjects/Cognitext/data/simp_entity_section_results.json'
concept_data = load_json(file_path)

# Clean the concepts
cleaned_concepts = clean_concept_data(concept_data)

# Classify the cleaned concepts using zero-shot classification
classification_results = classify_concepts(cleaned_concepts, candidate_labels_dict)

# Show the classification results
for concept_id, result in classification_results.items():
    print(f"Concept ID: {concept_id}")
    print(f"Predicted type: {result['predicted_type']}")
    print(f"Score: {result['score']}\n")
