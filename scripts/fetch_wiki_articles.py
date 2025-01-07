import requests
from openai import OpenAI
from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup
import json
import re
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ArticlePair:
    """Represents a pair of related articles with their relationship metrics."""
    seed_title: str
    related_title: str
    similarity_metrics: Dict
    learning_transfer_risk: float
    explanation: str
    content: Dict


class WikipediaAPI:
    """Handles all Wikipedia API interactions."""

    def __init__(self):
        self.base_url = "https://en.wikipedia.org/w/api.php"

    def fetch_article_html(self, title: str) -> Optional[str]:
        """Fetch article HTML content from Wikipedia."""
        params = {
            "action": "parse",
            "page": title,
            "format": "json",
            "prop": "text",
            "redirects": True
        }
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            return data["parse"]["text"]["*"] if "parse" in data else None
        except Exception as e:
            print(f"Error fetching {title}: {str(e)}")
            return None

    def get_article_length(self, title: str) -> Optional[int]:
        """Get the length of an article."""
        params = {
            "action": "query",
            "titles": title,
            "prop": "revisions",
            "rvprop": "size",
            "format": "json"
        }
        try:
            response = requests.get(self.base_url, params=params)
            data = response.json()
            pages = data["query"]["pages"]
            page = next(iter(pages.values()))
            return page["revisions"][0]["size"] if "revisions" in page else None
        except Exception as e:
            print(f"Error getting article length for {title}: {str(e)}")
            return None

    def get_linked_articles(self, title: str) -> List[str]:
        """Get articles that are directly linked from the given article."""
        params = {
            "action": "query",
            "titles": title,
            "prop": "links",
            "pllimit": "max",
            "format": "json"
        }
        try:
            response = requests.get(self.base_url, params=params)
            data = response.json()
            pages = data["query"]["pages"]

            linked_articles = []
            for page_id in pages:
                if "links" in pages[page_id]:
                    linked_articles.extend([link["title"] for link in pages[page_id]["links"]])
            return linked_articles
        except Exception as e:
            print(f"Error getting links: {str(e)}")
            return []

    def get_category_articles(self, title: str) -> List[str]:
        """Get articles that share categories with the given article."""
        # First get categories
        params = {
            "action": "query",
            "titles": title,
            "prop": "categories",
            "cllimit": "max",
            "format": "json"
        }
        try:
            response = requests.get(self.base_url, params=params)
            data = response.json()
            pages = data["query"]["pages"]

            categories = []
            for page_id in pages:
                if "categories" in pages[page_id]:
                    categories.extend([cat["title"] for cat in pages[page_id]["categories"]])

            # Then get articles from these categories
            related_articles = []
            for category in categories:
                params = {
                    "action": "query",
                    "list": "categorymembers",
                    "cmtitle": category,
                    "cmlimit": "max",
                    "cmtype": "page",
                    "format": "json"
                }
                response = requests.get(self.base_url, params=params)
                data = response.json()
                if "query" in data and "categorymembers" in data["query"]:
                    related_articles.extend([page["title"] for page in data["query"]["categorymembers"]])

            return [article for article in related_articles if article != title]
        except Exception as e:
            print(f"Error getting category members: {str(e)}")
            return []


