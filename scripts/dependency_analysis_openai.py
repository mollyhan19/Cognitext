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
        sections = [section["content"] for section in article["sections"]]
        article_content = "\n\n".join(sections)  # Combine section contents into one string
        # Append title and content to the articles list
        articles.append({
            "title": title,
            "content": article_content,
            "category": article["category"]
        })
    return articles

# Function to extract dependencies
def extract_dependencies(article_content):
    prompt = (f'''
    Your task is to categorize and extract dependencies and relationships between key concepts from the text. For each paragraph or section, follow these steps: 
    1. Identify relationship types: 
    a. First, classify the relationship as either discourse (based on linguistic markers) or semantic (based on domain-specific knowledge). 
    b. Then, specify the exact relation type (e.g., causal, temporal, hierarchical, pathway, logical, etc.).
    2. For each relationship identified: 
    a. Assign each relationship a unique ID (e.g., D1 for discourse, S1 for semantic).
    b. Identify the linguistic or conceptual marker used to establish the relationship.
    c. Provide exact text evidence showing the two related concepts and the exact sentence where they occur.
    d. Ensure that the number of unique IDs and evidence matches the frequency of occurrences. This means each instance of a relationship should have its own unique ID and corresponding evidence.
    3. Counting the frequency at the relationship-type level, based on the number of distinct instances (e.g., temporal_sequence: 3).
    4. Identify any cross-section relationships.
    
    Output the relationships in this exact JSON structure:
    {{
      "discourse_relationships": {{
        "temporal_sequence": {{
          "lifecycle": [
            {{
              "id": "D1",
              "evidence": "The eggs develop in gonads of female medusae...",
              "marker": "develop"
            }},
            {{
              "id": "D2",
              "evidence": "Fertilized eggs develop into planula larvae...",
              "marker": "develop into"
            }},
            {{
              "id": "D3",
              "evidence": "...which settle onto the sea floor...",
              "marker": "settle"
            }}
          ],
          "frequency": 3
        }}
      }}
    }}
    Text to analyze: {article_content}
    ''')

    response = client.chat.completions.create(model="gpt-4-turbo",
    messages=[
        {"role": "system", "content": "You are an experienced linguist specializing in dependency analysis."},
        {"role": "user", "content": prompt}
    ],
    max_tokens=2048,
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
    with open("/Users/mollyhan/PycharmProjects/Cognitext/data/sample_analysis_output_openai_raw.json", "w") as output_file:
        json.dump(all_relationships, output_file, indent=4)

    print("All relationships extracted and saved to 'sample_analysis_output_openai_raw.json'.")

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
    Analyze frequencies and patterns within categories.
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
        discourse_rels = relationships.get("discourse_relationships", {})

        # Count different types of discourse relationships
        for rel_type, rel_content in discourse_rels.items():
            # Add to relationship types
            analysis["relationship_types"][category].add(rel_type)
            category_stats["relationship_counts"][rel_type] += 1

            # Count evidence instances
            if isinstance(rel_content, dict):
                for subtype in rel_content.values():
                    if isinstance(subtype, list):
                        category_stats["evidence_counts"] += len(subtype)

    # Convert sets to lists for JSON serialization
    analysis["relationship_types"] = {category: list(types) for category, types in
                                      analysis["relationship_types"].items()}

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
    # articles = load_articles("/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json")
    # process_all_articles(articles)

    # input_file = "/Users/mollyhan/PycharmProjects/Cognitext/data/sample_analysis_output_openai_raw.json"
    # output_file = "/Users/mollyhan/PycharmProjects/Cognitext/data/sample_analysis_output_openai.json"
    # analysis_output = "/Users/mollyhan/PycharmProjects/Cognitext/data/sample_freq_output_openai.json"

    # Load and parse the JSON with category organization
    # parsed_data = load_and_parse_json(input_file)
    # Save the categorized data
    # save_formatted_json(parsed_data, output_file)

    # Perform category analysis
    # category_analysis = analyze_category_frequencies(parsed_data)

    # Save the analysis
    # save_formatted_json(category_analysis, analysis_output)

    # Print readable analysis
    # print_category_analysis(category_analysis)



    # Paths to files
    input_file = "/Users/mollyhan/PycharmProjects/Cognitext/data/sample_analysis_output_openai.json"
    analysis_output = "/Users/mollyhan/PycharmProjects/Cognitext/data/sample_freq_output_openai.json"

    # Load the pre-formatted JSON with categorized data
    with open(input_file, 'r') as f:
        parsed_data = json.load(f)

    # Perform category analysis
    category_analysis = analyze_category_frequencies(parsed_data)

    # Save the analysis results
    save_formatted_json(category_analysis, analysis_output)

    # Print a readable version of the analysis
    # print_category_analysis(category_analysis)




