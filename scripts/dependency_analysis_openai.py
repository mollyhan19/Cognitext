from datetime import datetime
from openai import OpenAI
import json
import os
import re
from dotenv import load_dotenv
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Load environment variables from .env file (make sure your API key is in this file)
load_dotenv()
client = OpenAI(api_key=os.getenv("OpenAI_API_KEY"))

# Load and preprocess articles from JSON file
def load_articles(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    articles = []

    # Extract articles from the JSON structure
    for title, article in data["articles"].items():
        sections_content = []

        # Iterate through each section and preserve its heading
        for section in article["sections"]:
            for heading, content in section.items():  # Access the heading and its content
                # Append the heading itself to make it part of the analysis
                sections_content.append(f"Section: {heading}")

                # Add the main text content
                sections_content.extend(content["text"])

                # Add subheading text, if available
                for subheading, subcontent in content["subheadings"].items():
                    sections_content.append(f"Subheading: {subheading}")
                    sections_content.extend(subcontent["text"])

        article_content = "\n\n".join(sections_content)  # Combine section contents into one string

        # Append title, content, and category to the articles list
        articles.append({
            "title": title,
            "content": article_content,
            "category": article["category"]
        })

    return articles

@dataclass
class TextChunk:
    content: str
    paragraphs: List[str]  # Store individual paragraphs
    paragraph_indices: List[int]  # Global paragraph indices
    section: str
    overlap_prev: List[str] = None  # Previous chunk's last paragraphs
    overlap_next: List[str] = None  # Next chunk's first paragraphs

    def __post_init__(self):
        self.overlap_prev = self.overlap_prev or []
        self.overlap_next = self.overlap_next or []


def preprocess_text(
        articles_list: list,  # Changed parameter name and type hint
        chunk_size: int = 3,
        overlap_size: int = 1
) -> Tuple[List[TextChunk], List[str]]:
    chunks = []
    sentence_mapping = []

    # Loop through articles in list
    for article in articles_list:
        category = article.get("category", "unknown")
        content = article["content"]

        # Split content into sections
        sections = content.split("Section: ")

        for section in sections:
            if not section.strip():
                continue

            # Extract paragraphs
            paragraphs = [p.strip() for p in section.split('\n\n') if p.strip()]
            if not paragraphs:
                continue

            section_name = paragraphs[0] if paragraphs else "Unknown Section"

            # Create chunks with overlap
            for i in range(0, len(paragraphs), chunk_size - overlap_size):
                chunk_paragraphs = paragraphs[i:i + chunk_size]
                chunk_paragraph_indices = list(range(i, i + len(chunk_paragraphs)))

                # Define overlaps
                overlap_prev = paragraphs[max(0, i - overlap_size):i]
                overlap_next = paragraphs[i + chunk_size:i + chunk_size + overlap_size]

                chunk = TextChunk(
                    content="\n\n".join(chunk_paragraphs),
                    paragraphs=chunk_paragraphs,
                    paragraph_indices=chunk_paragraph_indices,
                    section=section_name,
                    overlap_prev=overlap_prev,
                    overlap_next=overlap_next
                )
                chunks.append(chunk)

    return chunks, sentence_mapping

# Functions to extract dependencies

def extract_concepts(chunk: TextChunk):
    """
    Extract key concepts from a chunk and ground them in evidence.
    """
    # TODO: prompt engineering
    # Example LLM prompt for concept extraction
    prompt = f"""
    Analyze the following text and extract key concepts. For each concept:
    1. Provide the concept name.
    2. Specify the location (sentence or paragraph index).
    3. Include the exact sentence(s) as evidence.

    Text:
    {chunk.content}
    """

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": "You are an expert at analyzing text and extracting meaningful relationships between concepts, with a special focus on making complex information more understandable. "},
                  {"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.2,
        n=1,
        stop=None)

    # Process the response into a structured format
    response_content = response.choices[0].message.content.strip()
    try:
        # Handle case where response might include markdown code blocks
        if response_content.startswith("```") and response_content.endswith("```"):
            response_content = response_content[3:-3].strip()
        if response_content.startswith("```json"):
            response_content = response_content[7:].strip()

        concepts = json.loads(response_content)
        return concepts
    except json.JSONDecodeError:
        print(f"Error parsing response: {response_content}")
        return []

def extract_relations(chunk: TextChunk, concepts: List[dict]):
    """
    Extract relationships between concepts within the chunk.
    """
    # Example LLM prompt for relation extraction
    concept_names = ", ".join([c["concept"] for c in concepts])
    prompt = f"""
    Analyze the following text and identify relationships between these concepts:
    {concept_names}

    For each relationship:
    1. Specify the type of relationship (e.g., causal, hierarchical).
    2. List the two related concepts.
    3. Provide the sentence(s) as evidence.

    Text:
    {chunk.content}
    """
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "system",
                   "content": "You are an expert at analyzing text and extracting meaningful relationships between concepts, with a special focus on making complex information more understandable. "},
                  {"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=0.2,
        n=1,
        stop=None)

    response_content = response.choices[0].message.content.strip()
    try:
        if response_content.startswith("```") and response_content.endswith("```"):
            response_content = response_content[3:-3].strip()
        if response_content.startswith("```json"):
            response_content = response_content[7:].strip()

        relations = json.loads(response_content)
        return relations
    except json.JSONDecodeError:
        print(f"Error parsing response: {response_content}")
        return []

