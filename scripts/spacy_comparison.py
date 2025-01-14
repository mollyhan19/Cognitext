import spacy
import json
from typing import Dict, List
from fuzzywuzzy import fuzz

class SpacyExtractor:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.entities = {}

    
    def process_text(self, article_data: Dict) -> List[Dict]:
        """Process text and extract entities"""
            
        all_text = []

        for section in article_data["sections"]:
            # Add section title for context
            section_title = section.get("section_title", "")
            if section_title:
                all_text.append(section_title)
            
            # Add main content
            content = section.get("content", [])
            if isinstance(content, list):
                all_text.extend(content)
            
            # Add subsection content if any
            subsections = section.get("subsections", [])
            for subsection in subsections:
                if isinstance(subsection.get("content"), list):
                    all_text.extend(subsection["content"])

        full_text = " ".join(all_text)
        
        # Process with SpaCy
        doc = self.nlp(full_text)
            
        # Aggregate all entities
        entities = {}

        # Add named entities
        for ent in doc.ents:
            if ent.text not in entities:
                entities[ent.text] = {
                    "entity": ent.text,
                    "type": ent.label_,
                    "appearances": [{
                        "context": ent.sent.text
                    }],
                    "variants": {ent.text.lower()}
                }
            else:
                entities[ent.text]["variants"].add(ent.text.lower())
                entities[ent.text]["appearances"].append({
                    "context": ent.sent.text
                })
            
        # Add noun phrases
        for chunk in doc.noun_chunks:
            if chunk.text not in entities:
                entities[chunk.text] = {
                    "entity": chunk.text,
                    "type": "NOUN_PHRASE",
                    "appearances": [{
                        "context": chunk.sent.text
                    }],
                    "variants": {chunk.text.lower()}
                }
            else:
                entities[chunk.text]["appearances"].append({
                    "context": chunk.sent.text
                })
                
        # Add compound nouns
        for token in doc:
            if token.dep_ == "compound":
                compound = f"{token.text} {token.head.text}"
                if compound not in entities:
                    entities[compound] = {
                        "entity": compound,
                        "type": "COMPOUND_NOUN",
                        "appearances": [{
                            "context": token.sent.text
                        }],
                        "variants": {compound.lower()}
                    }
                else:
                    entities[compound]["appearances"].append({
                        "context": token.sent.text
                    })
        
        return list(entities.values())


    def process_spacy(self, section_content: Dict, section_name: str, section_num: int) -> List[Dict]:
        """Process entire section similar to your extract_entities_from_section"""
        # Combine all text in section including subheadings
        section_text = []

        # Check if section_content is a dictionary
        if isinstance(section_content, dict):
            # Add main text
            if "text" in section_content:
                # Ensure that we are extending with strings
                if isinstance(section_content["text"], list):
                    section_text.extend([str(text) for text in section_content["text"] if isinstance(text, str)])
            
            # Add subheading text
            if "subheadings" in section_content:
                for subheading, subcontent in section_content["subheadings"].items():
                    if "text" in subcontent:
                        if isinstance(subcontent["text"], list):
                            section_text.extend([str(text) for text in subcontent["text"] if isinstance(text, str)])
        elif isinstance(section_content, list):
            # If it's a list, ensure all items are strings
            section_text.extend([str(text) for text in section_content if isinstance(text, str)])
        elif isinstance(section_content, str):
            # If it's a string, append it directly
            section_text.append(section_content)
        else:
            print(f"Unexpected section_content type: {type(section_content)}")

        full_section_text = "\n".join(section_text)

        # Process with SpaCy
        doc = self.nlp(full_section_text)
            
        # Aggregate entities across the section
        section_entities = {}

        # Add named entities
        for ent in doc.ents:
            if ent.text not in section_entities:
                section_entities[ent.text] = {
                    "entity": ent.text,
                    "type": ent.label_,
                    "appearances": [{
                        "section": section_name,
                        "section_num": section_num
                    }],
                    "variants": {ent.text.lower()}
                }
            else:
                section_entities[ent.text]["variants"].add(ent.text.lower())
            
        # Add noun phrases
        for chunk in doc.noun_chunks:
            if chunk.text not in section_entities:
                section_entities[chunk.text] = {
                    "entity": chunk.text,  # Using string directly
                    "type": "NOUN_PHRASE",
                    "appearances": [{
                        "section": section_name,
                        "section_num": section_num
                    }],
                    "variants": {chunk.text.lower()}
                }
                
        # Add compound nouns
        for token in doc:
            if token.dep_ == "compound":
                compound = f"{token.text} {token.head.text}"  # Create compound string
                if compound not in section_entities:
                    section_entities[compound] = {
                        "entity": compound,
                        "type": "COMPOUND_NOUN",
                        "appearances": [{
                            "section": section_name,
                            "section_num": section_num
                        }],
                        "variants": {compound.lower()}
                    }
        
        return list(section_entities.values())

