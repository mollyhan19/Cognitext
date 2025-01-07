# fetching articles for data-driven approach
# identifying common dependencies among different categories by
# feeding certain articles within one category to LLMs to extract dependencies
# group LLM response to identify common relations found in certain category

import requests
from bs4 import BeautifulSoup
import json
import re

def fetch_wikipedia_html(title):
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "parse",
        "page": title,
        "format": "json",
        "prop": "text",
        "redirects": True
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    if "parse" in data and "text" in data["parse"]:
        return data["parse"]["text"]["*"]
    else:
        print(f"Page '{title}' does not exist.")
        return None


def clean_text(text):
    # Remove excess whitespace, including newlines, and trim text
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_wikipedia_content(html_content, category, title):
    # Initialize article_data with schema and title
    article_data = {
        "schema": {
            "schema_type": "WikiArticles",
            "schema_version": "1.0"
        },
        "title": title,
        "category": category,
        "sections": []
    }

    soup = BeautifulSoup(html_content, "html.parser")
    current_section = None
    current_subheading = None

    for element in soup.find_all(['h2', 'h3', 'p']):
        if element.name == 'h2':  # Top-level section headers
            section_title = clean_text(element.get_text().replace("[edit]", ""))
            if section_title in ["See also", "References", "External links"]:
                continue
            # Initialize a new section
            current_section = {
                f"heading: {section_title}": {
                    "text": [],
                    "subheadings": {}
                }
            }
            article_data["sections"].append(current_section)
            current_subheading = None  # Reset subheading when starting a new section

        elif element.name == 'h3' and current_section:  # Subsection headers
            subheading_title = clean_text(element.get_text().replace("[edit]", ""))
            current_subheading = f"subheading: {subheading_title}"
            # Add subheading under the current section
            list(current_section.values())[0]["subheadings"][current_subheading] = {"text": []}

        elif element.name == 'p' and current_section:
            paragraph_text = clean_text(element.get_text())
            # Replace math formulas with LaTeX format inline
            for math in element.find_all("span", {"class": "mwe-math-element"}):
                latex_formula = math.get("alttext", "")
                if latex_formula:
                    paragraph_text = paragraph_text.replace(math.get_text(), f"${latex_formula}$")

            # Append cleaned paragraph to the current section or subheading
            if current_subheading:
                # Add to the current subheading's text
                list(current_section.values())[0]["subheadings"][current_subheading]["text"].append(paragraph_text)
            else:
                # Add directly to the section's main text
                list(current_section.values())[0]["text"].append(paragraph_text)

    return article_data

# Seed articles setup
seed_articles = {
    "biology": [
        "Tardigrade"
    ]
}

all_articles = {"articles": {}}

# Fetch and parse content for each seed article
for category, titles in seed_articles.items():
    for title in titles:
        html_content = fetch_wikipedia_html(title)
        if html_content:
            parsed_content = parse_wikipedia_content(html_content, category, title)
            all_articles["articles"][title] = parsed_content

# Save to JSON file
json_file_path = "/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json"
with open(json_file_path, 'w', encoding='utf-8') as json_file:
    json.dump(all_articles, json_file, ensure_ascii=False, indent=4)

print(f"All articles fetched and stored in '{json_file_path}' successfully!")
