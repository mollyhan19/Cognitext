from anthropic import Anthropic
import json

# Initialize the client
anthropic = Anthropic(
    api_key='your-api-key'  # Replace with your API key
)

def analyze_text(text_content):
    prompt = f"""Analyze this text and output relationships in the following JSON structure:
    {{
      "Discourse relationships": [
        {{
          "relationship_type": "[type]": {{
            "Id": "[number]": {{
              "evidence": "[exact text from document]",
              "marker": "[specific words/phrases indicating relationship]"
            }},
            "frequency": [count of this relationship type]
          }}
        }}
      ],
      "Semantic relationships": [same structure as above]
    }}
    
    Guidelines:
    1. Discourse relationships: Focus on linguistic markers and explicit connections
    2. Semantic relationships: Focus on domain knowledge and conceptual connections
    3. For each relationship:
       - Include exact text evidence
       - Identify specific markers/indicators
       - Assign unique IDs
    4. Count frequencies based on actual identified instances only
    
    Text to analyze:
    {text_content}
    """

    # Make API call
    message = anthropic.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=4000,
        temperature=0.2,
        system="You are an expert in linguistics and semantic analysis.",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    # Parse the response
    try:
        relationships = json.loads(message.content[0].text)
        return relationships
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON response"}


# Function to process multiple documents
def batch_process_documents(documents):
    results = []
    for doc in documents:
        result = analyze_text(doc)
        results.append({
            "document_id": doc.get("id"),
            "relationships": result
        })
    return results


# Function to save results
def save_results(results, filename):
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)


# Example usage:
if __name__ == "__main__":
    # Example document
    document = {
        "id": "1",
        "content": """[Your document content here]"""
    }

    # Single document analysis
    result = analyze_text(document["content"])
    save_results(result, "analysis_results.json")

    # Or batch processing
    documents = [document1, document2, ...]  # Your list of documents
    batch_results = batch_process_documents(documents)
    save_results(batch_results, "batch_results.json")