class ContentParser:
    """Handles parsing and cleaning of Wikipedia content."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text."""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\[\d+\]', '', text)
        return text.strip()

    def parse_article_content(self, html_content: str, category: str, title: str) -> Dict:
        """Parse Wikipedia HTML content into structured format."""
        article_data = {
            "schema": {"schema_type": "WikiArticles", "schema_version": "1.0"},
            "title": title,
            "category": category,
            "sections": []
        }

        soup = BeautifulSoup(html_content, "html.parser")
        current_section = None
        current_subheading = None

        for element in soup.find_all(['h2', 'h3', 'p']):
            if element.name == 'h2':
                section_title = self.clean_text(element.get_text().replace("[edit]", ""))
                if section_title in ["See also", "References", "External links"]:
                    continue
                current_section = {
                    f"heading: {section_title}": {
                        "text": [],
                        "subheadings": {}
                    }
                }
                article_data["sections"].append(current_section)
                current_subheading = None
            elif element.name == 'h3' and current_section:
                subheading_title = self.clean_text(element.get_text().replace("[edit]", ""))
                current_subheading = f"subheading: {subheading_title}"
                list(current_section.values())[0]["subheadings"][current_subheading] = {"text": []}
            elif element.name == 'p' and current_section:
                paragraph_text = self.clean_text(element.get_text())
                if current_subheading:
                    list(current_section.values())[0]["subheadings"][current_subheading]["text"].append(paragraph_text)
                else:
                    list(current_section.values())[0]["text"].append(paragraph_text)

        return article_data


class ArticleEvaluator:
    """Handles article similarity and independence evaluation."""

    def __init__(self, openai_key: str, seed_articles: Dict[str, List[str]]):
        self.client = OpenAI(api_key=openai_key)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.max_candidates_per_request = 20
        self.min_article_length = 2000  # Minimum article length in characters
        # Flatten seed articles for easy checking
        self.all_seed_articles = [
            title for category_titles in seed_articles.values()
            for title in category_titles
        ]

    def filter_candidates(self, wiki_api: WikipediaAPI, candidates: List[str]) -> List[str]:
        """Filter candidates based on quality criteria."""
        filtered = []
        for title in candidates:
            # Skip if it's a seed article
            if title in self.all_seed_articles:
                continue

            # Skip meta pages and other unsuitable articles
            if any(x in title for x in [
                'Category:', 'Template:', 'Wikipedia:',
                'Help:', 'File:', 'Talk:', 'User:',
                'disambiguation', 'List of'
            ]):
                continue

            # Check article length
            length = wiki_api.get_article_length(title)
            if length and length >= self.min_article_length:
                filtered.append(title)
            else:
                print(f"Skipping {title} - too short ({length if length else 'unknown'} chars)")

        return filtered

    def chunk_candidates(self, candidates: List[str]) -> List[List[str]]:
        """Split candidates into smaller chunks to avoid token limits."""
        return [candidates[i:i + self.max_candidates_per_request]
                for i in range(0, len(candidates), self.max_candidates_per_request)]

    def evaluate_independence(self, seed_title: str, candidate_titles: List[str], wiki_api: WikipediaAPI) -> List[Dict]:
        """Evaluate which articles are sufficiently independent using LLM."""
        # First filter candidates
        filtered_candidates = self.filter_candidates(wiki_api, candidate_titles)
        if not filtered_candidates:
            print(f"No suitable candidates found for {seed_title}")
            return []

        # Split filtered candidates into chunks
        candidate_chunks = self.chunk_candidates(filtered_candidates)
        all_selections = []

        for chunk in candidate_chunks:
            prompt = f"""For the seed article "{seed_title}", evaluate these potential related articles:
            {json.dumps(chunk, indent=2)}

            Select up to 3 articles that meet ALL these criteria:
            1. Are substantive, well-developed articles
            2. Are related to {seed_title} but focus on different aspects
            3. Would be understandable WITHOUT having read {seed_title}
            4. Cover different enough topics to avoid learning transfer
            5. Are general or foundational topics in the field

            Format your response as a JSON array of objects with these fields:
            - title: The exact article title
            - relevance: Why it's related but different
            - independence: Why it can be learned independently
            - topic_type: Either "general_concept", "specific_application", or "related_field"

            If no articles in this set are suitable, return an empty array []."""

            try:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are helping select related but independently learnable articles. Prefer general, well-established topics over narrow or obscure ones."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2
                )

                chunk_selections = json.loads(response.choices[0].message.content)

                # Additional validation of selections
                validated_selections = []
                for selection in chunk_selections:
                    # Double-check length requirement
                    length = wiki_api.get_article_length(selection["title"])
                    if length and length >= self.min_article_length:
                        # Prefer general concepts
                        if selection.get("topic_type") == "general_concept":
                            validated_selections.insert(0, selection)
                        else:
                            validated_selections.append(selection)

                all_selections.extend(validated_selections)

                # If we have enough selections, stop processing more chunks
                if len(all_selections) >= 3:
                    return all_selections[:3]

            except Exception as e:
                print(f"Error processing chunk: {str(e)}")
                continue

        return all_selections[:3]

