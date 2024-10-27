import wikipediaapi
import requests
import json
import os

# Custom user agent
user_agent = "Cognitext/1.0 (https://github.com/mollyhan19/Cognitext; molly.han@emory.edu)"
wiki_wiki = wikipediaapi.Wikipedia(user_agent)

def fetch_wiki_content(title):
    page = wiki_wiki.page(title)
    if not page.exists():
        print(f"Article '{title}' does not exist.")
        return None

    # Initial article data
    article_data = {
        "title": page.title,
        "word_count": len(page.text.split()),
        "sections": [],
        "links": [link for link in page.links.keys()],  # Fetch links to related articles
    }

    def add_sections(sections):
        for section in sections:
            section_data = {
                "heading": section.title,
                "content": section.text,
                "subsections": []
            }
            if section.sections:
                add_sections(section.sections)
            article_data["sections"].append(section_data)

    add_sections(page.sections)
    return article_data

# Custom query filtering: fetch backlinks and filter out common articles
def get_backlinks(title):
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=backlinks&bltitle={title}&bllimit=500&format=json"
    response = requests.get(url).json()
    backlinks = response.get("query", {}).get("backlinks", [])
    return backlinks

def fetch_related_articles(seed_title, max_links=5):
    seed_article = fetch_wiki_content(seed_title)
    related_articles = []

    if not seed_article:
        return None

    # Fetch related articles from links and filter out articles with too many backlinks
    for link_title in seed_article["links"]:
        backlinks = get_backlinks(link_title)
        if len(backlinks) < 50:  # Custom filter: only fetch articles with fewer than 50 backlinks
            related_article = fetch_wiki_content(link_title)
            if related_article:
                related_articles.append(related_article)
                if len(related_articles) >= max_links:
                    break

    return related_articles

