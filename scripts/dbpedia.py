from SPARQLWrapper import SPARQLWrapper, JSON
import json
import re
import ssl
from difflib import SequenceMatcher
from tqdm import tqdm

class RelationValidator:
    def __init__(self):
        # Configure SSL
        ssl._create_default_https_context = ssl._create_unverified_context

        # Configure SPARQL
        self.sparql = SPARQLWrapper("http://dbpedia.org/sparql")
        self.sparql.setReturnFormat(JSON)

        # Configuration
        self.EVIDENCE_SIMILARITY_THRESHOLD = 0.85
        self.CONCEPT_SIMILARITY_THRESHOLD = 0.8

        self.clean_text_cache = {}

    def extract_article_text(self, article_data: dict) -> str:
        text = []
        for section in article_data["sections"]:
            text.extend(section["content"])
            for subsection in section.get("subsections", []):
                text.extend(subsection.get("content", []))
        return " ".join(text)

    def normalize_text(self, text: str) -> str:
        """Normalize text by handling quotes and special characters."""
        # Replace various quote types with simple quotes
        text = text.replace('"', '"').replace('"', '"').replace('\"', '"')
        return text.lower().strip()

    def split_into_sentences(self, text: str) -> list:
        """Split text into sentences, handling special cases."""
        # Split on sentence endings while preserving abbreviations
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', text)
        # Also split on semicolons
        result = []
        for sentence in sentences:
            parts = sentence.split(';')
            result.extend([p.strip() for p in parts if p.strip()])
        return result

    def find_concept_in_text(self, concept: str, text: str) -> tuple:
        """Find concept in text using fuzzy matching."""
        concept = concept.lower()
        text = text.lower()

        # Check exact match first
        if concept in text:
            return True, concept

        # Try fuzzy matching with sliding window
        words = text.split()
        concept_words = concept.split()
        window_size = len(concept_words)

        for i in range(len(words) - window_size + 1):
            window = ' '.join(words[i:i + window_size])
            if SequenceMatcher(None, concept, window).ratio() > self.CONCEPT_SIMILARITY_THRESHOLD:
                return True, window

        return False, ""

    def clean_text(self, text: str) -> str:
        """Clean text for comparison by removing quotes, parentheses and their content."""
        if text in self.clean_text_cache:
            return self.clean_text_cache[text]

        # Remove content within parentheses
        text = re.sub(r'\([^)]*\)', '', text)
        # Replace all types of quotes
        text = text.replace('"', ' ').replace('"', ' ').replace('"', ' ')
        text = text.replace("'", ' ').replace(''', ' ').replace(''', ' ')
        # Handle ellipsis
        text = text.replace('...', ' ').replace('…', ' ')
        # Normalize spaces and lowercase
        text = ' '.join(text.split())
        return text.strip().lower()

    def check_evidence_presence(self, evidence: str, sentences: list) -> tuple:
        """Check if evidence is present in any sentence."""
        clean_evidence = self.clean_text_for_comparison(evidence)

        for sentence in sentences:
            clean_sentence = self.clean_text_for_comparison(sentence)
            similarity = SequenceMatcher(None, clean_evidence, clean_sentence).ratio()
            if similarity > self.EVIDENCE_SIMILARITY_THRESHOLD:
                return True, similarity

            # If the evidence is completely contained in the sentence (after cleaning)
            if clean_evidence in clean_sentence:
                return True, 1.0
        return False, 0

    def validate_text_evidence(self, article_text: str, relation: dict) -> dict:
        """Validate a relation against article text."""
        # Clean inputs
        evidence = self.clean_text(relation["evidence"])
        text = self.clean_text(article_text)
        source = relation["source"]
        target = relation["target"]

        # Check evidence in sentences
        sentences = self.split_into_sentences(text)
        evidence_present = any(
            SequenceMatcher(None, evidence, self.clean_text(s)).ratio() > self.EVIDENCE_SIMILARITY_THRESHOLD
            or evidence in self.clean_text(s)
            for s in sentences
        )

        # Check source and target in evidence first
        source_in_evidence, source_match = self.find_concept_in_text(source, evidence)
        target_in_evidence, target_match = self.find_concept_in_text(target, evidence)

        # If not found in evidence, check in full text
        if not (source_in_evidence and target_in_evidence):
            source_in_text, source_match = self.find_concept_in_text(source, text)
            target_in_text, target_match = self.find_concept_in_text(target, text)
            source_found = source_in_evidence or source_in_text
            target_found = target_in_evidence or target_in_text
            proximity_score = 0.5 if (source_found and target_found) else 0.0
        else:
            source_found = source_in_evidence
            target_found = target_in_evidence
            proximity_score = 1.0

        return {
            "source_present": source_found,
            "source_match": source_match,
            "target_present": target_found,
            "target_match": target_match,
            "evidence_present": evidence_present,
            "proximity_score": proximity_score
        }

def calculate_statistics(validations: list) -> dict:
    """Calculate validation statistics."""
    total = len(validations)
    stats = {
        "total_relations": total,
        "proximity_scores": {"score_1": 0, "score_0.5": 0, "score_0": 0},
        "evidence_present": {"true": 0, "false": 0},
        "source_present": {"true": 0, "false": 0},
        "target_present": {"true": 0, "false": 0},
        "coverage": {"percentage": 0.0, "found": 0, "total": total}
    }

    for val in validations:
        v = val["validation"]
        # Count scores
        if v["proximity_score"] == 1.0:
            stats["proximity_scores"]["score_1"] += 1
        elif v["proximity_score"] == 0.5:
            stats["proximity_scores"]["score_0.5"] += 1
        else:
            stats["proximity_scores"]["score_0"] += 1

        # Count presence
        stats["evidence_present"]["true" if v["evidence_present"] else "false"] += 1
        stats["source_present"]["true" if v["source_present"] else "false"] += 1
        stats["target_present"]["true" if v["target_present"] else "false"] += 1

        # Update coverage
        if v["evidence_present"]:
            stats["coverage"]["found"] += 1

    if total > 0:
        stats["coverage"]["percentage"] = round((stats["coverage"]["found"] / total) * 100, 2)

    return stats

def main():
    # Load your data
    with open('/Users/mollyhan/PycharmProjects/Cognitext/data/relations/master_relations_section.json', 'r') as f:
        relations_data = json.load(f)
    with open('/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json', 'r') as f:
        articles_data = json.load(f)

    # Initialize validator
    # Process articles
    validator = RelationValidator()
    results = []
    total_articles = len([a for a in relations_data["articles"].items()
                          if a[0] in articles_data["articles"]])

    print("\nProcessing articles...")
    for article_title, article_data in tqdm(relations_data["articles"].items(),
                                            total=total_articles):
        if article_title not in articles_data["articles"]:
            continue

        article_text = validator.extract_article_text(articles_data["articles"][article_title])
        validations = []

        for relation in article_data["relations"]:
            validation = validator.validate_text_evidence(article_text, relation)
            validations.append({"relation": relation, "validation": validation})

        results.append({
            "article": article_title,
            "category": article_data["category"],
            "relations_validation": validations,
            "statistics": calculate_statistics(validations)
        })

    print("\nSaving results...")
    # Save results
    with open('/Users/mollyhan/PycharmProjects/Cognitext/data/relations/dbpedia_comparison_results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Done!")

if __name__ == "__main__":
    main()