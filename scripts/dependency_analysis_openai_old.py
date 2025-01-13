from openai import OpenAI
import json
import os
from dotenv import load_dotenv
from collections import defaultdict, Counter
from typing import Dict, List, Any

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

# Function to extract dependencies
def extract_dependencies(article_content):
    prompt = f'''
    Your task is to analyze the following text in three stages that would help readers better comprehend the material: 
    1. CONCEPT REGISTRY: For each paragraph, identify and track key concepts with their definitions/contexts. Note any concepts that appear in multiple paragraphs 
    2. RELATION EXTRACTION: Identify relationships between concepts (local, near, and distant) 
    3. RELATION CHAINS: Assemble any chains of relations where concepts are linked across multiple paragraphs. Summarize all cross-paragraph relationships you've identified, including their source locations.

    Important Guidelines:
    1. For each relationship identified, provide: 
    - Source and target concepts with their paragraph locations 
    - Supporting evidence from the text 
    - Type of relation 
    2. Use simple, intuitive language for relationship types
    3. Consider both explicit and implicit relationships that aid comprehension
    4. Pay special attention to relationships that connect concepts across different paragraphs
    5. Identify domain-specific relationships that are crucial for understanding this particular subject

    Please output only the extracted relation types as valid JSON following the exact structure below. Do not use Concise Mode. Think step by step. 
    {{
        "concept_registry": [
            {{
                "concept_id": string,
                "first_appearance": {{
                    "section": string,
                    "paragraph": number
                }},
                "subsequent_mentions": [
                    {{
                        "section": string,
                        "paragraph": number
                    }}
                ],
                "brief_explanation": string
            }}
        ],
        "relations": [
            {{
                "relation_id": string,
                "source": {{
                    "concept": string,
                    "location": {{
                        "section": string,
                        "paragraph": number
                    }}
                }},
                "target": {{
                    "concept": string,
                    "location": {{
                        "section": string,
                        "paragraph": number
                    }}
                }},
                "relation_type": string,        // Use intuitive, readable phrases
                "readable_statement": string,    // Complete, clear statement of the relationship
                "evidence": string,             // Supporting text from the document
                "is_domain_specific": boolean,  // Whether this is a subject-specific relationship
                "crosses_paragraphs": boolean   // Whether this connects concepts from different paragraphs
            }}
        ],
        "concept_chains": [
            {{
                "chain_id": string,
                "description": string,
                "components": [
                    {{
                        "concept": string,
                        "location": {{
                            "section": string,
                            "paragraph": number
                        }},
                        "role": "start|intermediate|end"
                    }}
                ],
                "chain_summary": string  // A readable summary of how these concepts connect
            }}
        ]
    }}

    TEXT FOR ANALYSIS: {article_content}
    '''

    response = client.chat.completions.create(model="gpt-4-turbo",
    messages=[
        {"role": "system", "content": "You are an expert at analyzing text and extracting meaningful relationships between concepts, with a special focus on making complex information more understandable. "},
        {"role": "user", "content": prompt}
    ],
    max_tokens=4096,
    temperature=0.2,
    n=1,
    stop=None)

    return response.choices[0].message.content.strip()

def process_all_articles(articles):
    all_relationships = {}
    for article in articles:
        print(f"Processing article: {article['title']}")

        # Extract the category
        category = article.get("category", "Unknown")  # Default to "Unknown" if category is not found

        # Extract dependencies
        relationships = extract_dependencies(article["content"])

        # Create a new entry for each article, including title and category
        all_relationships[article["title"]] = {
            "category": category,
            "relationships": relationships
        }

    # Save results to a JSON file for easier analysis
    with open("/Users/mollyhan/PycharmProjects/Cognitext/data/sample_analysis_output_openai_raw_old.json", "w") as output_file:
        json.dump(all_relationships, output_file, indent=4)

    print("All relationships extracted and saved to 'sample_analysis_output_openai_raw_old.json'.")

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


def save_formatted_json(data: Dict[str, Any], file_path: str) -> None:
    """
    Save data to JSON file with proper formatting
    """
    try:
        with open(file_path, "w") as output_file:
            json.dump(data, output_file, indent=2)
        print(f"Successfully saved formatted data to '{file_path}'")
    except Exception as e:
        print(f"Error saving to file: {str(e)}")


def verify_parsed_data(parsed_data: Dict[str, Any]) -> None:
    """
    Verify the structure of parsed data
    """
    print("\nVerifying parsed data structure:")
    for title, content in parsed_data.items():
        print(f"\nArticle: {title}")
        print(f"Category: {content.get('category')}")
        relationships = content.get('relationships', {})
        if isinstance(relationships, dict):
            print("Relationships successfully parsed as dictionary")
            if 'discourse_relationships' in relationships:
                print("Found discourse_relationships structure")
        else:
            print(f"Relationships type: {type(relationships)}")


