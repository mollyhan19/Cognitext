from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple
from functools import lru_cache
import json
from openai import OpenAI
from cache_manager import CacheManager

@dataclass
class Entity:
    id: str
    layer: str
    frequency: int = 0
    section_count: int = 0
    variants: Set[str] = field(default_factory=set)
    appearances: List[Dict] = field(default_factory=list) # increment each time the concept or its variant is extracted
    sections_seen: Set[int] = field(default_factory=set) # track the number of unique sections in which the entity appears

    def __post_init__(self):
        # Normalize the ID
        self.id = self.normalize_term(self.id)
        # Normalize all variants and remove duplicates
        self.variants = {self.normalize_term(v) for v in self.variants}
        # Remove variants that are same as ID
        self.variants = {v for v in self.variants if v != self.id}
        valid_layers = {"priority", "secondary", "tertiary"}
        if self.layer not in valid_layers:
            raise ValueError(f"Layer must be one of: {valid_layers}")

    @staticmethod
    def normalize_term(term: str) -> str:
        """Normalize a term """
        return term.lower().strip()
    
    def add_appearance(self, appearance: Dict, variant: str):
        """
        Add a new appearance and update frequencies.
        Args:
            appearance: Dict containing appearance details
            variant: The form of the concept that was found (original or variant)
        """
        variant = self.normalize_term(variant)

        self.variants.add(variant)
        
        # Update frequency
        self.frequency += 1

        # Increment section frequency if it's a new section
        section = appearance.get("section_index")
        if section not in self.sections_seen:
            self.section_count += 1
            self.sections_seen.add(section)
        
        # Add appearance
        self.appearances.append({
            **appearance,
            "variant": variant,
            "evidence": appearance.get("evidence", "")
        })

    def merge_from(self, other: 'Entity'):
        """Merge another entity into this one"""
        # Merge variants
        self.variants.update(other.variants)
        # Merge sections seen
        self.sections_seen.update(other.sections_seen)
        # Update section count
        self.section_count = len(self.sections_seen)
        # Keep the higher priority layer
        if self._get_layer_priority(other.layer) > self._get_layer_priority(self.layer):
            self.layer = other.layer
        for app in other.appearances: # Add unique appearances
            self.add_appearance(app, app.get("variant", ""))
        # Update frequency
        self.frequency = len(self.appearances)

    def _get_layer_priority(self, layer: str) -> int:
        """Get numeric priority of layer (higher number = higher priority)"""
        priorities = {
            "priority": 3,
            "secondary": 2,
            "tertiary": 1
        }
        return priorities.get(layer, 0)

@dataclass
class TextChunk:
    content: str
    section_name: str
    heading_level: str  # 'main' or 'sub'
    section_text: List[str]  # All paragraphs in the section
    section_index: int
    paragraph_index: int = 1
    overlap_prev: Dict = None  # Previous section's content
    overlap_next: Dict = None  # Next section's content

    def __post_init__(self):
        self.overlap_prev = self.overlap_prev or {}
        self.overlap_next = self.overlap_next or {}

@dataclass
class Relation:
    source: str
    relation_type: str 
    target: str
    evidence: str
    section_index: int
    section_name: str
    confidence: float = 1.0
    
    def __eq__(self, other):
        """Consider relations equal if they have same source, type, and target."""
        return (self.source.lower() == other.source.lower() and
                self.relation_type.lower() == other.relation_type.lower() and
                self.target.lower() == other.target.lower())
    
    def __hash__(self):
        """Hash based on normalized source, type, and target."""
        return hash((self.source.lower(), self.relation_type.lower(), self.target.lower()))