class RelatedArticleFinder:
    """Main class for finding related articles."""

    def __init__(self, openai_key: str, seed_articles: Dict[str, List[str]]):
        self.wiki_api = WikipediaAPI()
        self.parser = ContentParser()
        self.evaluator = ArticleEvaluator(openai_key, seed_articles)

    def filter_candidates(self, candidates: List[str]) -> List[str]:
        """Filter out obviously unsuitable candidates before LLM evaluation."""
        filtered = []
        for title in candidates:
            # Skip meta pages and other unsuitable articles
            if any(x in title for x in [
                'Category:', 'Template:', 'Wikipedia:',
                'Help:', 'File:', 'Talk:', 'User:',
                'disambiguation', 'List of'
            ]):
                continue
            filtered.append(title)
        return filtered

    def find_related_articles(self, seed_title: str, category: str) -> List[ArticlePair]:
        """Find related but independent articles for a seed article."""
        # Get candidate articles
        linked_articles = self.wiki_api.get_linked_articles(seed_title)
        category_articles = self.wiki_api.get_category_articles(seed_title)

        # Combine and remove duplicates
        all_candidates = list(set(linked_articles + category_articles))

        # Evaluate candidates
        selected_articles = self.evaluator.evaluate_independence(
            seed_title, all_candidates, self.wiki_api
        )

        # Create article pairs
        article_pairs = []
        for article in selected_articles:
            html_content = self.wiki_api.fetch_article_html(article["title"])
            if html_content:
                content = self.parser.parse_article_content(html_content, category, article["title"])
                pair = ArticlePair(
                    seed_title=seed_title,
                    related_title=article["title"],
                    similarity_metrics={},  # Add metrics as needed
                    learning_transfer_risk=0.0,  # Add calculation as needed
                    explanation=article.get("explanation", ""),
                    content=content
                )
                article_pairs.append(pair)

        return article_pairs


def main():
    load_dotenv()

    # Define seed articles first
    seed_articles = {
        "biology": ["Quantum biology","Quorum sensing","Symbiogenesis"]
    }

    # Initialize finder with both API key and seed articles
    finder = RelatedArticleFinder(
        openai_key=os.getenv("OpenAI_API_KEY"),
        seed_articles=seed_articles
    )

    all_articles = {"articles": {}}

    for category, titles in seed_articles.items():
        for title in titles:
            print(f"Processing {title}...")
            related_pairs = finder.find_related_articles(title, category)

            # Store results
            html_content = finder.wiki_api.fetch_article_html(title)
            if html_content:
                seed_content = finder.parser.parse_article_content(html_content, category, title)
                all_articles["articles"][title] = seed_content
                all_articles["articles"][title]["related_articles"] = [
                    {
                        "title": pair.related_title,
                        "explanation": pair.explanation,
                        "similarity_metrics": pair.similarity_metrics,
                        "learning_transfer_risk": pair.learning_transfer_risk,
                        "parsed_content": pair.content
                    }
                    for pair in related_pairs
                ]

    # Save results
    json_file_path = "/Users/mollyhan/PycharmProjects/Cognitext/data/text_corpus.json"
    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(all_articles, json_file, ensure_ascii=False, indent=4)

    print(f"All articles fetched and stored in '{json_file_path}' successfully!")

if __name__ == "__main__":
    main()