import wikipediaapi
import json
import os

# custom user agent
user_agent = "Cognitext/1.0 (https://github.com/mollyhan19/Cognitext; molly.han@emory.edu)"
wiki_wiki = wikipediaapi.Wikipedia(user_agent)

def count_words(text):
    return len(text.split())

# fetching article content
def fetch_article_content(title):
    page = wiki_wiki.page(title)
    if not page.exists():
        print(f"Article '{title}' does not exist.")
        return None

    article_data = {
        "title": page.title,
        "word_count": count_words(page.text),  # Add word count
        "sections": []
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

# List of article titles to fetch
article_titles = ["Zipf's law", "Ottoman Empire", "Extremophile", "Quorum sensing"]

# Initialize the data structure
all_articles = {"articles": {}}

# Fetch each article and append to the list
for title in article_titles:
    article_content = fetch_article_content(title)
    if article_content:
        all_articles["articles"][title] = article_content

# Path to the text_corpus.json file in the /data directory
json_file_path = "/Users/mollyhan/PycharmProjects/Cognitext/data/text_corpus.json"

# Write all articles to the JSON file
with open(json_file_path, 'w') as json_file:
    json.dump(all_articles, json_file, indent=4)

print(f"All articles fetched and stored in '{json_file_path}' successfully!")
