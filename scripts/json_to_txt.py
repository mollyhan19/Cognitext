import json
import re

def convert_math_expr(text):
    """Helper function to replace mathematical expressions with descriptive text"""
    
    # Replace common math symbols with readable text
    
    # Membership relations
    text = re.sub(r'(\w+) ∈ (\w+)', r'\1 is in \2', text)  # Example: L ∈ NP -> L is in NP
    text = re.sub(r'(\w+) ∉ (\w+)', r'\1 is not in \2', text)  # Example: L ∉ NP -> L is not in NP
    
    # Polynomial-time reducibility
    text = re.sub(r'(\w+) ≤p (\w+)', r'\1 is polynomial-time reducible to \2', text)  # Example: L' ≤p L -> L' is polynomial-time reducible to L
    text = re.sub(r'(\w+) ≤ (\w+)', r'\1 is less than or equal to \2', text)  # Example: x ≤ y -> x is less than or equal to y
    
    # Equalities and inequalities
    text = re.sub(r'(\w+) ≠ (\w+)', r'\1 is not equal to \2', text)  # Example: P ≠ NP -> P is not equal to NP
    text = re.sub(r'(\w+) = (\w+)', r'\1 is equal to \2', text)  # Example: A = B -> A is equal to B
    text = re.sub(r'(\w+) ≡ (\w+)', r'\1 is congruent to \2', text)  # Example: x ≡ y -> x is congruent to y
    
    # Set operations
    text = re.sub(r'(\w+) ∪ (\w+)', r'\1 union \2', text)  # Example: A ∪ B -> A union B
    text = re.sub(r'(\w+) ∩ (\w+)', r'\1 intersection \2', text)  # Example: A ∩ B -> A intersection B
    text = re.sub(r'(\w+) ⊆ (\w+)', r'\1 is a subset of \2', text)  # Example: A ⊆ B -> A is a subset of B
    text = re.sub(r'(\w+) ⊂ (\w+)', r'\1 is a proper subset of \2', text)  # Example: A ⊂ B -> A is a proper subset of B
    text = re.sub(r'(\w+) ⊇ (\w+)', r'\1 is a superset of \2', text)  # Example: A ⊇ B -> A is a superset of B
    text = re.sub(r'(\w+) ⊃ (\w+)', r'\1 is a proper superset of \2', text)  # Example: A ⊃ B -> A is a proper superset of B
    
    # Logical symbols
    text = re.sub(r'¬', r'not', text)  # Example: ¬A -> not A
    text = re.sub(r'∧', r'and', text)  # Example: A ∧ B -> A and B
    text = re.sub(r'∨', r'or', text)   # Example: A ∨ B -> A or B
    text = re.sub(r'⇒', r'implies', text)  # Example: A ⇒ B -> A implies B
    text = re.sub(r'⇔', r'is equivalent to', text)  # Example: A ⇔ B -> A is equivalent to B
    
    # Other common symbols
    text = re.sub(r'∀', r'for all', text)  # Example: ∀x -> for all x
    text = re.sub(r'∃', r'exists', text)   # Example: ∃x -> exists x
    text = re.sub(r'∅', r'empty set', text)  # Example: ∅ -> empty set
    text = re.sub(r'∞', r'infinity', text)  # Example: ∞ -> infinity
    text = re.sub(r'→', r'arrow', text)  # Example: A → B -> A arrow B
    
    # Fractions
    text = re.sub(r'(\d+)/(\d+)', r'\1 over \2', text)  # Example: 1/2 -> 1 over 2
    
    return text

def extract_text_from_json(input_json, output_txt):
    """Converts JSON structure into a structured text file with readable math expressions."""
    with open(input_json, 'r') as json_file:
        data = json.load(json_file)
    
    with open(output_txt, 'w') as output_file:
        for article_title, article in data['articles'].items():
            # Writing the category and title
            category = article.get('category', 'Unknown category')
            output_file.write(f"Category: {category}\n")
            output_file.write(f"Title: {article_title}\n\n")
            
            # Writing the sections and their content
            for section in article.get('sections', []):
                section_title = section.get('section_title', 'No section title')
                output_file.write(f"Section: {section_title}\n")
                content = section.get('content', [])
                
                for paragraph in content:
                    # Clean up math expressions in the content
                    paragraph = convert_math_expr(paragraph)
                    output_file.write(f"{paragraph}\n")
                
                output_file.write("\n")
            
            # Writing any subsections if present
            for subsection in article.get('sections', []):
                if subsection.get('subsections'):
                    for sub in subsection['subsections']:
                        subsection_title = sub.get('section_title', 'No subsection title')
                        output_file.write(f"Subsection: {subsection_title}\n")
                        sub_content = sub.get('content', [])
                        
                        for sub_paragraph in sub_content:
                            sub_paragraph = convert_math_expr(sub_paragraph)
                            output_file.write(f"{sub_paragraph}\n")
                        
                        output_file.write("\n")

input_json = '/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json' 
output_txt = '/Users/mollyhan/PycharmProjects/Cognitext/data/cleaned_text_sample.txt'
extract_text_from_json(input_json, output_txt)