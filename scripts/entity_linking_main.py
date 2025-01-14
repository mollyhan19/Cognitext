from dotenv import load_dotenv
import os
import json
from datetime import datetime
from entity_extraction import OptimizedEntityExtractor, TextChunk
from typing import Dict, List

def process_article_by_paragraphs(title: str, article: Dict, extractor: OptimizedEntityExtractor):
    """Process article paragraph by paragraph."""
    print(f"Processing article by paragraphs: {title}")
    
    sections = article.get('sections', [])
    processed_paragraphs = 0
    total_paragraphs = 0 

    sections_to_skip = {"See also", "Notes", "References", "Works cited", "External links"}

    for section in sections:
        section_title = section.get('section_title', '')
        if section_title in sections_to_skip: 
            continue
        
        # Count main content paragraphs
        main_content = section.get('content', [])
        total_paragraphs += len(main_content)
        
        # Count subsection paragraphs
        for subsection in section.get('subsections', []):
            subsection_content = subsection.get('content', [])
            total_paragraphs += len(subsection_content)
    
    print(f"Total paragraphs to process: {total_paragraphs}")
    
    # Reset entity tracking for new article
    extractor.reset_tracking()

    for section_idx, section in enumerate(sections, 1):
        try:
            section_title = section.get('section_title', '')

            if section_title in sections_to_skip: 
                continue
            
            # Process main content paragraphs
            main_content = section.get('content', [])
            for para_idx, paragraph in enumerate(main_content, 1):
                processed_paragraphs += 1
                print(f"\nProcessing paragraph {processed_paragraphs}/{total_paragraphs}: {section_title}")
                
                chunk = TextChunk(
                    content=paragraph,
                    section_name=section_title,
                    heading_level="main",
                    section_text=[paragraph],
                    section_index=section_idx,
                    paragraph_index=para_idx
                )
                extractor.process_paragraph(chunk)
            
            # Process subsection paragraphs
            for subsection in section.get('subsections', []):
                subsection_title = subsection.get('title', '')
                subsection_content = subsection.get('content', [])
                
                for para_idx, paragraph in enumerate(subsection_content, 1):
                    processed_paragraphs += 1
                    print(f"\nProcessing paragraph {processed_paragraphs}/{total_paragraphs}: {section_title} - {subsection_title}")
                    
                    chunk = TextChunk(
                        content=paragraph,
                        section_name=f"{section_title} - {subsection_title}",
                        heading_level="sub",
                        section_text=[paragraph],
                        section_index=section_idx,
                        paragraph_index=para_idx
                    )
                    extractor.process_paragraph(chunk)
                
            print(f"Current unique entities after paragraph {processed_paragraphs}: "
            f"{len(extractor.get_sorted_entities())}")
                    
        except Exception as e:
            print(f"Error processing paragraph {processed_paragraphs}: {str(e)}")
            continue
    
    return extractor.get_sorted_entities()

def process_article_by_sections(title, article, extractor):
    print(f"Processing article by sections: {title}")
    
    sections = article.get('sections', [])
    print(f"Total sections to process: {len(sections)}")

    # Reset entity tracking for new article
    extractor.reset_tracking()

    sections_to_skip = {"See also", "Notes", "References", "Works cited", "External links"}
    
    for section_idx, section in enumerate(sections, 1):
        try:
            section_text = []
            section_title = section.get('section_title', '')

            if section_title in sections_to_skip:  # Skip specified sections
                continue

            # Get section data
            main_content = section.get('content', [])
            section_text.extend(main_content)
            
            # Add subsection content
            for subsection in section.get('subsections', []):
                section_text.extend(subsection.get('content', []))
            
            # Process the combined section text
            if section_text:
                print(f"\nProcessing section {section_idx}: {section_title}")
                combined_text = "\n".join(section_text)
                chunk = TextChunk(
                    content=combined_text,
                    section_name=section_title,
                    heading_level="main",
                    section_text=section_text,
                    section_index=section_idx  # Pass the 1-based index
                )
                extractor.process_section(chunk)
                        
        except Exception as e:
            print(f"Error processing section {section_idx}: {str(e)}")
            continue
    
    return extractor.get_sorted_entities()  # Get final merged entities

