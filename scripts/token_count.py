import json
from tiktoken import encoding_for_model
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from cache_manager import CacheManager

@dataclass
class TokenCounts:
    """Store token counts for input and output."""
    input_tokens: int
    estimated_output_tokens: int

class TokenCounter:
    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self.enc = encoding_for_model(model)
        self.cache_manager = CacheManager()  # To access cached API responses

    def count_tokens(self, text: str) -> int:
        """Count tokens for specific text."""
        return len(self.enc.encode(text))

    def get_extraction_prompt(self, paragraph: str) -> str:
        """Get the entity extraction prompt."""
        return f"""Extract key concepts that are crucial for understanding the main ideas in this paragraph. Each concept should represent a distinct unit of knowledge or understanding.
        Focus on: 
        1. Foundational concepts that other ideas build upon
        2. Core processes or mechanisms that explain how something works
        3. Key principles or theories that frame the topic
        4. Critical relationships between ideas
        5. Defining characteristics or properties that distinguish important elements
        
        Important guidelines: 
        - Properties/attributes of a concept should be separate concepts if they represent important distinct ideas. (e.g., "tardigrade nervous system" is different from "tardigrade") 
        - Different states/processes should be separate concepts when they represent distinct phenomena (e.g., "active tardigrades" vs "dormant tardigrades") 

        Output format:
        [
            {{
            "entity": "main_form",
            "variants": ["true conceptual variations only"],
            "context": "Why this concept is essential for understanding the topic",
            }}
        ]
        Paragraph:{paragraph}"""

    def get_linking_prompt(self, list1: List, list2: List) -> str:
        """Get the entity linking prompt."""
        return f"""Compare these two lists of concepts and identify which ones represent EXACTLY the same abstract idea or unit of knowledge.
        Guidelines for matching:
        1. The concepts should teach the same core idea
        2. Understanding one should be equivalent to understanding the other
        3. They should operate at the same level of abstraction
        4. They should play the same role in building subject knowledge
        5. They should have the same relationship to other key concepts

        Do NOT match concepts that:
        - Are merely related or connected
        - Have a hierarchical relationship
        - Represent different aspects of the same topic
        - Operate at different levels of detail
        
        When in doubt about conceptual equivalence, DO NOT match
        Return a JSON dictionary where keys are concepts from List 2 and values are their matching entities from List 1. 
        Only include pairs that represent the exact same abstract idea or unit of knowledge.

        List 1:
        {json.dumps(list1, indent=2)}

        List 2:
        {json.dumps(list2, indent=2)}
        """

    def estimate_article_costs(self, article: Dict) -> Dict:
        extraction_counts = TokenCounts(0, 0)
        linking_counts = TokenCounts(0, 0)
        total_paragraphs = 0

        # Process each section
        for section in article["sections"]:
            for heading, content in section.items():
                # Process main text paragraphs
                for para in content["text"]:
                    if not para.strip():
                        continue

                    total_paragraphs += 1

                    # Count input tokens for this paragraph
                    extraction_prompt = self.get_extraction_prompt(para)
                    input_tokens = self.count_tokens(extraction_prompt)
                    extraction_counts.input_tokens += input_tokens

                    # Get actual API output from cache if available
                    cached_result = self.cache_manager.get_cached_entities(para)
                    if cached_result:
                        output_tokens = self.count_tokens(json.dumps(cached_result))
                        extraction_counts.estimated_output_tokens += output_tokens

                # Process subheadings
                for subheading, subcontent in content.get("subheadings", {}).items():
                    for para in subcontent.get("text", []):
                        if not para.strip():
                            continue

                        total_paragraphs += 1
                        extraction_prompt = self.get_extraction_prompt(para)
                        input_tokens = self.count_tokens(extraction_prompt)
                        extraction_counts.input_tokens += input_tokens

                        # Get actual API output from cache
                        cached_result = self.cache_manager.get_cached_entities(para)
                        if cached_result:
                            output_tokens = self.count_tokens(json.dumps(cached_result))
                            extraction_counts.estimated_output_tokens += output_tokens

        # For entity linking, we'll count actual cached comparison results
        # Get some cached comparisons for token counts
        if total_paragraphs > 1:
            estimated_linking_calls = total_paragraphs - 1

            # Try to get an average token count from actual cached comparisons
            cached_comparisons = []  # You might need to modify cache_manager to get these
            if cached_comparisons:
                avg_input_tokens = sum(self.count_tokens(comp['input']) for comp in cached_comparisons) / len(
                    cached_comparisons)
                avg_output_tokens = sum(self.count_tokens(comp['output']) for comp in cached_comparisons) / len(
                    cached_comparisons)

                linking_counts.input_tokens = int(avg_input_tokens * estimated_linking_calls)
                linking_counts.estimated_output_tokens = int(avg_output_tokens * estimated_linking_calls)
            else:
                # If no cache available, use direct prompt counting
                list1 = [{"entity": "placeholder", "variants": []}]
                list2 = [{"entity": "placeholder", "variants": []}]
                linking_prompt = self.get_linking_prompt(list1, list2)
                tokens_per_call = self.count_tokens(linking_prompt)
                linking_counts.input_tokens = tokens_per_call * estimated_linking_calls
                # Assume minimal output if no cache available
                linking_counts.estimated_output_tokens = self.count_tokens(
                    '{"placeholder": null}') * estimated_linking_calls

        # Calculate total costs
        total_input_tokens = extraction_counts.input_tokens + linking_counts.input_tokens
        total_output_tokens = extraction_counts.estimated_output_tokens + linking_counts.estimated_output_tokens

        input_cost = (total_input_tokens / 1000) * 0.03  # $0.03 per 1K tokens
        output_cost = (total_output_tokens / 1000) * 0.06  # $0.06 per 1K tokens
        total_cost = input_cost + output_cost

        return {
            "total_paragraphs": total_paragraphs,
            "entity_extraction": {
                "input_tokens": extraction_counts.input_tokens,
                "estimated_output_tokens": extraction_counts.estimated_output_tokens,
                "cost": (extraction_counts.input_tokens / 1000 * 0.03) +
                        (extraction_counts.estimated_output_tokens / 1000 * 0.06)
            },
            "entity_linking": {
                "estimated_operations": total_paragraphs - 1 if total_paragraphs > 1 else 0,
                "input_tokens": linking_counts.input_tokens,
                "estimated_output_tokens": linking_counts.estimated_output_tokens,
                "cost": (linking_counts.input_tokens / 1000 * 0.03) +
                        (linking_counts.estimated_output_tokens / 1000 * 0.06)
            },
            "total": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "input_cost": input_cost,
                "output_cost": output_cost,
                "total_cost": total_cost
            }
        }


def main():
    # Load sample article
    with open("/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json", "r") as f:
        data = json.load(f)

    counter = TokenCounter()
    article = data["articles"]["Tardigrade"]  # or loop through all articles
    costs = counter.estimate_article_costs(article)

    # Print results
    print("\nCost Estimation Results:")
    print("-" * 50)
    print(json.dumps(costs, indent=2))


if __name__ == "__main__":
    main()