def analyze_overlaps(chunk: TextChunk, concepts: List[dict], relations: List[dict]):
    """
    Identify connections between concepts and relationships across overlapping chunks.
    """
    # Example LLM prompt for analyzing overlaps
    prompt = f"""
    Compare the following text with its overlapping paragraphs from adjacent chunks. 
    Based on the concepts and relationships provided, identify connections between chunks.

    Overlap Previous:
    {" ".join(chunk.overlap_prev)}

    Current Text:
    {chunk.content}

    Overlap Next:
    {" ".join(chunk.overlap_next)}

    Concepts:
    {", ".join([c["concept"] for c in concepts])}

    Relationships:
    {relations}

    For each connection:
    1. Specify the related concepts.
    2. State the type of connection (e.g., shared context, causal link).
    3. Provide evidence from both chunks.
    """

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "system",
                   "content": "You are an expert at analyzing text and extracting meaningful relationships between concepts, with a special focus on making complex information more understandable. "},
                  {"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0.2,
        n=1,
        stop=None)

    response_content = response.choices[0].message.content.strip()
    try:
        if "```" in response_content:
            response_content = response_content.split("```")[1]
            if response_content.startswith("json"):
                response_content = response_content[4:]

        response_content = response_content.strip()
        overlaps = json.loads(response_content)
        return overlaps
    except json.JSONDecodeError:
        print(f"Error parsing response: {response_content}")
        return []

def process_chunk(chunk: TextChunk):
    # Step 1: Extract concepts
    concepts = extract_concepts(chunk)

    # Step 2: Extract intra-chunk relationships
    relations = extract_relations(chunk, concepts)

    # Step 3: Analyze overlaps for inter-chunk connections
    overlaps = analyze_overlaps(chunk, concepts, relations)

    return {
        "concepts": concepts,
        "relations": relations,
        "overlaps": overlaps
    }

def clean_markdown_json(json_str: str) -> str:
    """
    Clean JSON string that contains markdown formatting
    """
    # Remove markdown code block markers if present
    if json_str.startswith('```'):
        # Split by ``` and take the content
        parts = json_str.split('```')
        # Get the JSON part (should be in the middle if properly formatted)
        if len(parts) >= 3:
            json_str = parts[1]
        else:
            json_str = parts[-1]

        # Remove language identifier if present (e.g., 'json\n')
        if '\n' in json_str:
            json_str = json_str.split('\n', 1)[1]

    # Remove any trailing markdown markers
    json_str = json_str.replace('```', '').strip()

    return json_str

def parse_relationships(relationships_str: str) -> Dict:
    """
    Parse relationships string, handling markdown formatting
    """
    try:
        # First, clean the markdown formatting
        cleaned_str = clean_markdown_json(relationships_str)

        # Parse the cleaned JSON
        return json.loads(cleaned_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON after cleaning: {str(e)}")
        return {"error": "Could not parse relationships", "raw_data": relationships_str}


def load_and_parse_json(file_path: str) -> Dict[str, Any]:
    """
    Load and parse JSON file, handling markdown-formatted JSON strings
    """
    try:
        # Load the original JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)

        # Create new dictionary for parsed data
        parsed_data = {}

        # Process each article
        for title, content in data.items():
            print(f"\nProcessing article: {title}")

            # Initialize the article entry
            parsed_data[title] = {
                "category": content.get("category", "Unknown")
            }

            # Parse relationships if present
            if "relationships" in content:
                if isinstance(content["relationships"], str):
                    parsed_relationships = parse_relationships(content["relationships"])
                    parsed_data[title]["relationships"] = parsed_relationships
                else:
                    parsed_data[title]["relationships"] = content["relationships"]

        return parsed_data

    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Error parsing JSON file: {str(e)}", e.doc, e.pos)


def process_and_save_results(articles_list: list, output_path: str):
    chunks, _ = preprocess_text(articles_list, chunk_size=2, overlap_size=1)

    results = {
        "analysis_date": datetime.now().isoformat(),
        "articles": {}
    }

    for article in articles_list:
        article_results = {
            "title": article["title"],
            "category": article["category"],
            "chunks": []
        }

        # Process chunks for this article
        article_chunks = [c for c in chunks if c.content in article["content"]]
        for chunk in article_chunks:
            concepts = extract_concepts(chunk)
            relations = extract_relations(chunk, concepts)
            overlaps = analyze_overlaps(chunk, concepts, relations)

            chunk_analysis = {
                "section": chunk.section,
                "concepts": concepts,
                "relations": relations,
                "overlaps": overlaps
            }
            article_results["chunks"].append(chunk_analysis)

        results["articles"][article["title"]] = article_results

    # Save results
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

# Main script execution
if __name__ == "__main__":
    articles = load_articles("/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json")
    process_and_save_results(articles, "/Users/mollyhan/PycharmProjects/Cognitext/data/sample_analysis_output_chunked_openai.json")
