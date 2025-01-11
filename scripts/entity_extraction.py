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
        """Normalize a term by handling common variations."""
        term = term.lower().strip()
        # Handle plural forms of common words
        if term.endswith('s'):
            singular = term[:-1]
            if singular in {'tardigrade', 'concept', 'feature', 'process'}:
                return singular
        return term
    
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
            "variant": variant
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
    
    def validate_appearances(self) -> bool:
        """Validate that all appearance variants are registered."""
        valid_variants = {self.id} | self.variants
        invalid_appearances = []
        
        for appearance in self.appearances:
            variant = appearance.get("variant")
            if variant and variant not in valid_variants:
                invalid_appearances.append({
                    "section": appearance.get("section"),
                    "invalid_variant": variant
                })
        
        if invalid_appearances:
            print(f"Warning: Found invalid variants in appearances for {self.id}:")
            for invalid in invalid_appearances:
                print(f"  Section: {invalid['section']}, Invalid variant: {invalid['invalid_variant']}")
        
        return len(invalid_appearances) == 0

@dataclass
class TextChunk:
    content: str
    section_name: str
    heading_level: str  # 'main' or 'sub'
    section_text: List[str]  # All paragraphs in the section
    section_index: int
    overlap_prev: Dict = None  # Previous section's content
    overlap_next: Dict = None  # Next section's content

    def __post_init__(self):
        self.overlap_prev = self.overlap_prev or {}
        self.overlap_next = self.overlap_next or {}