def analyze_category_frequencies(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze frequencies and patterns within categories, including semantic relationships.
    """
    analysis = {
        "category_counts": Counter(),
        "relationship_types": defaultdict(set),
        "category_statistics": {}
    }

    for title, content in data.items():
        # Extract category from each article's content
        category = content.get("category", "unknown")

        # Increment count of articles per category
        analysis["category_counts"][category] += 1

        # Initialize category-specific statistics if not already set
        if category not in analysis["category_statistics"]:
            analysis["category_statistics"][category] = {
                "total_articles": 0,
                "relationship_counts": defaultdict(int),
                "evidence_counts": 0
            }

        category_stats = analysis["category_statistics"][category]
        category_stats["total_articles"] += 1

        # Process relationships within each article
        relationships = content.get("relationships", {})

        # Ensure discourse relationships are captured
        discourse_rels = relationships.get("discourse_relationships", {})

        # Count different types of discourse relationships
        for rel_type, rel_content in discourse_rels.items():
            # Add to relationship types
            analysis["relationship_types"][category].add(rel_type)

            # Count evidence instances for this relationship type
            if isinstance(rel_content, dict):
                for subtype in rel_content.values():
                    if isinstance(subtype, list):
                        count = len(subtype)
                        category_stats["relationship_counts"][rel_type] += count
                        category_stats["evidence_counts"] += count

        # Check for semantic relationships if they exist
        semantic_rels = relationships.get("semantic_relationships", {})
        for rel_type, rel_content in semantic_rels.items():
            # Add to relationship types
            analysis["relationship_types"][category].add(rel_type)

            # Count evidence instances for this semantic relationship type
            if isinstance(rel_content, dict):
                for subtype in rel_content.values():
                    if isinstance(subtype, list):
                        count = len(subtype)
                        category_stats["relationship_counts"][rel_type] += count
                        category_stats["evidence_counts"] += count

    # Convert sets to lists for JSON serialization
    analysis["relationship_types"] = {category: list(types) for category, types in
                                      analysis["relationship_types"].items()}

    for category, stats in analysis["category_statistics"].items():
        stats["relationship_counts"] = dict(
            sorted(stats["relationship_counts"].items(), key=lambda item: item[1], reverse=True))

    return analysis

'''
def print_category_analysis(analysis: Dict[str, Any]) -> None:
    """
    Print readable analysis of the categorized data
    """
    print("\nCategory Analysis Summary:")
    print("=" * 50)

    # Print category counts
    print("\nArticles per Category:")
    for category, count in analysis["category_counts"].items():
        print(f"{category}: {count} articles")

    print("\nDetailed Category Statistics:")
    print("=" * 50)
    for category, stats in analysis["category_statistics"].items():
        print(f"\n{category}:")
        print(f"Total Articles: {stats['total_articles']}")
        print(f"Total Evidence Instances: {stats['evidence_counts']}")
        print("Relationship Types:")
        for rel_type, count in stats['relationship_counts'].items():
            print(f"  - {rel_type}: {count} instances")
'''

# Main script execution
if __name__ == "__main__":
    articles = load_articles("/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json")
    process_all_articles(articles)

    input_file = "/Users/mollyhan/PycharmProjects/Cognitext/data/sample_analysis_output_openai_raw_old.json"
    output_file = "/Users/mollyhan/PycharmProjects/Cognitext/data/sample_analysis_output_openai_old.json"
    # analysis_output = "/Users/mollyhan/PycharmProjects/Cognitext/data/sample_freq_output_openai.json"

    # Load and parse the JSON with category organization
    parsed_data = load_and_parse_json(input_file)
    save_formatted_json(parsed_data, output_file)

    # Load the pre-formatted JSON with categorized data
    # with open(output_file, 'r') as f:
        # parsed_data = json.load(f)

    # Perform category analysis
    # category_analysis = analyze_category_frequencies(parsed_data)
    # save_formatted_json(category_analysis, analysis_output)


    # Save the categorized data
    # save_formatted_json(parsed_data, output_file)

    # Perform category analysis
    # category_analysis = analyze_category_frequencies(parsed_data)

    # Save the analysis
    # save_formatted_json(category_analysis, analysis_output)

    # Print readable analysis
    # print_category_analysis(category_analysis)



    # Paths to files


    # Print a readable version of the analysis
    # print_category_analysis(category_analysis)