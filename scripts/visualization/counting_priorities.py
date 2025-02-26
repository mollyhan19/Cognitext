import json
from typing import Dict, List, Union
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConceptPriority:
    concept: str
    title: str  # Document title
    category: str  # Document category
    out_degree: int
    in_degree: int
    total_degree: int
    normalized_score: float

class PriorityCalculator:
    def __init__(self, relations_file: str):
        self.relations_file = relations_file
        self.priorities: Dict[str, ConceptPriority] = {}
        self.max_total_degree = 0

    def load_relations(self) -> tuple[List[Dict], str, str]:
        """Load relations and metadata from JSON file."""
        with open(self.relations_file, 'r') as f:
            data = json.load(f)
            title = next(iter(data.keys()))  # Get the document title
            category = data[title]["category"]
            relations = data[title]["relations"]
            return relations, title, category

    def calculate_priorities(self) -> Dict[str, ConceptPriority]:
        """Calculate priorities for all concepts based on their relationships."""
        relations, doc_title, category = self.load_relations()
        concept_counts: Dict[str, Dict[str, int]] = {}

        # Initialize counts
        for relation in relations:
            source = relation["source"].lower()  # Normalize to lowercase
            target = relation["target"].lower()

            # Initialize if not exists
            if source not in concept_counts:
                concept_counts[source] = {"out_degree": 0, "in_degree": 0}
            if target not in concept_counts:
                concept_counts[target] = {"out_degree": 0, "in_degree": 0}

            # Increment counts
            concept_counts[source]["out_degree"] += 1
            concept_counts[target]["in_degree"] += 1

        # Calculate total degrees and find maximum
        self.max_total_degree = 0
        for concept, counts in concept_counts.items():
            total_degree = counts["out_degree"] + counts["in_degree"]
            self.max_total_degree = max(self.max_total_degree, total_degree)

        # Create ConceptPriority objects with normalized scores
        for concept, counts in concept_counts.items():
            total_degree = counts["out_degree"] + counts["in_degree"]
            normalized_score = total_degree / self.max_total_degree if self.max_total_degree > 0 else 0

            self.priorities[concept] = ConceptPriority(
                concept=concept,
                title=doc_title,
                category=category,
                out_degree=counts["out_degree"],
                in_degree=counts["in_degree"],
                total_degree=total_degree,
                normalized_score=normalized_score
            )

        return self.priorities

    def get_sorted_priorities(self, sort_by: str = 'total') -> List[ConceptPriority]:
        """Get sorted list of priorities."""
        if not self.priorities:
            self.calculate_priorities()

        priorities_list = list(self.priorities.values())

        if sort_by == 'total':
            return sorted(priorities_list, key=lambda x: x.total_degree, reverse=True)
        elif sort_by == 'out':
            return sorted(priorities_list, key=lambda x: x.out_degree, reverse=True)
        elif sort_by == 'in':
            return sorted(priorities_list, key=lambda x: x.in_degree, reverse=True)
        else:
            raise ValueError("sort_by must be one of: 'total', 'out', 'in'")

    def save_priorities(self, output_file: str):
        """Save calculated priorities to JSON file."""
        if not self.priorities:
            self.calculate_priorities()

        # Get document metadata from first priority (they're all the same)
        first_priority = next(iter(self.priorities.values()))

        output_data = {
            "document_metadata": {
                "title": first_priority.title,
                "category": first_priority.category
            },
            "max_total_degree": self.max_total_degree,
            "concepts": {
                concept: {
                    "out_degree": priority.out_degree,
                    "in_degree": priority.in_degree,
                    "total_degree": priority.total_degree,
                    "normalized_score": priority.normalized_score
                }
                for concept, priority in self.priorities.items()
            }
        }

        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

    def get_hierarchy_levels(self, num_levels: int = 5) -> Dict[str, int]:
        """Assign hierarchy levels to concepts based on their total degree."""
        if not self.priorities:
            self.calculate_priorities()

        levels = {}
        sorted_priorities = self.get_sorted_priorities('total')

        # Calculate thresholds for each level
        thresholds = [
            self.max_total_degree * (1 - i / num_levels)
            for i in range(num_levels)
        ]

        # Assign levels based on thresholds
        for priority in sorted_priorities:
            for level, threshold in enumerate(thresholds):
                if priority.total_degree >= threshold:
                    levels[priority.concept] = level
                    break
            else:
                levels[priority.concept] = num_levels - 1

        return levels


def main():
    # Example usage
    calculator = PriorityCalculator("/concept-visualization/public/data/simp_relation_section_results.json")

    # Calculate priorities
    priorities = calculator.calculate_priorities()

    # Get sorted results
    total_sorted = calculator.get_sorted_priorities('total')
    print("\nDocument Analysis:")
    print(f"Title: {total_sorted[0].title}")
    print(f"Category: {total_sorted[0].category}")

    print("\nTop 10 concepts by total connections:")
    for p in total_sorted[:10]:
        print(f"{p.concept}: Total={p.total_degree} (Out={p.out_degree}, In={p.in_degree})")

    # Save results
    calculator.save_priorities("/Users/mollyhan/PycharmProjects/Cognitext/data/simp_concept_priorities.json")

    # Get hierarchy levels
    levels = calculator.get_hierarchy_levels()
    print("\nHierarchy levels for top concepts:")
    for p in total_sorted[:10]:
        print(f"{p.concept}: Level {levels[p.concept]}")


if __name__ == "__main__":
    main()