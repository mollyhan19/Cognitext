# fetching articles for data-driven approach
# identifying common dependencies among different categories by
# feeding certain articles within one category to LLMs to extract dependencies
# group LLM response to identify common relations found in certain category

import wikipediaapi
import json

# Initialize Wikipedia API
wiki_wiki = wikipediaapi.Wikipedia('fetching_wiki_samples')

# Seed articles with categories and titles
seed_articles = {
    "biology": [
        "Tardigrade"
    ]
}

def fetch_article_content(title, category):
    page = wiki_wiki.page(title)
    if not page.exists():
        print(f"Page {title} does not exist.")
        return None

    # Helper function to split content into paragraphs
    def split_into_paragraphs(text):
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        return paragraphs

    # Extract the opening section as a pseudo-section
    opening_section = {
        "section_title": "Introduction",
        "content": split_into_paragraphs(page.summary),
        "subsections": []
    }

    # Function to extract sections and subsections
    def extract_sections(section):
        sections_list = []
        for s in section.sections:
            sections_list.append({
                "section_title": s.title,
                "content": split_into_paragraphs(s.text),
                "subsections": extract_sections(s)
            })
        return sections_list

    sections = extract_sections(page)

    # Prepend the opening section to the sections list
    sections.insert(0, opening_section)

    # Create JSON structure
    article_data = {
        "schema": {
            "schema_type": "WikiArticles",
            "schema_version": "1.0"
        },
        "title": title,
        "category": category,
        "sections": sections
    }
    return article_data

# Store all articles data
all_articles_data = []

# Fetch data for each article
for category, titles in seed_articles.items():
    for title in titles:
        article_data = fetch_article_content(title, category)
        if article_data:
            all_articles_data.append(article_data)

# Save to JSON file
json_file_path = "/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json"
with open(json_file_path, 'w') as json_file:
    json.dump(all_articles_data, json_file, indent=4)

print("Articles fetched and stored successfully.")
