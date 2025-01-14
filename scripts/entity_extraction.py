from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple
from functools import lru_cache
import json
from openai import OpenAI
from cache_manager import CacheManager

@dataclass
class Entity:
    id: str
    frequency: int = 0
    section_count: int = 0
    variants: Set[str] = field(default_factory=set)
    appearances: List[Dict] = field(default_factory=list) # increment each time the concept or its variant is extracted
    sections_seen: Set[int] = field(default_factory=set) # track the number of unique sections in which the entity appears
    builds_on: Set[str] = field(default_factory=set)  

    def __post_init__(self):
        # Normalize the ID
        self.id = self.normalize_term(self.id)
        # Normalize all variants and remove duplicates
        self.variants = {self.normalize_term(v) for v in self.variants}
        # Remove variants that are same as ID
        self.variants = {v for v in self.variants if v != self.id}

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
        self.builds_on.update(other.builds_on)
        for app in other.appearances: # Add unique appearances
            self.add_appearance(app, app.get("variant", ""))
        # Update frequency
        self.frequency = len(self.appearances)

    def merge_from(self, other: 'Entity'):
        """Merge another entity into this one"""
        # Merge variants
        self.variants.update(other.variants)
        # Add unique appearances
        for app in other.appearances:
            self.add_appearance(app, app.get("variant", ""))

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

class Relation:
    source_concept: str
    target_concept: str
    relation_type: str
    evidence: str
    section_index: int
    section_name: str
    confidence: float = 1.0
    is_cross_section: bool = False