def save_relations(self, output_path: str, processing_mode: str, title: str):
    """Save relations to a JSON file."""
    summary = {
        'metadata': {
            'title': title,
            'processing_mode': processing_mode,
            'timestamp': datetime.now().isoformat(),
            'total_relations': len(self.relations)
        },
        'relations': self.relations
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=4, ensure_ascii=False)

def build_concept_hierarchy(results: List[Dict]) -> Dict:
    """Build a hierarchical structure of concepts based on builds_on relationships."""
    hierarchy = {}
    
    # First pass: create nodes for all concepts
    for entity in results:
        hierarchy[entity['id']] = {
            'children': [],  # Change from set() to list
            'parents': []    # Change from set() to list
        }
    
    # Second pass: establish relationships
    for entity in results:
        for parent in entity.get('builds_on', []):  # Add get() with default empty list
            if parent.lower() in hierarchy:  # Convert to lowercase for comparison
                parent_key = parent.lower()
                child_key = entity['id'].lower()
                # Add to lists if not already present
                if child_key not in hierarchy[parent_key]['children']:
                    hierarchy[parent_key]['children'].append(child_key)
                if parent_key not in hierarchy[child_key]['parents']:
                    hierarchy[child_key]['parents'].append(parent_key)
    
    return hierarchy

def print_concept_hierarchy(hierarchy: Dict, root_concepts=None, level=0):
    """Print the concept hierarchy in a tree-like format."""
    if root_concepts is None:
        # Start with concepts that have no parents
        root_concepts = [concept for concept, data in hierarchy.items() 
                        if not data['parents']]
    
    for concept in root_concepts:
        print("  " * level + "└─ " + concept)
        children = hierarchy[concept]['children']
        if children:
            print_concept_hierarchy(hierarchy, children, level + 1)

def save_and_summarize_results(results: List[Dict], output_path: str, processing_mode: str, article_title: str, category: str):
    """Save results to file and print summary."""
    print("\nFinal Results for Article:", article_title)
    print("=" * 50)

    # Load existing results if the file already exists
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    else:
        existing_data = {'metadata': {'processing_mode': processing_mode, 'timestamp': datetime.now().isoformat()}}

    # Update existing data with the new article results
    existing_data[article_title] = {
        'category': category, 
        'total_entities': len(results),
        'entities': results
    }

    # Save updated results to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=4, ensure_ascii=False)


def main(processing_mode='section'):
    # Initialize the entity extractor
    api_key = os.getenv('OpenAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found. Please set OpenAI_API_KEY environment variable.")
    
    # Initialize the entity extractor with your actual API key
    extractor = OptimizedEntityExtractor(
        api_key=api_key,
        cache_version="10.0"
    )
    
    # Load your articles
    with open('data/text_sample.json', 'r', encoding='utf-8') as f:
        data = json.load(f)  # Load the entire JSON
        articles = data.get('articles', {})  # Access the 'articles' key

    output_path = f"data/entity_analysis_{processing_mode}_results.json"  # Define output path

    for title, article in articles.items():  # Iterate over the items in the articles dictionary
        print(f"\nProcessing article: {title}")
        
        # Reset entity tracking for new article
        extractor.reset_tracking()

        category = article.get('category', 'Uncategorized')
        
        if processing_mode == 'section':
            entities = process_article_by_sections(title, article, extractor)
        else:  # paragraph mode
            entities = process_article_by_paragraphs(title, article, extractor)
            
        print(f"\nFound {len(entities)} entities in article {title}")
        for entity in entities[:5]:  # Show top 5 entities
            print(f"- {entity['id']} (frequency: {entity['frequency']})")

        # Save results for the current article
        save_and_summarize_results(entities, output_path, processing_mode, title, category)  # Save after each article
        
        # relation_output_path = f"data/relation_analysis_{processing_mode}_results.json"
        # extractor.save_relations(relation_output_path, processing_mode, title)

if __name__ == "__main__":
    main(processing_mode='paragraph')  # 'section' or 'paragraph'