class RelationTracker:
    def __init__(self, periodic_extraction_threshold: int = 3):
        self.local_relations = []  # All local relations from sections
        self.global_relations = []  # Relations from global extraction
        self.master_relations = []  # Merged local and global relations
        self.sections_processed = 0
        self.periodic_extraction_threshold = periodic_extraction_threshold

    def add_local_relations(self, relations: List[Relation]):
        """Add relations extracted from a section."""
        self.local_relations.extend(relations)
        self.sections_processed += 1
        self.merge_relations()  # Update master relations

    def add_global_relations(self, relations: List[Relation]):
        """Add relations from global extraction."""
        self.global_relations.extend(relations)
        self.merge_relations()  # Update master relations

    def merge_relations(self):
        """Merge local and global relations into master list, avoiding duplicates."""
        # Convert to sets to remove duplicates
        all_relations = set(self.local_relations) | set(self.global_relations)
        self.master_relations = list(all_relations)
    
class OptimizedEntityExtractor:
    def __init__(self, api_key: str, cache_version: str = "12.0"):
        self.client = OpenAI(api_key=api_key)
        self.cache_manager = CacheManager(version=cache_version)
        self.memory_cache = {}
        self.entities = {}

        self.sections_processed = 0

        self.relation_tracker = RelationTracker()

    @lru_cache(maxsize=1000)
    def _cached_api_call(self, prompt: str) -> str:
        """Cache API calls in memory."""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt},
                      {"role": "system", "content": "You are an expert at analyzing text and extracting meaningful concepts and relationships between them, with a special focus on making complex information more understandable. "}],
            temperature=0.1
        )
        return response.choices[0].message.content

    @staticmethod
    def clean_markdown_json(response: str) -> str:
        """Clean JSON string from markdown formatting."""
        # Remove markdown code blocks if present
        if '```' in response:
            # Split by code blocks and get the content
            parts = response.split('```')
            # Get the part that's between the first and second ``` markers
            if len(parts) >= 3:
                response = parts[1]
            else:
                response = parts[-1]
            
            # Remove any language identifier (e.g., 'json')
            if '\n' in response:
                response = response.split('\n', 1)[1]
        
        # Remove any remaining ``` markers
        response = response.replace('```', '')
        
        # Strip whitespace
        response = response.strip()
        
        # If the response starts with a newline, remove it
        if response.startswith('\n'):
            response = response[1:]
        
        return response

    def extract_entities_from_paragraph(self, paragraph: str, para_num: int, section_name: str, section_index: int, heading_level: str = "main") -> List[Dict]:
        """Extract entities from a paragraph with caching."""
        # Check memory cache
        if paragraph in self.memory_cache:
            print(f"  [P{para_num}] Using memory cache for entity extraction")
            return self.memory_cache[paragraph]

        # Check file cache
        cached_result = self.cache_manager.get_cached_entities(paragraph)
        if cached_result is not None:
            print(f"  [P{para_num}] Using file cache for entity extraction")
            self.memory_cache[paragraph] = cached_result
            return cached_result

        print(f"  [P{para_num}] Making API call for entity extraction")
        prompt = f"""
        A concept is defined as a significant term or phrase that represents a fundamental idea, entity, or phenomenon within a discipline. 
        Extract key concepts from the provided text using the following guidelines. The extracted concepts will be used for relation extraction and creating layered visualizations that support flexible, non-linear educational comprehension.

        **Context:**
        The extracted concepts should represent distinct units of knowledge, organized in priority layers to facilitate both high-level understanding and detailed exploration of the text.
        
        **Concept Layers:**
        1. **Core Concepts (Priority Layer):**
        - Primary theoretical concepts and fundamental principles
        - Key terminology and definitions essential to the topic
        - Major themes and overarching frameworks
        - Critical processes and mechanisms central to understanding
        
        2. **Supporting Concepts (Secondary Layer):**
        - Sub-processes and variations of core concepts
        - Related theories and complementary ideas
        - Component parts and organizational structures
        - Methodological approaches and analytical frameworks
        
        3. **Contextual Elements (Tertiary Layer):**
        - Author names and their key contributions
        - Specific examples and case studies
        - Historical context and developments
        - Applications and implementations
        - Measurements and quantitative data
        
        **Extraction Guidelines:**
        - Tag each extracted concept with its appropriate layer (core, supporting, contextual)
        - Ensure comprehensive coverage across all layers
        - Include concepts that answer: "What" (definitions and principles), "How" (processes and methods), "Why" (reasoning and implications) and"When" (temporal and contextual factors)
        - ONLY exclude purely anecdotal details unless they are crucial for defining a concept
        
        **Output Format:** 
        [
            {{
            "entity": "main_form",
            "context": "The exact sentence where this concept appeared", 
            "evidence: "Why this concept is essential for understanding the topic",
            "layer": "The layer (priority, secondary, or tertiary) of this concept"
            }}
        ]

        Paragraph:
        {paragraph}
        """

        try:
            response = self._cached_api_call(prompt)
            entities = json.loads(OptimizedEntityExtractor.clean_markdown_json(response))

            # Cache results
            self.memory_cache[paragraph] = entities
            self.cache_manager.cache_entities(paragraph, entities)

            return entities
        except Exception as e:
            print(f"  [P{para_num}] Error extracting entities: {str(e)}")
            return []

    def extract_entities_from_section(self, section_content: List[str], section_name: str, section_index: int) -> List[Dict]:
        """Extract entities from a section with caching."""
        # Combine all text in the section including subheadings
        section_text = []

        # Add main text
        if "text" in section_content:
            section_text.extend(section_content["text"])

        # Add subheading text
        if "subheadings" in section_content:
            for subheading, subcontent in section_content["subheadings"].items():
                if "text" in subcontent:
                    section_text.extend(subcontent["text"])

        full_section_text = "\n".join(section_text)

        # Check memory cache
        if full_section_text in self.memory_cache:
            print(f"  [S{section_index}] Using memory cache for entity extraction")
            return self.memory_cache[full_section_text]

        # Check file cache
        cached_result = self.cache_manager.get_cached_entities(full_section_text)
        if cached_result is not None:
            print(f"  [S{section_index}] Using file cache for entity extraction")
            self.memory_cache[full_section_text] = cached_result
            return cached_result

        print(f"  [S{section_index}] Making API call for entity extraction")
        prompt = f"""
        A concept is defined as a significant term or phrase that represents a fundamental idea, entity, or phenomenon within a discipline. 
        Extract key concepts from the provided text using the following guidelines. The extracted concepts will be used for relation extraction and creating layered visualizations that support flexible, non-linear educational comprehension.

        **Concept Layers:**
        1. **Core Concepts (Priority Layer):**
        - Primary theoretical concepts and fundamental principles
        - Key terminology and definitions essential to the topic
        - Major themes and overarching frameworks
        - Critical processes and mechanisms central to understanding
        
        2. **Supporting Concepts (Secondary Layer):**
        - Sub-processes and variations of core concepts
        - Related theories and complementary ideas
        - Component parts and organizational structures
        - Methodological approaches and analytical frameworks
        
        3. **Contextual Elements (Tertiary Layer):**
        - Author names and their key contributions
        - Specific examples and case studies
        - Historical context and developments
        - Applications and implementations
        - Measurements and quantitative data
        
        **Extraction Guidelines:**
        - Tag each extracted concept with its appropriate layer (priority, secondary, tertiary)
        - Ensure comprehensive coverage across all layers
        - Include concepts that answer: "What" (definitions and principles), "How" (processes and methods), "Why" (reasoning and implications) and"When" (temporal and contextual factors)
        - ONLY exclude purely anecdotal details unless they are crucial for defining a concept
        
        **Output Format:** 
        [
            {{
            "entity": "main_form",
            "context": "The exact sentence where this concept appeared", 
            "evidence: "Why this concept is essential for understanding the topic",
            "layer": "priority/secondary/tertiary" # Must be exactly one of these values
            }}
        ]
        
        Section text:
        {full_section_text}
        """

        try:
            response = self._cached_api_call(prompt)
            entities = json.loads(OptimizedEntityExtractor.clean_markdown_json(response))
            
            # Cache results
            self.memory_cache[full_section_text] = entities
            self.cache_manager.cache_entities(full_section_text, entities)
            
            return entities
        except Exception as e:
            print(f"Error extracting entities: {str(e)}")
            return []

    def reset_tracking(self):
        """Reset entity tracking to start fresh."""
        self.entities = {}

    def reset_relation_tracking(self):
        """Reset entity tracking to start fresh."""
        self.relations = {}

    def extract_local_relations(self, text: str, concepts: List[Dict], section_info: Dict) -> List[Relation]:
        """Extract relationships between concepts within a section."""

        print(f"  Making API call for local relation extraction")
        prompt = f"""
        Extract key relationships between these available concepts using the following guidelines. The extracted relations will be used for visualizations to aid educational comprehension.
        
        **Context:**
        The extracted relations should represent meaningful connections that contribute to understanding the main ideas in the text.
        
        **Guidelines:**
        - Ensure that the relations are clearly defined and relevant to the text's main ideas.
        - Focus on capturing a variety of relationship types without restricting to specific categories.
        - Avoid speculative relationships; only include those with explicit or strong implicit textual support.


        Available Concepts:
        {json.dumps([c["id"] for c in concepts], indent=2)}

        **Output Format:** 
        {{
            "relations": [
                {{
                    "source": "source concept",
                    "relation_type": "type of relationship",
                    "target": "target concept",
                    "evidence": "text evidence for this relationship"
                }}
            ]
        }}

        Section Text:
        {text}
        """

        try:
            response = self._cached_api_call(prompt)
            relations_data = json.loads(self.clean_markdown_json(response))
            
            relations = []
            for rel in relations_data["relations"]:
                relation = Relation(
                    source=rel["source"],
                    relation_type=rel["relation_type"],
                    target=rel["target"],
                    evidence=rel["evidence"],
                    section_index=section_info["section_index"],
                    section_name=section_info["section_name"]
                )
                relations.append(relation)
            
            return relations
                
        except Exception as e:
            print(f"Error extracting section relations: {str(e)}")
            return []
        
    def extract_global_relations(self, master_concepts: List[Dict]) -> List[Relation]:
        print(f"  Making API call for global relation extraction")
        """Extract global relationships using all processed concepts."""
        prompt = f"""
        Extract global relationships using all processed concepts. The focus is on identifying high-level connections that span across sections or paragraphs, providing a comprehensive understanding of how concepts interrelate on a broader scale.
        
        **Context:**
        The extracted global relationships should illustrate overarching connections that tie together multiple sections, enhancing the reader’s comprehension of the text as a whole.

        **Guidelines:**
        - Identify relationships that are significant at a higher level, beyond individual sections or paragraphs.
        - Include relationships that show how concepts influence each other across different contexts or sections.
        - Ensure each identified relationship is supported by reasoning or textual evidence, highlighting the connection’s relevance to the overall content.

        Available Concepts:
        {json.dumps([c["id"] for c in master_concepts], indent=2)}

        Return in JSON format:
        {{
            "relations": [
                {{
                    "source": "source concept",
                    "relation_type": "type of relationship",
                    "target": "target concept",
                    "evidence": "reasoning for this relationship"
                }}
            ]
        }}
        """

        try:
            response = self._cached_api_call(prompt)
            relations_data = json.loads(self.clean_markdown_json(response))
            
            relations = []
            for rel in relations_data["relations"]:
                relation = Relation(
                    source=rel["source"],
                    relation_type=rel["relation_type"],
                    target=rel["target"],
                    evidence=rel["evidence"],
                    section_index=-1,  # Indicates global relation
                    section_name="global"
                )
                relations.append(relation)
            
            return relations
                
        except Exception as e:
            print(f"Error extracting global relations: {str(e)}")
            return []
    
    def get_all_relations(self) -> Dict:
        """Get all three types of relations."""
        return {
            "local_relations": [
                {
                    "source": rel.source,
                    "relation_type": rel.relation_type,
                    "target": rel.target,
                    "evidence": rel.evidence,
                    "section_name": rel.section_name,
                    "section_index": rel.section_index
                }
                for rel in self.relation_tracker.local_relations
            ],
            "global_relations": [
                {
                    "source": rel.source,
                    "relation_type": rel.relation_type,
                    "target": rel.target,
                    "evidence": rel.evidence,
                }
                for rel in self.relation_tracker.global_relations
            ],
            "master_relations": [
                {
                    "source": rel.source,
                    "relation_type": rel.relation_type,
                    "target": rel.target,
                    "evidence": rel.evidence,
                    "section_name": rel.section_name,
                    "section_index": rel.section_index
                }
                for rel in self.relation_tracker.master_relations
            ]
        }

    def compare_concept_lists(self, list1: List[Dict], list2: List[Dict]) -> Dict[str, str]:
        """Compare two lists of entities with caching."""
        # Check memory cache
        cache_key = (
            json.dumps(sorted(list1, key=lambda x: x['entity']), sort_keys=True),
            json.dumps(sorted(list2, key=lambda x: x['entity']), sort_keys=True)
        )

        if cache_key in self.memory_cache:
            print("Using memory cache for list comparison")
            return self.memory_cache[cache_key]

        # Check file cache
        cached_result = self.cache_manager.get_cached_comparison(list1, list2)
        if cached_result is not None:
            print("  Using file cache for list comparison")
            self.memory_cache[cache_key] = cached_result
            return cached_result

        print("  Making API call for list comparison")
        
        # Create a sample output format without f-string
        sample_output = {
            "water bear": "tardigrade",
            "tardigrade species": "tardigrade"
        }

        # Normalize case for comparison
        normalized_list1 = [
            {
                "entity": ent["entity"].lower(),
                "context": ent["context"]
            }
            for ent in list1
        ]
        
        normalized_list2 = [
            {
                "entity": ent["entity"].lower(),
                "context": ent["context"]
            }
            for ent in list2
        ]

        prompt = f"""
        Compare these two lists of concepts and identify which ones represent EXACTLY the same abstract idea or unit of knowledge.
        If a concept in List 2 matches one in List 1, it should be treated as a variant of that concept.
        
        Guidelines for matching:
        1. Match concepts that: 
            - Refer to exactly the same concept
            - Are synonyms or alternative expressions
            - Mean the same thing in different contexts
        
        2. Do NOT match concepts that:
            - Are merely related or connected (e.g., "tardigrade anatomy" ≠ "tardigrade")
            - Have a hierarchical relationship
            - Represent different aspects of the same topic
        
        Return a simple dictionary mapping concepts from List 2 to their matches in List 1.
        If no match exists, don't include that concept.

        Example output format:
        {json.dumps(sample_output, indent=2)}

        List 1:
        {json.dumps(normalized_list1, indent=2)}

        List 2:
        {json.dumps(normalized_list2, indent=2)}
        """

        try:
            response = self._cached_api_call(prompt)
            matches = json.loads(self.clean_markdown_json(response))


            original_case_matches = {}
            for new_entity in list2:
                if new_entity["entity"].lower() in matches:
                    # Find original case in list1
                    for orig_entity in list1:
                        if orig_entity["entity"].lower() == matches[new_entity["entity"].lower()]:
                            original_case_matches[new_entity["entity"]] = orig_entity["entity"]
                            break
            return original_case_matches
        
        except Exception as e:
            print(f"Error comparing entity lists: {str(e)}")
            return {}

    def process_section(self, chunk: TextChunk):
        try:
            new_entities = self.extract_entities_from_section(
                {"text": chunk.section_text, "subheadings": {}},
                chunk.section_name,
                chunk.section_index
            )

            # Create case-insensitive lookup dictionary
            entities_lookup = {k.lower(): k for k in self.entities.keys()}

            # Always attempt to merge or create entities
            try:
                # For first section or subsequent sections, follow same logic
                if not self.entities:
                    # First section processing
                    existing_entities = []
                else:
                    # Get existing entities for comparison
                    existing_entities = [
                        {
                            "entity": ent.id,
                            "context": "Previously identified concept"
                        }
                        for ent in self.entities.values()
                    ]

                # Get semantic matches
                matches = self.compare_concept_lists(existing_entities, new_entities)
                print(f"\nFound matches: {json.dumps(matches, indent=2)}")
                
                # Process each new entity
                for new_entity in new_entities:
                    try:
                        entity_id = new_entity["entity"]
                        # Determine the layer
                        layer = new_entity.get("layer", "tertiary")  # Default to tertiary if missing
                        if layer not in {"priority", "secondary", "tertiary"}:
                            layer = "tertiary"  # Default for invalid values
                        appearance = {
                            "section": chunk.section_name,
                            "section_index": chunk.section_index,
                            "heading_level": chunk.heading_level,
                            "variant": entity_id,
                            "context": new_entity.get("context", "")
                        }

                        if entity_id in matches:
                            existing_id = matches[entity_id]
                            print(f"\nMerging '{entity_id}' into existing concept '{existing_id}'")
                            
                            # Look up the actual key using case-insensitive comparison
                            actual_key = entities_lookup.get(existing_id.lower())
                            
                            if actual_key:
                                self.entities[actual_key].add_appearance(appearance, entity_id)
                                print(f"Successfully merged '{entity_id}' as variant")
                            else:
                                # If no match found, create new entity
                                print(f"Creating new entity for '{entity_id}' with layer '{layer}'")
                                new_entity_obj = Entity(id=entity_id, layer=layer)
                                new_entity_obj.add_appearance(appearance, entity_id)
                                self.entities[entity_id] = new_entity_obj
                        else:
                            # Create new entity
                            print(f"\nCreating new entity '{entity_id}' with layer '{layer}'")
                            new_entity_obj = Entity(id=entity_id, layer=layer)
                            new_entity_obj.add_appearance(appearance, entity_id)
                            self.entities[entity_id] = new_entity_obj
                            print(f"Successfully created new entity")

                    except Exception as e:
                        print(f"\nError processing entity: {str(e)}")
                        continue

            except Exception as e:
                print(f"Error processing section: {str(e)}")

            section_concepts = [
                {"id": ent.id, "variants": list(ent.variants)}
                for ent in self.entities.values()
                if any(app["section_index"] == chunk.section_index for app in ent.appearances)
            ]

            '''
            section_relations = self.extract_local_relations(
                chunk.content,  # Use the raw content for relation extraction
                section_concepts,
                {
                    "section_index": chunk.section_index,
                    "section_name": chunk.section_name
                }
            )
            
            # Add to relation tracker
            self.relation_tracker.add_local_relations(section_relations)
            
            # Periodic global relation extraction
            if (self.relation_tracker.sections_processed % 
                self.relation_tracker.periodic_extraction_threshold == 0):
                global_relations = self.extract_global_relations(self.get_sorted_entities())
                self.relation_tracker.add_global_relations(global_relations)
            '''

        except Exception as e:
            print(f"Error in main section processing: {str(e)}")

    def process_paragraph(self, chunk: TextChunk):
        """Process a paragraph and update entity tracking."""
        try:
            # 1. Extract raw entities from GPT
            new_entities = self.extract_entities_from_paragraph(
                paragraph=chunk.content,
                para_num=chunk.paragraph_index,
                section_name=chunk.section_name,
                section_index=chunk.section_index,
                heading_level=chunk.heading_level
            )

            # Create case-insensitive lookup dictionary
            entities_lookup = {k.lower(): k for k in self.entities.keys()}

            # Always attempt to merge or create entities
            try:
                # For first paragraph or subsequent paragraphs, follow same logic
                if not self.entities:
                    # First paragraph processing
                    existing_entities = []
                else:
                    # Get existing entities for comparison
                    existing_entities = [
                        {
                            "entity": ent.id,
                            "context": "Previously identified concept"
                        }
                        for ent in self.entities.values()
                    ]

                # Get semantic matches
                matches = self.compare_concept_lists(existing_entities, new_entities)
                print(f"\nFound matches: {json.dumps(matches, indent=2)}")

                # Process each new entity
                for new_entity in new_entities:
                    try:
                        entity_id = new_entity["entity"]
                        appearance = {
                            "section": chunk.section_name,
                            "section_index": chunk.section_index,
                            "paragraph_index": chunk.paragraph_index,
                            "heading_level": chunk.heading_level,
                            "variant": entity_id,
                            "context": new_entity.get("context", "")
                        }

                        if entity_id in matches:
                            existing_id = matches[entity_id]
                            print(f"\nMerging '{entity_id}' into existing concept '{existing_id}'")

                            # Look up the actual key using case-insensitive comparison
                            actual_key = entities_lookup.get(existing_id.lower())

                            if actual_key:
                                self.entities[actual_key].add_appearance(appearance, entity_id)
                                if "layer" in new_entity:
                                    self.entities[actual_key].layer.update(new_entity["layer"])
                                print(f"Successfully merged '{entity_id}' as variant")
                            else:
                                # If no match found, create new entity
                                print(f"No case-insensitive match found for '{existing_id}', creating new entity")
                                new_entity_obj = Entity(id=entity_id)
                                new_entity_obj.add_appearance(appearance, entity_id)
                                if "layer" in new_entity:
                                    new_entity_obj.layer.update(new_entity["layer"])
                                self.entities[entity_id] = new_entity_obj
                        else:
                            # Create new entity
                            print(f"\nCreating new entity '{entity_id}'")
                            new_entity_obj = Entity(id=entity_id)
                            new_entity_obj.add_appearance(appearance, entity_id)
                            if "layer" in new_entity:
                                new_entity_obj.layer.update(new_entity["layer"])
                            self.entities[entity_id] = new_entity_obj
                            print(f"Successfully created new entity")

                    except Exception as e:
                        print(f"\nError processing entity: {str(e)}")
                        continue

            except Exception as e:
                print(f"Error processing paragraph: {str(e)}")

            # Extract local relations for this paragraph
            section_concepts = [
                {"id": ent.id, "variants": list(ent.variants)}
                for ent in self.entities.values()
                if any(app.get("section_index") == chunk.section_index and
                       app.get("paragraph_index") == chunk.paragraph_index
                       for app in ent.appearances)
            ]

            section_relations = self.extract_local_relations(
                chunk.content,  # Use the raw content for relation extraction
                section_concepts,
                {
                    "section_index": chunk.section_index,
                    "section_name": chunk.section_name
                }
            )

            # Add to relation tracker
            self.relation_tracker.add_local_relations(section_relations)

            # Periodic global relation extraction
            if (self.relation_tracker.sections_processed %
                    self.relation_tracker.periodic_extraction_threshold == 0):
                global_relations = self.extract_global_relations(self.get_sorted_entities())
                self.relation_tracker.add_global_relations(global_relations)

        except Exception as e:
            print(f"Error in paragraph processing: {str(e)}")
    
    def get_sorted_entities(self) -> List[Dict]:
        """Return entities sorted by frequency."""
        sorted_entities = sorted(
            self.entities.values(), 
            key=lambda x: (x.section_count, x.frequency), 
            reverse=True
        )

        return [
        {
            "id": entity.id,
            "frequency": entity.frequency,
            "section_count": entity.section_count,
            "variants": list(entity.variants),
            "appearances": [
                {
                    "section": app["section"],
                    "section_index": app["section_index"],
                    "variant": app["variant"],
                    "context": app.get("context", "")
                }
                for app in entity.appearances
            ],
            "layer": list(entity.layer)
        }
        for entity in sorted_entities
    ]