'''
def process_spacy_paragraph(self, paragraph: str, para_num: int) -> List[Dict]:
        """Process single paragraph similar to your extract_entities_from_paragraph"""
        doc = self.nlp(paragraph)
        
        # Collect both named entities and noun phrases
        paragraph_entities = {}
        
        # Process named entities
        for ent in doc.ents:
            if ent.text not in paragraph_entities:
                paragraph_entities[ent.text] = {
                    "entity": ent.text,
                    "type": ent.label_,
                    "appearances": [{
                        "paragraph": para_num,
                        "form": ent.text
                    }],
                    "variants": {ent.text.lower()}
                }
            else:
                paragraph_entities[ent.text]["variants"].add(ent.text.lower())
                
        # Process noun phrases
        for chunk in doc.noun_chunks:
            if chunk.text not in paragraph_entities:
                paragraph_entities[chunk.text] = {
                    "entity": chunk.text,
                    "type": "NOUN_PHRASE",
                    "appearances": [{
                        "paragraph": para_num,
                        "form": chunk.text
                    }],
                    "variants": {chunk.text.lower()}  # Correctly create a set
                }
        
        # Add compound nouns
        for token in doc:
            if token.dep_ == "compound":
                compound = f"{token.text} {token.head.text}"  # Create compound string
                if compound not in paragraph_entities:
                    paragraph_entities[compound] = {
                        "entity": compound,
                        "type": "COMPOUND_NOUN",
                        "appearances": [{
                            "section": para_num,
                            "form": compound
                        }],
                        "variants": {compound.lower()}
                    }
                
        return list(paragraph_entities.values())
'''
    
def process_articles(json_path: str):
        """Process articles extracting entities"""
        extractor = SpacyExtractor()
        
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        results = {}
        
        for article_title, article_data in data["articles"].items():
            print(f"\nProcessing article: {article_title}")
            
            # Process full article
            article_entities = extractor.process_text(article_data)
            
            results[article_title] = {
                "category": article_data["category"],
                "total_entities": len(article_entities),
                "entities": article_entities
            }
            
        return results

def process_articles_sec(json_path: str, mode: str = 'section'):
    """Process articles in either paragraph or section mode"""
    extractor = SpacyExtractor()
    
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    results = {}
    
    
    for article_title, article_data in data["articles"].items():
        print(f"\nProcessing article: {article_title}")
        
        article_entities = []
        

        for section_idx, section in enumerate(article_data["sections"]):
            for heading, content in section.items():
                print(f"Processing section: {heading}")
                section_entities = extractor.process_spacy(
                    content, heading, section_idx
                )
                article_entities.extend(section_entities)
        
        results[article_title] = {
            "category": article_data["category"],
            "total_entities": len(article_entities),
            "entities": article_entities
        }
        
    return results

    '''
        else:
            # Process by paragraph
            processed_paragraphs = 0
            for section in article_data["sections"]:
                for heading, content in section.items():
                    # Debugging output to check the structure of content
                    print(f"Content for heading '{heading}': {content}")
                    
                    # Check if content is a list and process accordingly
                    if isinstance(content, list):
                        if content:  # If content is not empty
                            for paragraph in content:
                                if isinstance(paragraph, str) and paragraph.strip():  # Ensure paragraph is a string
                                    processed_paragraphs += 1
                                    para_entities = extractor.process_spacy_paragraph(
                                        paragraph, processed_paragraphs
                                    )
                                    article_entities.extend(para_entities)
                        else:
                            print(f"Content for heading '{heading}' is an empty list.")
                    elif isinstance(content, dict):
                        # Handle the case where content is a dictionary (e.g., for subsections)
                        if "content" in content and isinstance(content["content"], list):
                            for paragraph in content["content"]:
                                if isinstance(paragraph, str) and paragraph.strip():
                                    processed_paragraphs += 1
                                    para_entities = extractor.process_spacy_paragraph(
                                        paragraph, processed_paragraphs
                                    )
                                    article_entities.extend(para_entities)
                        else:
                            print(f"Unexpected content structure for heading '{heading}': {content}")
                    else:
                        print(f"Unexpected content structure for heading '{heading}': {content}")
        '''

