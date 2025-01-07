from dataclasses import dataclass
from typing import List, Dict
import json
from openai import OpenAI
import os
from cache_manager import CacheManager
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class RelationshipExtractor:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.cache_manager = CacheManager()  # Reuse your existing cache manager
        self.memory_cache = {}

    def _clean_markdown_json(self, json_str: str) -> str:
        """Clean JSON string from markdown formatting."""
        if json_str.startswith('```'):
            parts = json_str.split('```')
            if len(parts) >= 3:
                json_str = parts[1]
            else:
                json_str = parts[-1]

            if '\n' in json_str:
                json_str = json_str.split('\n', 1)[1]

        return json_str.replace('```', '').strip()

    def extract_relationships(self, concepts: List[Dict], text: str) -> Dict:
        """Extract meaningful relationships between concepts from text."""

        # Format concepts into a more readable format for the prompt
        concept_summary = "\n".join([
            f"- {concept['id']} (Appears in paragraphs: {[a['paragraph'] for a in concept['appearances']]})"
            for concept in concepts[:50]  # Limit to first 20 concepts to avoid token limits
        ])

        prompt = f"""
        Your task is to analyze how concepts connect across the entire text. Even if concepts are found in different paragraphs or sections, identify relationships that would help readers understand connections or dependencies.
        1. Have clear evidence in the text
        2. Help explain how concepts connect or influence each other
        3. Aid in comprehending the overall topic

        For each relationship identified, provide:
        1. The source and target concepts
        2. A clear description of their relationship
        3. Evidence from the text
        4. An explanation of how this relationship aids comprehension

        Key concepts from the text:
        {concept_summary}

        Full text for analysis:
        {text}

        Return only relationships that have strong textual evidence and genuinely aid comprehension.
        Format your response as a JSON object with this structure:
        {{
            "relationships": [
                {{
                    "source_concept": "concept from list",
                    "target_concept": "concept from list",
                    "relationship_type": "type of relationship",
                    "relationship_description": "clear explanation of how they relate",
                    "evidence": "quote from text",
                    "location": {{"paragraph": paragraph_number}},
                    "comprehension_value": "how this helps understanding"
                }}
            ]
        }}
        """

        # Check cache
        cache_key = f"{hash(text)}_relationships"
        cached_result = self.cache_manager.get_cached_entities(cache_key)
        if cached_result:
            return cached_result

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2000
            )

            # Parse response
            response_text = response.choices[0].message.content
            cleaned_json = self._clean_markdown_json(response_text)
            relationships = json.loads(cleaned_json)

            # Cache result
            self.cache_manager.cache_entities(cache_key, relationships)

            return relationships

        except Exception as e:
            print(f"Error extracting relationships: {str(e)}")
            return {"relationships": []}

    def analyze_relationship_patterns(self, relationships: Dict) -> Dict:
        """Analyze patterns in extracted relationships."""
        analysis = {
            "total_relationships": len(relationships["relationships"]),
            "relationship_types": {},
            "most_connected_concepts": {},
            "paragraph_distribution": {}
        }

        # Analyze relationship types
        for rel in relationships["relationships"]:
            rel_type = rel["relationship_type"]
            analysis["relationship_types"][rel_type] = analysis["relationship_types"].get(rel_type, 0) + 1

            # Track concept connections
            for concept in [rel["source_concept"], rel["target_concept"]]:
                analysis["most_connected_concepts"][concept] = analysis["most_connected_concepts"].get(concept, 0) + 1

            # Track paragraph distribution
            para = rel["location"]["paragraph"]
            analysis["paragraph_distribution"][para] = analysis["paragraph_distribution"].get(para, 0) + 1

        return analysis


def get_full_text(article_data):
    """Extract full text from article data structure."""
    text_parts = []

    for section in article_data["sections"]:
        for heading, content in section.items():
            # Add main text
            text_parts.extend(content["text"])

            # Add text from subheadings
            if content["subheadings"]:
                for subheading, subcontent in content["subheadings"].items():
                    text_parts.extend(subcontent.get("text", []))

    return "\n".join(text_parts)


def main():
    print("Starting relationship extraction process...")

    load_dotenv("/Users/mollyhan/PycharmProjects/Cognitext/.env")
    api_key = os.getenv("OpenAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI_API_KEY not found in environment variables")

    extractor = RelationshipExtractor(api_key)

    # Load entity analysis results
    print("Loading entity analysis results...")
    with open("/Users/mollyhan/PycharmProjects/Cognitext/data/entity_analysis_results.json", "r") as f:
        entity_results = json.load(f)

    # Load original text data
    print("Loading original text data...")
    with open("/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json", "r") as f:
        text_data = json.load(f)

    results = {}

    # Process each article
    for article_title, article_data in entity_results["analysis_results"].items():
        print(f"\nProcessing relationships for: {article_title}")

        # Get full text for this article
        text_content = get_full_text(text_data["articles"][article_title])

        # Extract relationships
        relationships = extractor.extract_relationships(
            article_data["entities"],
            text_content
        )

        # Analyze patterns
        analysis = extractor.analyze_relationship_patterns(relationships)

        results[article_title] = {
            "relationships": relationships,
            "analysis": analysis
        }

        # Print some stats
        print(f"Found {len(relationships['relationships'])} relationships")
        print("Relationship types:", list(analysis["relationship_types"].keys()))
        print("Most connected concepts:", sorted(
            analysis["most_connected_concepts"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5])

    # Save results
    output_path = "/Users/mollyhan/PycharmProjects/Cognitext/data/relationship_analysis_results.json"
    print(f"\nSaving results to {output_path}")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print("\nRelationship extraction and analysis complete!")

if __name__ == "__main__":
    main()