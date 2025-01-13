# fetching articles for data-driven approach
# identifying common dependencies among different categories by
# feeding certain articles within one category to LLMs to extract dependencies
# group LLM response to identify common relations found in certain category

import wikipediaapi
import json
import re
from bs4 import BeautifulSoup
import requests

wiki_wiki = wikipediaapi.Wikipedia('fetching_wiki_samples')

def clean_wiki_text(text):
    """Clean wiki text by handling LaTeX and mathematical expressions."""
    # Replace LaTeX display style expressions with their text content
    text = re.sub(r'\{\\displaystyle (.*?)\}', r'\1', text)
    
    # Handle mathematical symbols
    math_replacements = {
        '\\mathbf': '',
        '\\text': '',
        '\\in': '∈',
        '\\Sigma': 'Σ',
        '\\ast': '*',
        '^{*}': '*',
        '_{M}': '_M'
    }
    
    for old, new in math_replacements.items():
        text = text.replace(old, new)
    
    # Remove remaining LaTeX markers
    text = re.sub(r'\{\\.*?\}', '', text)
    
    return text.strip()

def split_into_paragraphs(text):
    """
    Split text into paragraphs while preserving formulas.
    A real paragraph should:
    1. End with a sentence-ending punctuation
    2. Be followed by a newline
    3. Have reasonable length
    """
    # First clean the text of excessive newlines/spaces
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Normalize paragraph breaks
    text = re.sub(r' +', ' ', text)  # Normalize spaces
    
    # Split on sentence endings followed by newlines
    potential_paragraphs = re.split(r'([.!?])\s*\n+', text)
    
    paragraphs = []
    current_para = ""
    
    for i in range(0, len(potential_paragraphs), 2):
        if i < len(potential_paragraphs):
            # Add current piece
            current_para += potential_paragraphs[i]
            
            # If there's punctuation after this piece, it's a paragraph end
            if i + 1 < len(potential_paragraphs):
                current_para += potential_paragraphs[i + 1]  # Add the punctuation
                if current_para.strip():  # Only add non-empty paragraphs
                    # Clean the paragraph
                    cleaned_para = clean_wiki_text(current_para)
                    if len(cleaned_para) > 20:  # Minimum length check
                        paragraphs.append(cleaned_para)
                current_para = ""
            
    # Add any remaining text as a paragraph
    if current_para.strip():
        cleaned_para = clean_wiki_text(current_para)
        if len(cleaned_para) > 20:
            paragraphs.append(cleaned_para)

    return paragraphs

def fetch_article_content(title, category):
    page = wiki_wiki.page(title)
    if not page.exists():
        print(f"Page {title} does not exist.")
        return None

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
    sections.insert(0, opening_section)

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

def save_articles(seed_articles, output_path):
    """Save processed articles to JSON file."""
    all_articles = {"articles": {}}
    
    for category, titles in seed_articles.items():
        for title in titles:
            print(f"Processing {title}...")
            article_data = fetch_article_content(title, category)
            if article_data:
                all_articles["articles"][title] = article_data
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_articles, f, indent=4, ensure_ascii=False)

    print(f"Articles saved to {output_path}")

# Example usage
seed_articles = {
    "computer science": ["P versus NP problem"],
    "biology": ["Tardigrades"], 
    "history": ["Lost Colony of Roanoke"],
    "philosophy": ["Epistemic injustice"],
    "political_science": ["Consociationalism"],
    "linguistics": ["Garden path sentence"],
    "arts": ["Fluxus"],
    "math/stats": ["Mandelbrot set"],
    "health/medicine": ["Cryotherapy"],
    "general": ["Mandela effect"]
}

save_articles(seed_articles, "/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json")