def compare_entities(spacy_entity: str, gpt_entity: str) -> float:
    """Compare entities with fuzzy matching"""
    # Direct match
    if spacy_entity.lower() == gpt_entity.lower():
        return 1.0
        
    # Partial match
    ratio = fuzz.partial_ratio(spacy_entity.lower(), gpt_entity.lower())
    if ratio > 80:  # Threshold for considering match
        return ratio / 100
        
    return 0.0

def calculate_mode_comparison_metrics(spacy_results: Dict, gpt_results_path: str, mode: str):
    """Calculate comparison metrics for a specific processing mode"""
    
    with open(gpt_results_path, 'r') as f:
        gpt_results = json.load(f)

    if "metadata" in gpt_results:
        gpt_results.pop("metadata")

    metrics = {
        "overall": {
            "total_articles": 0,
            "spacy_total_entities": 0,
            "gpt_total_entities": 0,
            "overlap_total": 0
        },
        "articles": {}
    }

    # Process each article
    for article_title, spacy_article in spacy_results.items():
        
        # Handle potential title variations (singular/plural)
        if article_title not in gpt_results:
            singular_title = article_title.rstrip('s')
            plural_title = article_title + 's'
            
            if singular_title in gpt_results:
                article_title = singular_title
            elif plural_title in gpt_results:
                article_title = plural_title
            else:
                print(f"Article '{article_title}' not found in GPT results.")
                continue
            
        gpt_article = gpt_results[article_title]
        
        # Get entity sets (convert to lowercase for comparison)
        spacy_entities = {e["entity"].lower(): e for e in spacy_article["entities"]}
        gpt_entities = {e["id"].lower(): e for e in gpt_article["entities"]}


        # Calculate entity types distribution
        spacy_types = {}
        for entity in spacy_article["entities"]:
            entity_type = entity.get("type", "UNKNOWN")
            spacy_types[entity_type] = spacy_types.get(entity_type, 0) + 1
        
        # Track best matches
        gpt_best_matches = {}  # Store best match score for each GPT entity
        spacy_best_matches = {}  # Store best match score for each SpaCy entity
        
        # Find best matches
        for spacy_entity in spacy_entities:
            for gpt_entity in gpt_entities:
                match_score = compare_entities(spacy_entity, gpt_entity)
                if match_score > 0:
                    # Update best match for GPT entity
                    if gpt_entity not in gpt_best_matches or match_score > gpt_best_matches[gpt_entity][1]:
                        gpt_best_matches[gpt_entity] = (spacy_entity, match_score)
                    # Update best match for SpaCy entity
                    if spacy_entity not in spacy_best_matches or match_score > spacy_best_matches[spacy_entity][1]:
                        spacy_best_matches[spacy_entity] = (gpt_entity, match_score)
        
        # Calculate weighted overlap scores
        total_match_score = sum(score for _, score in gpt_best_matches.values())
        
        # Calculate metrics
        precision = total_match_score / len(gpt_entities) if gpt_entities else 0
        recall = total_match_score / len(spacy_entities) if spacy_entities else 0
        f1 = 2 * (precision * recall) / (precision + recall) if precision + recall > 0 else 0
        
        
        # Store detailed match information for analysis
        matched_pairs = [
            {
                "spacy_entity": spacy_entity,
                "gpt_entity": gpt_entity,
                "score": round(score, 3)
            }
            for gpt_entity, (spacy_entity, score) in list(gpt_best_matches.items())[:5]
        ]
        
        metrics["articles"][article_title] = {
            "entity_counts": {
                "spacy": len(spacy_entities),
                "gpt": len(gpt_entities),
                "matched": len(gpt_best_matches)
            },
            "precision": min(1.0, precision),  # Cap at 1.0
            "recall": min(1.0, recall),  # Cap at 1.0
            "f1": min(1.0, f1),  # Cap at 1.0
            "entity_types": {
                etype: count 
                for etype, count in spacy_types.items()
            },
            "matched_examples": matched_pairs
        }
        
        # Update overall metrics
        metrics["overall"]["total_articles"] += 1
        metrics["overall"]["spacy_total_entities"] += len(spacy_entities)
        metrics["overall"]["gpt_total_entities"] += len(gpt_entities)
        metrics["overall"]["overlap_total"] += len(gpt_best_matches)

    # Calculate aggregate metrics
    if metrics["overall"]["total_articles"] > 0:
        metrics["overall"].update({
            "average_precision": sum(
                m["precision"] for m in metrics["articles"].values()
            ) / metrics["overall"]["total_articles"],
            "average_recall": sum(
                m["recall"] for m in metrics["articles"].values()
            ) / metrics["overall"]["total_articles"],
            "average_f1": sum(
                m["f1"] for m in metrics["articles"].values()
            ) / metrics["overall"]["total_articles"]
        })

    return metrics