# Seed articles (15 manually selected articles)
seed_articles = {
    "biology": [
        "Tardigrade",
        "Immortal jellyfish",
        "Quantum biology",
        "Quorum sensing",
        "Extremophile",
        "Symbiogenesis",
        "Horizontal gene transfer",
        "Microchimerism",
        "Biological immortality",
        "Stigmergy",
        "Magnetoreception",
        "Chronobiology",
        "Bioluminescence",
        "Biomimicry"
    ],

    "computer_science": [
        "Quantum computing",
        "Ant colony optimization algorithms",
        "Byzantine fault",
        "Lambda calculus",
        "Quantum supremacy",
        "Neural network (machine learning)",
        "P versus NP problem",
        "Turing test",
        "Quantum entanglement",
        "Blockchain",
        "Zero-knowledge proof",
        "Homomorphic encryption",
        "Quantum teleportation",
        "Self-modifying code",
        "Cellular automaton",
        "Confidential computing",
        "Hypertext"
    ],

    "history": [
        "Dancing plague of 1518",
        "Year Without a Summer",
        "Great Molasses Flood",
        "Tulip mania",
        "Lost Colony of Roanoke",
        "Christmas truce",
        "Emu War",
        "Kingdom of North Sudan",
        "Ghost Army",
        "Operation Acoustic Kitty",
        "War of the Bucket",
        "Witch bottle",
        "Carrington Event",
        "Bronze Age collapse",
        "Phantom time hypothesis"
    ],

    "philosophy": [
        "Chinese room",
        "Ship of Theseus",
        "Eliminative materialism",
        "Embodied cognition"
        "Philosophical zombie",
        "Simulation hypothesis",
        "Epistemic injustice",
        "Modal realism",
        "Trolley problem",
        "Mary's room",
        "Boltzmann brain",
        "Experience machine",
        "Philosophical razor",
        "Newcomb's paradox",
        "Meta-epistemology",
        "Ethical intuitionism",
        "Moral luck",
        "Hylomorphism",
        "Vitalism",
        "Panpsychism",
    ],

    "political_science": [
        "Consociationalism",
        "Paradiplomacy",
        "Constructivism (international relations)",
        "Arrow's impossibility theorem",
        "Participatory economics",
        "Overton window",
        "Sortition",
        "Georgism",
        "Liquid democracy",
        "Noocracy",
        "Post-scarcity economy",
        "Meritocracy",
        "Postcolonial international relation",
        "Resource-based economy",
        "Fourth-generation warfare"
    ],

    "linguistics": [
        "Pirahã language",
        "Linear B",
        "Linguistic relativity",
        "Silbo Gomero",
        "Semantic satiation",
        "Optimality theory",
        "Garden path sentence",
        "Cryptolect",
        "Constructed language",
        "Proto-Human language",
        "Sound symbolism",
        "Syntactic ambiguity",
        "Glossolalia",
        "Language of thought hypothesis",
        "Signed English",
        "Linguistic prescription",
        "Ergative-absolutive alignment",
        "Distributed morphology",
        "Construction grammar"
    ],

    "arts": [
        "Vorticism",
        "Arte Povera",
        "Ukiyo-e",
        "Anamorphosis",
        "Outsider art",
        "Fluxus",
        "Gutai Art Association",
        "Mail art",
        "Sound art",
        "Kinetic art",
        "Land art",
        "Bio art",
        "Glitch art",
        "Light art",
        "Net art",
        "Performance art",
        "Installation art",
        "Environmental art",
        "Vorticism",
        "Suprematism"
    ],

    "math/stats": [
        "Banach–Tarski paradox",
        "Four color theorem",
        "Möbius strip",
        "Gabriel's Horn",
        "Birthday problem",
        "Monty Hall problem",
        "Mandelbrot set",
        "Game of Life",
        "Chaos theory",
        "Monster group",
        "Perfect number",
        "Twin prime conjecture",
        "Fibonacci sequence",
        "Golden ratio",
        "Riemann hypothesis"
    ],

    "health/medicine": [
        "Foreign accent syndrome",
        "Alice in Wonderland syndrome",
        "Capgras delusion",
        "Cryotherapy",
        "Nanomedicine"
        "Pharmacogenomics",
        "Immunotherapy",
        "Cotard delusion",
        "Walking corpse syndrome",
        "Targeted memory reactivation",
        "Fecal microbiota transplant",
        "Optogenetics",
        "Brain-computer interface",
        "Circadian medicine",
        "Chronotherapy",
        "Genetic counseling",
        "Precision medicine",
        "Metabolomics"
    ],

    "general": [
        "Mandela effect",
        "Dunbar's number",
        "Solarpunk",
        "Anthropocene",
        "Sustainable fashion"
        "Dunning–Kruger effect",
        "Butterfly effect",
        "Streisand effect",
        "Internet phenomenon",
        "Urban legend",
        "Collective intelligence",
        "Mass hysteria",
        "Emergence",
        "Synchronicity",
        "Cognitive bias",
        "Social proof",
        "Viral phenomenon",
        "Cultural universals",
        "List of common misconceptions"
    ]
}

# Initialize JSON structure
all_articles = {
    "schema": {
        "schema_type": "ArticleData",
        "schema_version": "1.0"
    },
    "articles": {}
}

# Expand from seed articles and filter for lesser-known related articles
for category, seeds in seed_articles.items():
    for seed_title in seeds:
        print(f"Fetching and expanding from seed article: {seed_title} in category {category}")
        seed_content = fetch_wiki_content(seed_title)
        if seed_content:
            all_articles["articles"][seed_title] = {
                "category": category,
                "content": seed_content,
                "related_articles": []
            }

            # Fetch related articles that are less commonly linked
            related_articles = fetch_related_articles(seed_title)
            all_articles["articles"][seed_title]["related_articles"] = related_articles

# Save to text_corpus.json
json_file_path = "/Users/mollyhan/PycharmProjects/Cognitext/data/text_corpus.json"
with open(json_file_path, 'w') as json_file:
    json.dump(all_articles, json_file, indent=4)

print(f"All seed and related articles fetched and stored in '{json_file_path}' successfully!")