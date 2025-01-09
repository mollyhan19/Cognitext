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
    variants: Set[str] = field(default_factory=set)
    appearances: List[Dict] = field(default_factory=list)

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
        """Add a new appearance and ensure variant is from known variants."""
        variant = self.normalize_term(variant)

        # Only use variants that are registered or the main ID
        if variant != self.id and variant not in self.variants:
            print(f"Warning: Unregistered variant '{variant}' for {self.id}, defaulting to main form")
            variant = self.id  # Always default to main form if variant not recognized

        section = appearance.get("section", "")
        # Check if this exact variant already appears in this section
        existing_in_section = any(
            app.get("section") == section and
            app.get("variant") == variant
            for app in self.appearances
        )

        if not existing_in_section:
            appearance["variant"] = variant
            self.appearances.append(appearance)
            self.frequency += 1
            print(f"Added appearance for '{variant}' in section {section}")

    def merge_from(self, other: 'Entity'):
        """Merge another entity into this one"""
        # Merge variants
        self.variants.update(other.variants)
        # Add unique appearances
        for app in other.appearances:
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
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content

    def clean_markdown_json(json_str: str) -> str:
        """Clean JSON string from markdown formatting."""
        if json_str.startswith('```'):
            parts = json_str.split('```')
            if len(parts) >= 3:
                json_str = parts[1]
            else:
                json_str = parts[-1]

            if '\n' in json_str:
                json_str = json_str.split('\n', 1)[1]

        return json_str.replace('```', '').strip()

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
        Extract key concepts that are crucial for understanding the main ideas in this section using the following strict guidelines. Each concept should represent a distinct unit of knowledge or understanding.
        Section name: {section_name}

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
        
        
        1. CONCEPT IDENTIFICATION:
        - Extract only distinct, well-defined units of knowledge
        - Each concept should represent ONE specific concept, process, or entity
        - Split compound concepts if they represent separate important concepts

        2. Focus on: 
        - Foundational concepts that other ideas build upon
        - Core processes or mechanisms that explain how something works
        - Key principles or theories that frame the topic
        - Defining characteristics or properties that distinguish important elements
        - Consider how concepts in this section relate to the section topic: {section_name}
        
        3. VARIANT CONSOLIDATION:
        When matching concepts:
        - Combine variant lists only for true matches
        - Preserve the more common/standard form as primary
        - Remove duplicates and near-duplicates

        Output format:
        [
            {{
            "entity": "main_form",
            "variants": ["true conceptual variations only"],
            "context": "Why this concept is essential for understanding the topic",
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
            print(f"  [S{section_index}] Error extracting entities: {str(e)}")
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
            print("  Using memory cache for list comparison")
            return self.memory_cache[cache_key]

        # Check file cache
        cached_result = self.cache_manager.get_cached_comparison(list1, list2)
        if cached_result is not None:
            print("  Using file cache for list comparison")
            self.memory_cache[cache_key] = cached_result
            return cached_result

        print("  Making API call for list comparison")
        prompt = f"""
        Compare these two lists of concepts and identify which ones represent EXACTLY the same abstract idea or unit of knowledge.
        
        Guidelines for matching:
        - Match terms that refer to exactly the same concept even if worded differently
        - Common variations of the same term should be matched (e.g., hyphenated vs non-hyphenated)
        - Different languages or regional terms for the same concept should be matched
        
        Do NOT match concepts that:
        - Are merely related or connected (e.g., "tardigrade anatomy" ≠ "tardigrade")
        - Have a hierarchical relationship
        - Represent different aspects of the same topic
        
        Return a JSON dictionary mapping List 2 concepts to their EXACT matches in List 1.
        Only include pairs with complete conceptual equivalence.

        List 1:
        {json.dumps(list1, indent=2)}

        List 2:
        {json.dumps(list2, indent=2)}
        """

        try:
            response = self._cached_api_call(prompt)
            matches = json.loads(OptimizedEntityExtractor.clean_markdown_json(response))

            # Cache results
            self.memory_cache[cache_key] = matches
            self.cache_manager.cache_comparison(list1, list2, matches)

            return matches
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

            appearance = {
                "section": chunk.section_name,
                "heading_level": chunk.heading_level,
                "section_index": chunk.section_index
            }

            # For first section, initialize entities
            if not self.entities:
                for new_entity in new_entities:
                    entity_id = new_entity["entity"].lower()
                    entity = Entity(
                        id=entity_id,
                        variants={entity_id} | {v.lower() for v in new_entity["variants"]}
                    )
                    entity.add_appearance(appearance, entity_id)
                    self.entities[entity_id] = entity
                return

            # For subsequent sections, use LLM to compare with existing entities
            existing_entities = [
                {
                    "entity": ent.id,
                    "variants": list(ent.variants),
                    "context": "Previously identified concept"
                }
                for ent in self.entities.values()
            ]

            # Get semantic matches from LLM
            matches = self.compare_concept_lists(existing_entities, new_entities)

            for new_entity in new_entities:
                entity_id = self.normalize_term(new_entity["entity"])
                variants = {self.normalize_term(v) for v in new_entity["variants"]}
                variants.add(entity_id)  # Add main form as a variant

                # Enhanced matching logic
                matched_entity = None
                for existing_id, existing_entity in self.entities.items():
                    # Check main forms
                    if entity_id == existing_entity.id:
                        matched_entity = existing_entity
                        break
                    
                    # Check variants both ways
                    if (entity_id in existing_entity.variants or
                        any(v in existing_entity.variants for v in variants) or
                        existing_entity.id in variants):
                        matched_entity = existing_entity
                        break

                appearance = {
                    "section": chunk.section_name,
                    "heading_level": chunk.heading_level,
                    "section_index": chunk.section_index
                }

                if matched_entity:
                    # Update existing entity
                    matched_entity.variants.update(variants)
                    matched_entity.add_appearance(appearance, entity_id)
                    print(f"Updated entity: {matched_entity.id} with new variants")
                else:
                    # Create new entity
                    new_entity_obj = Entity(
                        id=entity_id,
                        variants=variants
                    )
                    new_entity_obj.add_appearance(appearance, entity_id)
                    self.entities[entity_id] = new_entity_obj
                    print(f"Created new entity: {entity_id}")

        except Exception as e:
            print(f"Error processing section {chunk.section_name}: {str(e)}")
            raise

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
            key=lambda x: x.frequency,  # Now using explicit frequency
            reverse=True
        )

        return [
            {
                "id": entity.id,
                "frequency": entity.frequency,
                "variants": list(entity.variants),
                "appearances": entity.appearances
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