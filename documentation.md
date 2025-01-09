# File Documentations

## Entity Extractor: entity_extraction.py

### Overview
The Entity Extractor is a robust system for extracting and analyzing key concepts from structured text documents. It supports both paragraph-level and section-level analysis, with built-in caching and entity tracking capabilities.

### Key Features
- Dual processing modes (paragraph or section-level)
- Multi-level caching system
- Entity deduplication and variant tracking
- Flexible text processing
- OpenAI GPT-4 integration

### System Architecture

#### Core Classes

##### 1. Entity
Represents a single extracted concept with its variants and appearances.
```python
@dataclass
class Entity:
    id: str                # Unique identifier
    variants: Set[str]     # Alternative forms
    appearances: List[Dict] # Locations in text
```

##### 2. TextChunk
Manages text segments for processing.
```python
@dataclass
class TextChunk:
    content: str          # Main text content
    section_name: str     # Section identifier
    heading_level: str    # Hierarchy level
    section_text: List[str] # Full text
    section_index: int    # Position
```
##### 3. OptimizedEntityExtractor
Main class for entity extraction processing.

#### Key Methods
Initialization and Setup
```python
def __init__(self, api_key: str, cache_version: str = "3.0")
    """Initializes extractor with API key and caching system."""

def reset_tracking(self)
    """Resets entity tracking to start fresh with new article."""
```
Text Processing and Preprocessing
```python
@staticmethod
def preprocess_text(articles_list: list, overlap_size: int = 1) -> List[TextChunk]
    """Preprocesses articles into manageable chunks with overlap."""

@staticmethod
def clean_markdown_json(json_str: str) -> str
    """Cleans JSON strings from markdown formatting."""
```
Caching and API Interaction
```python
def _cached_api_call(self, prompt: str) -> str
    """Makes cached API calls to OpenAI."""
```
Core Processing Methods
```python
def extract_entities_from_paragraph(self, paragraph: str, para_num: int) -> List[Dict]
    """Extracts entities from a single paragraph with caching."""

def extract_entities_from_section(self, section_content: Dict, section_name: str, section_num: int) -> List[Dict]
    """Extracts entities from an entire section with caching."""

def process_paragraph(self, paragraph: str, para_num: int)
    """Processes a paragraph and updates entity tracking."""

def process_section(self, section_content: Dict, section_name: str, section_num: int)
    """Processes a section and updates entity tracking."""
```
Entity Comparison and Management
```python
def compare_concept_lists(self, list1: List[Dict], list2: List[Dict]) -> Dict[str, str]
    """Compares two lists of entities to identify matches."""

def get_sorted_entities(self) -> List[Dict]
    """Returns entities sorted by frequency of appearance."""
```

## Entity Linking: entity_linking_main.py

### Overview
This file serves as the main driver for processing articles to extract and analyze key concepts/entities. It can handle articles in two ways: paragraph-by-paragraph or section-by-section analysis

### Key Features
- Dual processing modes (paragraph or section-level)
- Entity extraction with context: the `OptimizedEntityExtractor` processes each text chunk with context, considering surrounding paragraphs or sections.
- Automatic metadata generation (the processing mode, timestamps, and structural information such as total sections and paragraphs).
- Entity sorting by frequency and comprehensive summarization.


### System Architecture

#### Key Methods
Data Loading
```python
# Loads article data from JSON file
with open("text_sample.json", "r", encoding="utf-8") as f:
    data = json.load(f)
```
Main method
```python
def main(processing_mode='paragraph'):
    """processing_mode: Defines the mode of processing, either `'paragraph'` or `'section'."""
```
Paragraph-level processing 
```python
def process_article_by_paragraphs(article_title, article_data, extractor):
    """Processes an article by breaking it into paragraphs, extracting entities within each paragraph, and managing context between paragraphs."""
```
Section-level processing 
```python
def process_article_by_sections(article_title, article_data, extractor):
    """Processes an article by breaking it into sections, extracting entities within each section, and managing context between sections."""
```
Save and summary
```python
def save_and_summarize_results(results, output_path):
    """Saves the extracted results to a JSON file and prints a summary of the processed data."""
```

## Relation Extractor: relation_extraction.py
### Overview


### Key Features


### System Architecture

#### Core Classes

## Visualization: concept_graph.py