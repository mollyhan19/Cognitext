from dataclasses import dataclass, field
from typing import List, Dict, Set
from functools import lru_cache
import json
from openai import OpenAI
from cache_manager import CacheManager

@dataclass
class Entity:
    id: str
    variants: Set[str] = field(default_factory=set)
    appearances: List[Dict] = field(default_factory=list)

    @property
    def frequency(self) -> int:
        return len(self.appearances)

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
    def __init__(self, api_key: str, cache_version: str = "3.0"):  # Added cache_version parameter
        self.client = OpenAI(api_key=api_key)
        self.cache_manager = CacheManager(version=cache_version)
        self.memory_cache = {}
        self.entities = {}

    @lru_cache(maxsize=1000)
    def _cached_api_call(self, prompt: str) -> str:
        """Cache API calls in memory."""
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
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

    def extract_entities_from_section(self, section: TextChunk) -> List[Dict]:
        """Extract entities from a section with caching."""
        # Check memory cache
        if section.content in self.memory_cache:
            print(f"  [Section: {section.section_name}] Using memory cache for entity extraction")
            return self.memory_cache[section.content]

        # Check file cache
        cached_result = self.cache_manager.get_cached_entities(section.content)
        if cached_result is not None:
            print(f"  [Section: {section.section_name}] Using file cache for entity extraction")
            self.memory_cache[section.content] = cached_result
            return cached_result

        print(f"  [Section: {section.section_name}] Making API call for entity extraction")
        prompt = f"""
        Extract key concepts that are crucial for understanding the main ideas in this section. Each concept should represent a distinct unit of knowledge or understanding.
        Focus on: 
        1. Foundational concepts that other ideas build upon
        2. Core processes or mechanisms that explain how something works
        3. Key principles or theories that frame the topic
        4. Critical relationships between ideas
        5. Defining characteristics or properties that distinguish important elements

        Important guidelines: 
        - Properties/attributes of a concept should be separate concepts if they represent important distinct ideas. (e.g., "tardigrade nervous system" is different from "tardigrade") 
        - Different states/processes should be separate concepts when they represent distinct phenomena (e.g., "active tardigrades" vs "dormant tardigrades")
        - Consider how concepts in this section relate to the section heading: {section.section_name}
        - For subsections, consider how concepts relate to both the main section and subsection context

        Output format:
        [
            {{
            "entity": "main_form",
            "variants": ["true conceptual variations only"],
            "context": "Why this concept is essential for understanding the topic",
            "section_relevance": "How this concept relates to the section theme"
            }}
        ]

        Section heading: {section.section_name}
        Section level: {section.heading_level}
        Content:
        {section.content}
        """

        try:
            response = self._cached_api_call(prompt)
            entities = json.loads(OptimizedEntityExtractor.clean_markdown_json(response))

            # Cache results
            self.memory_cache[section.content] = entities
            self.cache_manager.cache_entities(section.content, entities)

            return entities
        except Exception as e:
            print(f"  [Section: {section.section_name}] Error extracting entities: {str(e)}")
            return []

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
        1. The concepts should teach the same core idea
        2. Understanding one should be equivalent to understanding the other
        3. They should operate at the same level of abstraction
        4. They should play the same role in building subject knowledge
        5. They should have the same relationship to other key concepts

        Do NOT match concepts that:
        - Are merely related or connected
        - Have a hierarchical relationship
        - Represent different aspects of the same topic
        - Operate at different levels of detail
        
        When in doubt about conceptual equivalence, DO NOT match
        Return a JSON dictionary where keys are concepts from List 2 and values are their matching entities from List 1. 
        Only include pairs that represent the exact same abstract idea or unit of knowledge.

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

    def process_paragraph(self, paragraph: str, para_num: int):
        """Process paragraph and update entity tracking."""
        new_entities = self.extract_entities_from_paragraph(paragraph, para_num)

        if not self.entities:  # First paragraph
            for new_entity in new_entities:
                entity_id = new_entity["entity"]
                self.entities[entity_id] = Entity(
                    id=entity_id,
                    variants={entity_id} | set(new_entity["variants"]),
                    appearances=[{"paragraph": para_num, "form": entity_id}]
                )
        else:
            existing_entities = [
                {"entity": ent.id, "variants": list(ent.variants)}
                for ent in self.entities.values()
            ]

            matches = self.compare_concept_lists(existing_entities, new_entities)

            for new_entity in new_entities:
                entity_id = new_entity["entity"]

                if entity_id in matches:
                    existing_id = matches[entity_id]
                    if existing_id is not None and existing_id in self.entities:
                        self.entities[existing_id].variants.add(entity_id)
                        self.entities[existing_id].variants.update(new_entity["variants"])
                        self.entities[existing_id].appearances.append({
                            "paragraph": para_num,
                            "form": entity_id
                        })
                    else:
                        self.entities[entity_id] = Entity(
                            id=entity_id,
                            variants={entity_id} | set(new_entity["variants"]),
                            appearances=[{"paragraph": para_num, "form": entity_id}]
                        )
                else:
                    self.entities[entity_id] = Entity(
                        id=entity_id,
                        variants={entity_id} | set(new_entity["variants"]),
                        appearances=[{"paragraph": para_num, "form": entity_id}]
                    )

    def process_section(self, section: TextChunk):
        """Process section and update entity tracking."""
        new_entities = self.extract_entities_from_section(section)

        if not self.entities:  # First section
            for new_entity in new_entities:
                entity_id = new_entity["entity"]
                self.entities[entity_id] = Entity(
                    id=entity_id,
                    variants={entity_id} | set(new_entity["variants"]),
                    appearances=[{"section": section.section_name, "form": entity_id}]
                )
        else:
            existing_entities = [
                {"entity": ent.id, "variants": list(ent.variants)}
                for ent in self.entities.values()
            ]

            matches = self.compare_concept_lists(existing_entities, new_entities)

            for new_entity in new_entities:
                entity_id = new_entity["entity"]

                if entity_id in matches:
                    existing_id = matches[entity_id]
                    if existing_id is not None and existing_id in self.entities:
                        self.entities[existing_id].variants.add(entity_id)
                        self.entities[existing_id].variants.update(new_entity["variants"])
                        self.entities[existing_id].appearances.append({
                            "section": section.section_name,
                            "form": entity_id
                        })
                else:
                    self.entities[entity_id] = Entity(
                        id=entity_id,
                        variants={entity_id} | set(new_entity["variants"]),
                        appearances=[{"section": section.section_name, "form": entity_id}]
                    )

    def get_sorted_entities(self) -> List[Dict]:
        """Return entities sorted by frequency."""
        sorted_entities = sorted(
            self.entities.values(),
            key=lambda x: x.frequency,
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