class OptimizedEntityExtractor:
    def __init__(self, api_key: str, cache_version: str = "8.0", cleanup_interval: int = 3):
        self.client = OpenAI(api_key=api_key)
        self.cache_manager = CacheManager(version=cache_version)
        self.memory_cache = {}
        self.entities = {}

        self.cleanup_interval = cleanup_interval
        self.sections_processed = 0

    @lru_cache(maxsize=1000)
    def _cached_api_call(self, prompt: str) -> str:
        """Cache API calls in memory."""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt},
                      {"role": "system", "content": "You are an expert at analyzing text and extracting meaningful relationships between concepts, with a special focus on making complex information more understandable. "}],
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

    def extract_entities_from_paragraph(self, paragraph: str, para_num: int) -> List[Dict]:
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
        Extract key concepts that are crucial for understanding the main ideas in this paragraph. Each concept should represent a distinct unit of knowledge or understanding.
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
        Extract key concepts that are crucial for understanding the main ideas in this section using the following strict guidelines. Each concept should represent a distinct unit of knowledge that significantly contributes to understanding the topic.
        Section name: {section_name}

        Focus on: 
        1. Primary concepts that form the foundation of understanding.
            - Core ideas that other concepts build upon
            - Essential principles or characteristics
            - Distinctive features and capabilities  
            - Key classifications or categories
        2. Critical processes or mechanisms that explain the main ideas.
            - How things work or interact
            - Key sequences or developments
        3. Supporting structures and systems
            - Component parts and organization
            - Essential subsystems
            - Related elements and factors

        Guidelines for concept selection:
            - Include concepts necessary for understanding later topics
            - Include concepts that explain key "how" or "why" aspects
            - Exclude purely descriptive or anecdotal details unless they define the topic
                
        Output format:
        [
            {{
            "entity": "main_form",
            "context": "Why this concept is essential for understanding the topic",
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

    def preprocess_text(articles_list: list, overlap_size: int = 1) -> List[TextChunk]:
        chunks = []

        for article in articles_list:
            content = article["content"]
            sections = article.get("sections", [])

            for section_idx, section in enumerate(sections):
                for heading, content in section.items():
                    # Process main section content
                    main_text = content.get("text", [])
                    if main_text:
                        chunk = TextChunk(
                            content="\n\n".join(main_text),
                            section_name=heading,
                            heading_level="main",
                            section_text=main_text,
                            section_index=section_idx,
                            overlap_prev={
                                "section": sections[section_idx - 1] if section_idx > 0 else None
                            } if section_idx > 0 else None,
                            overlap_next={
                                "section": sections[section_idx + 1] if section_idx < len(sections) - 1 else None
                            } if section_idx < len(sections) - 1 else None
                        )
                        chunks.append(chunk)

                    # Process subheadings
                    for subheading, subcontent in content.get("subheadings", {}).items():
                        sub_text = subcontent.get("text", [])
                        if sub_text:
                            chunk = TextChunk(
                                content="\n\n".join(sub_text),
                                section_name=f"{heading} - {subheading}",
                                heading_level="sub",
                                section_text=sub_text,
                                section_index=section_idx,
                                overlap_prev={"main_section": main_text[-1]} if main_text else None,
                                overlap_next=None
                            )
                            chunks.append(chunk)

        return chunks

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
                            "context": entity.get("context", "")
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

    def are_concepts_related(self, concept1: str, concept2: str) -> bool:
        """Determine if two concepts are semantically related."""
        # Define related concept groups
        related_groups = [
            {"tardigrade", "water bear", "moss piglet", "tardigrada"},
            {"dna", "genetic", "genome", "chromosomal"},
            {"survival", "resistance", "tolerance", "adaptation"},
            # Add more related concept groups as needed
        ]

        # Normalize concepts
        c1 = self.normalize_term(concept1)
        c2 = self.normalize_term(concept2)

        # Check if concepts are in the same group
        for group in related_groups:
            if c1 in group and c2 in group:
                return True

        # Check if one concept contains the other (for compound terms)
        if c1 in c2 or c2 in c1:
            return True

        return False
    
    def process_all_sections(self, chunks: List[TextChunk]):
        """Process all sections with periodic cleanup."""
        total_chunks = len(chunks)
        print(f"Starting processing of {total_chunks} sections...")
        
        for i, chunk in enumerate(chunks, 1):
            print(f"\nProcessing section {i}/{total_chunks}: {chunk.section_name}")
            self.process_section(chunk)

        # Final cleanup
        print("\nPerforming final cleanup...")
        self.cleanup_entities()
        print(f"Processing complete. Final unique entities: {len(self.entities)}")

    def process_paragraph(self, paragraph: str, para_num: int):
        """Process paragraph and update entity tracking."""
        new_entities = self.extract_entities_from_paragraph(paragraph, para_num)

        # For first paragraph, initialize entities
        if not self.entities:
            for new_entity in new_entities:
                entity_id = new_entity["entity"]
                entity = Entity(
                    id=entity_id,
                    variants={entity_id} | set(new_entity["variants"])
                )
                entity.add_appearance({
                    "paragraph": para_num,
                    "form": entity_id
                })
                self.entities[entity_id] = entity
            return

        # For subsequent paragraphs, compare with existing entities
        existing_entities = [
            {"entity": ent.id, "variants": list(ent.variants)}
            for ent in self.entities.values()
        ]

        # Get matches between existing and new entities
        matches = self.compare_concept_lists(existing_entities, new_entities)

        # Process each new entity
        for new_entity in new_entities:
            entity_id = new_entity["entity"]
            appearance = {
                "paragraph": para_num,
                "form": entity_id
            }

            if entity_id in matches and matches[entity_id] is not None:
                # Found a match - merge with existing entity
                existing_id = matches[entity_id]
                existing_entity = self.entities[existing_id]

                # Update variants
                existing_entity.variants.add(entity_id)
                existing_entity.variants.update(new_entity["variants"])

                # Add new appearance
                existing_entity.add_appearance(appearance)

                print(f"Merged entity: {entity_id} -> {existing_id}")
                print(f"Updated frequency: {existing_entity.frequency}")
            else:
                # No match - create new entity
                entity = Entity(
                    id=entity_id,
                    variants={entity_id} | set(new_entity["variants"])
                )
                entity.add_appearance(appearance)
                self.entities[entity_id] = entity
                print(f"New entity: {entity_id}")
                print(f"Initial frequency: {entity.frequency}")

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
    
    def normalize_term(self, term: str) -> str:
        """Enhanced term normalization."""
        term = term.lower().strip()
        
        # Remove common suffixes that don't change the core meaning
        suffixes_to_remove = ['um', 'us', 'a', 'ae']
        for suffix in suffixes_to_remove:
            if term.endswith(suffix) and len(term) > len(suffix) + 3:  # Ensure we don't over-trim
                potential_root = term[:-len(suffix)]
                # Only remove if the root is substantial enough
                if len(potential_root) > 3:
                    term = potential_root
                    break
        
        # Handle plural forms more generally
        if term.endswith('s') and not term.endswith('ss'):  # Don't strip 'ss'
            singular = term[:-1]
            if len(singular) > 3:  # Only strip 's' if result is substantial
                term = singular
        
        return term

    def validate_appearances(self):
        """Validate that all appearance variants are registered."""
        valid_variants = {self.id} | self.variants
        invalid_appearances = []
        
        for appearance in self.appearances:
            variant = appearance.get("variant")
            if variant not in valid_variants:
                invalid_appearances.append({
                    "section": appearance.get("section"),
                    "invalid_variant": variant
                })
        
        if invalid_appearances:
            print(f"Warning: Found invalid variants in appearances for {self.id}:")
            for invalid in invalid_appearances:
                print(f"  Section: {invalid['section']}, Invalid variant: {invalid['invalid_variant']}")
        
        return len(invalid_appearances) == 0
    
    def are_terms_equivalent(self, term1: str, term2: str) -> bool:
        """Check if two terms are semantically equivalent."""
        # Normalize both terms
        norm1 = self.normalize_term(term1)
        norm2 = self.normalize_term(term2)
        
        # Direct match after normalization
        if norm1 == norm2:
            return True
        
        # Check if one term contains the other (for compound terms)
        if norm1 in norm2 or norm2 in norm1:
            # Only consider it a match if the longer term is not significantly longer
            longer = max(len(norm1), len(norm2))
            shorter = min(len(norm1), len(norm2))
            if longer <= shorter * 1.5:  # Arbitrary threshold, can be adjusted
                return True
        
        return False

    def cleanup_entities(self):
        """Merge any duplicate entities that were missed during processing."""
    
        entities_to_merge = {}

         # Compare each pair of entities
        entity_items = list(self.entities.items())
        for i, (id1, entity1) in enumerate(entity_items):
            for id2, entity2 in entity_items[i+1:]:
                if id1 != id2 and id2 not in entities_to_merge:
                    # Check main forms
                    if self.are_terms_equivalent(entity1.id, entity2.id):
                        entities_to_merge[id2] = id1
                        continue
                
                    # Check variants
                    for variant1 in entity1.variants:
                        for variant2 in entity2.variants:
                            if self.are_terms_equivalent(variant1, variant2):
                                entities_to_merge[id2] = id1
                                break
                        if id2 in entities_to_merge:
                            break

        for entity_to_merge, target_id in entities_to_merge.items():
            if entity_to_merge in self.entities and target_id in self.entities:
                print(f"Merging entity '{entity_to_merge}' into '{target_id}'")
                self.entities[target_id].merge_from(self.entities[entity_to_merge])
                del self.entities[entity_to_merge]
    
        # Validate appearances
        for entity in self.entities.values():
            entity.validate_appearances()