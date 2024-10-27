# fetching articles for data-driven approach
# identifying common dependencies among different categories by
# feeding certain articles within one category to LLMs to extract dependencies
# group LLM response to identify common relations found in certain category

import wikipediaapi
import json
import os

# Custom user agent
user_agent = "Cognitext/1.0 (https://github.com/mollyhan19/Cognitext; molly.han@emory.edu)"
wiki_wiki = wikipediaapi.Wikipedia(user_agent)

def count_words(text):
    return len(text.split())

# Fetching article content
def fetch_wiki_content(title):
    page = wiki_wiki.page(title)
    if not page.exists():
        print(f"Article '{title}' does not exist.")
        return None

    article_data = {
        "schema": {
            "schema_type": "WikiArticles",
            "schema_version": "1.0"  # Version of your schema
        },
        "title": page.title,
        "word_count": count_words(page.text),  # Add word count
        "sections": []
    }

    # Recursive function to add sections and subsections properly
    def add_sections(sections, section_list):
        for section in sections:
            section_data = {
                "heading": section.title,
                "content": section.text,
                "subsections": []  # Initialize subsections
            }
            if section.sections:
                # Recursively add subsections within this section
                add_sections(section.sections, section_data["subsections"])
            section_list.append(section_data)

    # Start processing from top-level sections
    add_sections(page.sections, article_data["sections"])

    return article_data

# Seed articles (15 manually selected articles)
seed_articles = {
    "biology": [
        "Tardigrade",
        "Immortal jellyfish",
        "Quantum biology"]
}

# Initialize the data structure
all_articles = {
    "schema": {
        "schema_type": "ArticleData",
        "schema_version": "1.0"
    },
    "articles": {}
}

# Fetch each article from the seed articles and append to the list
for category, titles in seed_articles.items():
    for title in titles:
        article_content = fetch_wiki_content(title)
        if article_content:
            # Include category in the article data
            article_content["category"] = category
            all_articles["articles"][title] = article_content

# Path to the text_corpus.json file in the /data directory
json_file_path = "/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json"

# Write all articles to the JSON file
with open(json_file_path, 'w') as json_file:
    json.dump(all_articles, json_file, indent=4)

print(f"All articles fetched and stored in '{json_file_path}' successfully!")