def print_comparison_summary(metrics: Dict):
    print("\n=== Detailed Analysis ===")

    if "articles" not in metrics:
        print("No articles found in metrics.")
        return
    
    for article_title, article_metrics in metrics["articles"].items():
        print(f"\n{article_title}:")
        print(f"Entities found - SpaCy: {article_metrics['entity_counts']['spacy']}, "
              f"GPT: {article_metrics['entity_counts']['gpt']}")
        print(f"Matched entities: {article_metrics['entity_counts']['matched']}")
        print(f"Precision: {article_metrics['precision']:.3f}")
        print(f"Recall: {article_metrics['recall']:.3f}")
        print(f"F1: {article_metrics['f1']:.3f}")
        
        print("\nTop matches examples:")
        for match in article_metrics['matched_examples'][:5]:
            print(f"SpaCy: {match['spacy_entity']}")
            print(f"GPT: {match['gpt_entity']}")
            print(f"Match score: {match['score']}")
            print("---")

    print("\n=== Overall Statistics ===")
    print(f"Average Precision: {metrics['overall']['average_precision']:.3f}")
    print(f"Average Recall: {metrics['overall']['average_recall']:.3f}")
    print(f"Average F1: {metrics['overall']['average_f1']:.3f}")

def convert_sets_to_lists(data):
    """Recursively convert sets to lists in a dictionary or list."""
    if isinstance(data, dict):
        return {key: convert_sets_to_lists(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_sets_to_lists(item) for item in data]
    elif isinstance(data, set):
        return list(data)  # Convert set to list
    else:
        return data  # Return the data as is
    
def main():
    text_input = "/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json"
    gpt_results_section = "/Users/mollyhan/PycharmProjects/Cognitext/data/entity_analysis_section_results.json"
    # gpt_results_paragraph = "/Users/mollyhan/PycharmProjects/Cognitext/data/entity_analysis_paragraph_results.json"
    
    # Process in both modes
    spacy_results = process_articles(text_input)

    # Calculate comparisons for each mode
    # paragraph_comparison = calculate_mode_comparison_metrics(
        # spacy_results, 
        # gpt_results_paragraph,
        # 'paragraph'
    # )
    
    section_comparison = calculate_mode_comparison_metrics(
        spacy_results, 
        gpt_results_section,
        'section'
    )
    
    output = {
        # "paragraph_mode": {
            # "spacy_results": spacy_results,
            # "comparison_metrics": paragraph_comparison
        # },
        "section_mode": {
            "spacy_results": spacy_results,
            "comparison_metrics": section_comparison
        }
    }

    output = convert_sets_to_lists(output)

    with open("/Users/mollyhan/PycharmProjects/Cognitext/data/spacy_section_comparison.json", "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    # print("\n=== Paragraph Mode Comparison ===")
    # print(f"Average Precision: {paragraph_comparison['overall']['average_precision']:.3f}")
    # print(f"Average Recall: {paragraph_comparison['overall']['average_recall']:.3f}")
    # print(f"Average F1: {paragraph_comparison['overall']['average_f1']:.3f}")
    
    # print_comparison_summary(section_comparison)
    # print("\n=== Section Mode Comparison ===")
    # print(f"Average Precision: {section_comparison['overall']['average_precision']:.3f}")
    # print(f"Average Recall: {section_comparison['overall']['average_recall']:.3f}")
    # print(f"Average F1: {section_comparison['overall']['average_f1']:.3f}")

if __name__ == "__main__":
    main()