class OptimizedEntityExtractor:
    def __init__(self, api_key: str, cache_version: str = "10.0"):
        self.client = OpenAI(api_key=api_key)
        self.cache_manager = CacheManager(version=cache_version)
        self.memory_cache = {}
        self.entities = {}

        self.sections_processed = 0

        self.local_relations = []  # Store section-level relations
        self.global_relations = [] # Store cross-section relations
        self.extracted_sections = set()  # Track processed sections

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
        Extract key concepts from the provided text using the following guidelines. The extracted concepts will be used for relation extraction and visualizations to aid educational comprehension.

        **Context:**
        The extracted concepts should represent distinct units of knowledge that contribute to understanding the main ideas in the text.

        **Focus Areas:**
        1. **Foundational Concepts:**
        - Identify all core ideas, principles, and overarching themes central to the topic.
        - Include broad categories and specific examples that contribute to the foundational understanding.

        2. **Processes and Mechanisms:**
        - Extract detailed descriptions of processes, mechanisms, or systems, highlighting all steps, interactions, and their implications.
        - Emphasize not only major processes but also sub-processes and any variations.

        3. **Supporting Structures:**
        - Identify component parts, subsystems, and organizational structures.
        - Include measurements, scales, or any quantitative data that offer a deeper understanding.
        
        **Guidelines:**
        - Ensure concepts are comprehensive, covering all possible relevant aspects of the topic.
        - Include concepts that answer "what," "how," "why," and "when," ensuring a broad capture of informative elements.
        - ONLY exclude purely anecdotal details unless they are crucial for defining a concept.

        **Output Format:** 
        [
            {{
            "entity": "main_form",
            "context": "The exact sentence where this concept appeared", 
            "evidence: "Why this concept is essential for understanding the topic",
            "builds_on": ["list of prerequisite concepts if any"]
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

    def extract_entities_from_section(self, section_content: Dict, section_name: str, section_index: int) -> List[Dict]:
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
        Extract key concepts from the provided text using the following guidelines. The extracted concepts will be used for relation extraction and visualizations to aid educational comprehension.

        **Context:**
        The extracted concepts should represent distinct units of knowledge that contribute to understanding the main ideas in the text.

        **Focus Areas:**
        1. **Foundational Concepts:**
        - Identify all core ideas, principles, and overarching themes central to the topic.
        - Include broad categories and specific examples that contribute to the foundational understanding.

        2. **Processes and Mechanisms:**
        - Extract detailed descriptions of processes, mechanisms, or systems, highlighting all steps, interactions, and their implications.        
        - Emphasize not only major processes but also sub-processes and any variations.

        3. **Supporting Structures:**
        - Identify component parts, subsystems, and organizational structures.
        - Include measurements, scales, or any quantitative data that offer a deeper understanding.
        
        **Guidelines:**
        - Ensure concepts are comprehensive, covering all possible relevant aspects of the topic.
        - Include concepts that answer "what," "how," "why," and "when," ensuring a broad capture of informative elements.
        - ONLY exclude purely anecdotal details unless they are crucial for defining a concept.

        **Output Format:** 
        [
            {{
            "entity": "main_form",
            "context": "The exact sentence where this concept appeared", 
            "evidence: "Why this concept is essential for understanding the topic",
            "builds_on": ["list of prerequisite concepts if any"]
            }}
        ]
        
        Section text:
        {full_section_text}
        """

        try:
            response = self._cached_api_call(prompt)
            print(f"\n=== Raw GPT Response for Section {section_name} ===")
            print(response)
            print("=" * 50)

            entities = json.loads(OptimizedEntityExtractor.clean_markdown_json(response))
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


    def extract_local_relations(self, text: str, section_concepts: List[Dict], section_info: Dict) -> List[Relation]:
        """Extract relationships between concepts within a section."""
        prompt = f"""
        Extract relationships between these concepts within this section of text.
        Focus on relationships that are explicitly mentioned or strongly implied.
        
        Concepts available:
        {[c["entity"] for c in section_concepts]}
        
        Guidelines:
        1. Only extract relationships with clear textual evidence
        2. Relationships should help explain how concepts connect
        3. Focus on direct relationships visible in this section
        
        Return JSON format:
        {{
            "relations": [
                {{
                    "source": "concept1",
                    "target": "concept2",
                    "relation_type": "describes the relationship",
                    "evidence": "exact text supporting this relationship"
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
                    source_concept=rel["source"],
                    target_concept=rel["target"],
                    relation_type=rel["relation_type"],
                    evidence=rel["evidence"],
                    section_index=section_info["section_index"],
                    section_name=section_info["section_name"]
                )
                relations.append(relation)
            
            return relations
        except Exception as e:
            print(f"Error extracting local relations: {str(e)}")
            return []
        
    def extract_global_relations(self) -> List[Relation]:
        """Extract relationships between concepts across sections."""
        # Only extract global relations after processing multiple sections
        if len(self.extracted_sections) < 2:
            return []
            
        concepts_by_section = {}
        for entity in self.entities.values():
            for appearance in entity.appearances:
                section_idx = appearance["section_index"]
                if section_idx not in concepts_by_section:
                    concepts_by_section[section_idx] = set()
                concepts_by_section[section_idx].add(entity.id)

        prompt = f"""
        Analyze potential relationships between concepts that appear in different sections.
        Focus on high-level relationships that span multiple sections.
        
        Concepts by section:
        {json.dumps(concepts_by_section, indent=2)}
        
        Prior local relationships found:
        {json.dumps([(r.source_concept, r.relation_type, r.target_concept) for r in self.local_relations], indent=2)}
        
        Return only cross-section relationships in JSON format:
        {{
            "relations": [
                {{
                    "source": "concept1",
                    "target": "concept2", 
                    "relation_type": "relationship description",
                    "evidence": "reasoning for this relationship",
                    "sections_involved": [section_numbers]
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
                    source_concept=rel["source"],
                    target_concept=rel["target"],
                    relation_type=rel["relation_type"],
                    evidence=rel["evidence"],
                    section_index=-1,  # Indicates cross-section
                    section_name="cross-section",
                    is_cross_section=True
                )
                relations.append(relation)
                
            return relations
        except Exception as e:
            print(f"Error extracting global relations: {str(e)}")
            return []
    

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
        """Process a section and merge with existing entities."""
        try:
            new_entities = self.extract_entities_from_section(
                {"text": chunk.section_text, "subheadings": {}},
                chunk.section_name,
                chunk.section_index
            )

            # Create case-insensitive lookup dictionary
            entities_lookup = {k.lower(): k for k in self.entities.keys()}
            
            # For first section, initialize entities
            if not self.entities:
                for entity in new_entities:
                    try:
                        new_entity = Entity(id=entity["entity"])
                        appearance = {
                            "section": chunk.section_name,
                            "section_index": chunk.section_index,
                            "heading_level": chunk.heading_level,
                            "variant": entity["entity"],
                            "context": entity.get("context", ""), 
                            "evidence": entity.get("evidence", "")
                        }
                        new_entity.add_appearance(appearance, entity["entity"])
                        if "builds_on" in entity:
                            new_entity.builds_on.update(entity["builds_on"])
                        self.entities[entity["entity"]] = new_entity
                    except Exception as e:
                        print(f"Warning: Could not process initial entity: {str(e)}")
                        continue
                return

            # For subsequent sections
            try:
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
                                if "builds_on" in new_entity:
                                    self.entities[actual_key].builds_on.update(new_entity["builds_on"])
                                print(f"Successfully merged '{entity_id}' as variant")
                            else:
                                # If no match found, create new entity
                                print(f"No case-insensitive match found for '{existing_id}', creating new entity")
                                new_entity_obj = Entity(id=entity_id)
                                new_entity_obj.add_appearance(appearance, entity_id)
                                if "builds_on" in new_entity:
                                    new_entity_obj.builds_on.update(new_entity["builds_on"])
                                self.entities[entity_id] = new_entity_obj
                        else:
                            # Create new entity
                            print(f"\nCreating new entity '{entity_id}'")
                            new_entity_obj = Entity(id=entity_id)
                            new_entity_obj.add_appearance(appearance, entity_id)
                            if "builds_on" in new_entity:
                                new_entity_obj.builds_on.update(new_entity["builds_on"])
                            self.entities[entity_id] = new_entity_obj
                            print(f"Successfully created new entity")

                    except Exception as e:
                        print(f"\nError processing entity:")
                        print(f"Entity data: {json.dumps(new_entity, indent=2)}")
                        print(f"Current entities: {list(self.entities.keys())}")
                        print(f"Error details: {str(e)}")
                        continue

            except Exception as e:
                print(f"Error in section processing: {str(e)}")

        except Exception as e:
            print(f"Error in main section processing: {str(e)}")

        # relations = self.extract_relations(chunk.content, chunk.section_index)
        # self.store_relations(relations, chunk.section_name, chunk.section_index)
    
    '''
    def store_relations(self, relations: List[Relation], section_name: str, section_index: int):
        """Store relations in a structured format."""
        for relation in relations:
            self.relations.append({
                "head": relation.head,
                "relation": relation.relation,
                "tail": relation.tail,
                "context": relation.context,
                "section_name": section_name,
                "section_index": section_index
            })
    '''

    def process_paragraph(self, chunk: TextChunk):
        """Process a paragraph and update entity tracking."""
        try:
            # 1. Extract raw entities from GPT
            print("\n=== Raw GPT Extraction ===")
            new_entities = self.extract_entities_from_paragraph(
                paragraph=chunk.content,
                para_num=chunk.paragraph_index,
                section_name=chunk.section_name,
                section_index=chunk.section_index,
                heading_level=chunk.heading_level
            )
            print("Raw entities extracted:")
            print(json.dumps(new_entities, indent=2))
            print("=" * 50)

            # Create case-insensitive lookup dictionary
            entities_lookup = {k.lower(): k for k in self.entities.keys()}
            
            # For first paragraph, initialize entities
            if not self.entities:
                print("\n=== Initializing First Entities ===")
                for entity in new_entities:
                    try:
                        # Keep the original entity casing
                        new_entity = Entity(id=entity["entity"])  # This should keep the original casing
                        appearance = {
                            "section": chunk.section_name,
                            "section_index": chunk.section_index,
                            "paragraph_index": chunk.paragraph_index,
                            "heading_level": chunk.heading_level,
                            "variant": entity["entity"],
                            "context": entity.get("context", ""), 
                            "evidence": entity.get("evidence", "")
                        }
                        new_entity.add_appearance(appearance, entity["entity"])
                        if "builds_on" in entity:
                            new_entity.builds_on.update(entity["builds_on"])
                        self.entities[entity["entity"]] = new_entity  # Store with original casing
                        print(f"Added initial entity: {entity['entity']}")
                    except Exception as e:
                        print(f"Warning: Could not process initial entity: {str(e)}")
                        continue
                return

            # For subsequent paragraphs
            try:
                # 2. Get existing entities for comparison
                print("\n=== Matching Against Existing Entities ===")          
                existing_entities = [
                    {
                        "entity": ent.id,
                        "context": "Previously identified concept"
                    }
                    for ent in self.entities.values()
                ]

                # Print the existing entities
                print("Existing entities for comparison:")
                print(json.dumps(existing_entities, indent=2))

                # Print the new entities
                print("New entities for comparison:")
                print(json.dumps(new_entities, indent=2))

                # 3. Find matches
                print("\nLooking for matches...")
                matches = self.compare_concept_lists(existing_entities, new_entities)
                print("Found matches:")
                print(json.dumps(matches, indent=2))
                
                # 4. Process each new entity
                print("\n=== Processing New Entities ===")
                for new_entity in new_entities:
                    try:
                        entity_id = new_entity["entity"]
                        print(f"\nProcessing: {entity_id}")
                        
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
                            print(f"Matched with existing: {existing_id}")

                            # Look up the actual key using case-insensitive comparison
                            actual_key = entities_lookup.get(existing_id.lower())
                            
                            if actual_key:
                                self.entities[actual_key].add_appearance(appearance, entity_id)
                                if "builds_on" in new_entity:
                                    self.entities[actual_key].builds_on.update(new_entity["builds_on"])
                                print(f"Successfully merged '{entity_id}' as variant")
                            else:
                                # If no match found, create new entity
                                print(f"No case-insensitive match found for '{existing_id}', creating new entity")
                                new_entity_obj = Entity(id=entity_id)
                                new_entity_obj.add_appearance(appearance, entity_id)
                                if "builds_on" in new_entity:
                                    new_entity_obj.builds_on.update(new_entity["builds_on"])
                                self.entities[entity_id] = new_entity_obj
                        else:
                            # Create new entity
                            print(f"\nCreating new entity '{entity_id}'")
                            new_entity_obj = Entity(id=entity_id)
                            new_entity_obj.add_appearance(appearance, entity_id)
                            if "builds_on" in new_entity:
                                new_entity_obj.builds_on.update(new_entity["builds_on"])
                            self.entities[entity_id] = new_entity_obj
                            print(f"Successfully created new entity")

                    except Exception as e:
                        print(f"\nError processing entity:")
                        print(f"Entity data: {json.dumps(new_entity, indent=2)}")
                        print(f"Current entities: {list(self.entities.keys())}")
                        print(f"Error details: {str(e)}")
                        continue
                
            except Exception as e:
                print(f"Error processing paragraph {chunk.paragraph_index}: {str(e)}")

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
            "builds_on": list(entity.builds_on)
        }
        for entity in sorted_entities
    ]