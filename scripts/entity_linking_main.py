from dotenv import load_dotenv
import os
import json
from datetime import datetime
from entity_extraction import OptimizedEntityExtractor
from entity_extraction import TextChunk

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

"""
paragraph-level processing 

def main():
    from dotenv import load_dotenv
    import os
    import json
    from datetime import datetime

    print("Starting entity extraction process...")
    load_dotenv("/Users/mollyhan/PycharmProjects/Cognitext/.env")

    # Initialize extractor
    print("Loading OpenAI API key...")
    extractor = OptimizedEntityExtractor(os.getenv("OpenAI_API_KEY"), cache_version="3.0")

    # Load JSON file
    print("Loading input JSON file...")
    try:
        with open("/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"Found {len(data['articles'])} articles to process")
    except FileNotFoundError:
        print("Input JSON file not found")
        return

    results = {}

    # Process each article
    for article_title, article_data in data["articles"].items():
        print(f"\n{'=' * 50}")
        print(f"Processing article: {article_title}")
        print(f"Category: {article_data['category']}")

        # Count total paragraphs
        total_paragraphs = sum(
            len(content["text"]) +
            sum(len(subcontent.get("text", []))
                for subcontent in content.get("subheadings", {}).values())
            for section in article_data["sections"]
            for content in section.values()
        )

        print(f"Total paragraphs to process: {total_paragraphs}")
        processed_paragraphs = 0

        # Process sections
        for section_idx, section in enumerate(article_data["sections"], 1):
            for heading, content in section.items():
                print(f"\nProcessing section {section_idx}/{len(article_data['sections'])}: {heading}")

                # Process main text
                for para_idx, paragraph in enumerate(content["text"], 1):
                    if paragraph.strip():
                        print(f"  Processing paragraph {para_idx}/{len(content['text'])} in main section")
                        extractor.process_paragraph(paragraph, processed_paragraphs + 1)
                        processed_paragraphs += 1

                # Process subheadings
                if content["subheadings"]:
                    print(f"  Processing {len(content['subheadings'])} subheadings...")
                    for subheading, subcontent in content["subheadings"].items():
                        print(f"    Processing subheading: {subheading}")
                        for para_idx, paragraph in enumerate(subcontent.get("text", []), 1):
                            if paragraph.strip():
                                print(f"      Processing paragraph {para_idx}/{len(subcontent['text'])}")
                                extractor.process_paragraph(paragraph, processed_paragraphs + 1)
                                processed_paragraphs += 1

        print(f"\nExtracting and sorting entities for {article_title}...")
        sorted_entities = extractor.get_sorted_entities()

        results[article_title] = {
            "category": article_data["category"],
            "total_entities": len(sorted_entities),
            "entities": sorted_entities
        }
        print(f"Found {len(sorted_entities)} unique entities")

    print("\nSaving results to JSON file...")
    output = {
        "timestamp": datetime.now().isoformat(),
        "analysis_results": results
    }

    with open("/Users/mollyhan/PycharmProjects/Cognitext/data/entity_analysis_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print("Results saved successfully!")

    # Print summary
    print("\nFinal Analysis Summary:")
    print("=" * 50)
    for article_title, result in results.items():
        print(f"\n{article_title}:")
        print(f"Category: {result['category']}")
        print(f"Total unique entities: {result['total_entities']}")
        print("\nTop 5 most frequent entities:")
        for entity in result['entities'][:5]:
            print(f"\n- {entity['id']}")
            print(f"  Frequency: {entity['frequency']}")
            print(f"  Variants: {', '.join(entity['variants'])}")

    print("\nProcess completed successfully!")
"""


def main():

    print("Starting entity extraction process...")
    load_dotenv("/Users/mollyhan/PycharmProjects/Cognitext/.env")

    # Initialize extractor
    print("Loading OpenAI API key...")
    extractor = OptimizedEntityExtractor(os.getenv("OpenAI_API_KEY"), cache_version="3.0")

    # Load JSON file
    print("Loading input JSON file...")
    try:
        with open("/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"Found {len(data['articles'])} articles to process")
    except FileNotFoundError:
        print("Input JSON file not found")
        return

    results = {}

    # Process each article
    for article_title, article_data in data["articles"].items():
        print(f"\n{'=' * 50}")
        print(f"Processing article: {article_title}")
        print(f"Category: {article_data['category']}")

        # Count total sections and subsections
        total_sections = 0
        for section in article_data["sections"]:
            total_sections += 1  # Count main section
            for content in section.values():
                total_sections += len(content.get("subheadings", {}))  # Count subsections

        print(f"Total sections to process: {total_sections}")
        processed_sections = 0

        # Process sections
        for section_idx, section in enumerate(article_data["sections"], 1):
            for heading, content in section.items():
                print(f"\nProcessing main section {section_idx}/{len(article_data['sections'])}: {heading}")

                # Create main section chunk
                if content["text"]:
                    section_chunk = TextChunk(
                        content="\n\n".join(content["text"]),
                        section_name=heading,
                        heading_level="main",
                        section_text=content["text"],
                        section_index=processed_sections,
                        overlap_prev={
                            "section": article_data["sections"][section_idx - 2] if section_idx > 1 else None
                        } if section_idx > 1 else None,
                        overlap_next={
                            "section": article_data["sections"][section_idx] if section_idx < len(
                                article_data["sections"]) else None
                        } if section_idx < len(article_data["sections"]) else None
                    )
                    extractor.process_section(section_chunk)
                    processed_sections += 1

                # Process subheadings
                if content["subheadings"]:
                    print(f"  Processing {len(content['subheadings'])} subheadings...")
                    for subheading, subcontent in content["subheadings"].items():
                        print(f"    Processing subheading: {subheading}")
                        if subcontent.get("text"):
                            sub_chunk = TextChunk(
                                content="\n\n".join(subcontent["text"]),
                                section_name=f"{heading} - {subheading}",
                                heading_level="sub",
                                section_text=subcontent["text"],
                                section_index=processed_sections,
                                overlap_prev={"main_section_text": content["text"]} if content["text"] else None,
                                overlap_next=None
                            )
                            extractor.process_section(sub_chunk)
                            processed_sections += 1

        print(f"\nExtracting and sorting entities for {article_title}...")
        sorted_entities = extractor.get_sorted_entities()

        results[article_title] = {
            "category": article_data["category"],
            "total_entities": len(sorted_entities),
            "entities": sorted_entities
        }
        print(f"Found {len(sorted_entities)} unique entities")

    print("\nSaving results to JSON file...")
    output = {
        "timestamp": datetime.now().isoformat(),
        "analysis_results": results
    }

    output_path = "/Users/mollyhan/PycharmProjects/Cognitext/data/entity_analysis_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print("Results saved successfully!")

    # Print summary
    print("\nFinal Analysis Summary:")
    print("=" * 50)
    for article_title, result in results.items():
        print(f"\n{article_title}:")
        print(f"Category: {result['category']}")
        print(f"Total unique entities: {result['total_entities']}")
        print("\nTop 5 most frequent entities:")
        for entity in result['entities'][:5]:
            print(f"\n- {entity['id']}")
            print(f"  Frequency: {entity['frequency']}")
            print(f"  Variants: {', '.join(entity['variants'])}")
            # Print section appearances instead of paragraph appearances
            print("  Appears in sections:", ", ".join(set(app["section"] for app in entity["appearances"])))

    print("\nProcess completed successfully!")

if __name__ == "__main__":
    main()