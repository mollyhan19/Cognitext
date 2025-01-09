from dotenv import load_dotenv
import os
import json
from datetime import datetime
from entity_extraction import OptimizedEntityExtractor, TextChunk
from typing import Dict

def process_article_by_paragraphs(article_title: str, article_data: Dict, extractor: OptimizedEntityExtractor):
    """Process an article paragraph by paragraph with surrounding context."""
    print(f"\n{'=' * 50}")
    print(f"Processing article by paragraphs: {article_title}")
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

    # Reset entity tracking for new article
    extractor.reset_tracking()

    # Process sections
    for section_idx, section in enumerate(article_data["sections"], 1):
        for heading, content in section.items():
            print(f"\nProcessing section {section_idx}/{len(article_data['sections'])}: {heading}")

            # Process main text with context
            main_text = content["text"]
            for para_idx, paragraph in enumerate(main_text):
                if paragraph.strip():
                    print(f"  Processing paragraph {para_idx + 1}/{len(main_text)} in main section")

                    # Create paragraph chunk with context
                    para_chunk = TextChunk(
                        content=paragraph,
                        section_name=heading,
                        heading_level="main",
                        section_text=main_text,
                        section_index=section_idx,
                        # Previous context
                        overlap_prev={
                            "paragraph": main_text[para_idx - 1] if para_idx > 0 else None,
                            "section": heading
                        },
                        # Next context
                        overlap_next={
                            "paragraph": main_text[para_idx + 1] if para_idx < len(main_text) - 1 else None,
                            "section": heading
                        }
                    )
                    extractor.process_paragraph(para_chunk, processed_paragraphs + 1)
                    processed_paragraphs += 1

            # Process subheadings with context
            if content["subheadings"]:
                for subheading, subcontent in content["subheadings"].items():
                    print(f"    Processing subheading: {subheading}")
                    sub_text = subcontent.get("text", [])

                    for para_idx, paragraph in enumerate(sub_text):
                        if paragraph.strip():
                            # Create subheading paragraph chunk with context
                            para_chunk = TextChunk(
                                content=paragraph,
                                section_name=f"{heading} - {subheading}",
                                heading_level="sub",
                                section_text=sub_text,
                                section_index=section_idx,
                                # Previous context includes main section
                                overlap_prev={
                                    "paragraph": sub_text[para_idx - 1] if para_idx > 0 else main_text[-1],
                                    "section": heading,
                                    "subheading": subheading
                                },
                                # Next context
                                overlap_next={
                                    "paragraph": sub_text[para_idx + 1] if para_idx < len(sub_text) - 1 else None,
                                    "section": heading,
                                    "subheading": subheading
                                }
                            )
                            extractor.process_paragraph(para_chunk, processed_paragraphs + 1)
                            processed_paragraphs += 1

    print(f"\nExtracting and sorting entities for {article_title}...")
    sorted_entities = extractor.get_sorted_entities()

    return {
        "category": article_data["category"],
        "total_entities": len(sorted_entities),
        "entities": sorted_entities
    }

def process_article_by_sections(article_title: str, article_data: Dict, extractor) -> Dict:
    """Process article section by section."""
    print(f"\nProcessing article by sections: {article_title}")
    print(f"Category: {article_data['category']}")

    # Reset entity tracking for new article
    extractor.reset_tracking()

    sections = article_data["sections"]
    print(f"Total sections to process: {len(sections)}")

    try:
        # Process each section
        for section_idx, section in enumerate(sections):
            for heading, content in section.items():
                print(f"Processing section {section_idx + 1}: {heading}")

                # Create TextChunk for main section
                main_chunk = TextChunk(
                    content="\n".join(content["text"]),
                    section_name=heading,
                    heading_level="main",
                    section_text=content["text"],
                    section_index=section_idx,
                    overlap_prev={"section": sections[section_idx - 1]} if section_idx > 0 else None,
                    overlap_next={"section": sections[section_idx + 1]} if section_idx < len(sections) - 1 else None
                )

                extractor.process_section(main_chunk)

                # Process subheadings if they exist
                if content["subheadings"]:
                    for sub_idx, (subheading, subcontent) in enumerate(content["subheadings"].items()):
                        print(f"  Processing subsection: {subheading}")

                        sub_chunk = TextChunk(
                            content="\n".join(subcontent.get("text", [])),
                            section_name=f"{heading} - {subheading}",
                            heading_level="sub",
                            section_text=subcontent.get("text", []),
                            section_index=section_idx,
                            overlap_prev={"main_section": content["text"][-1]} if content["text"] else None,
                            overlap_next=None
                        )

                        extractor.process_section(sub_chunk)

            # Periodic cleanup based on cleanup_interval
            # The interval is set in the OptimizedEntityExtractor initialization
            if (section_idx + 1) % extractor.cleanup_interval == 0:
                print(f"\nPerforming periodic cleanup after section {section_idx + 1}...")
                extractor.cleanup_entities()

        # Final cleanup after all sections are processed
        print("\nPerforming final cleanup...")
        extractor.cleanup_entities()

        # Get sorted entities
        sorted_entities = extractor.get_sorted_entities()

        return {
            "category": article_data["category"],
            "total_entities": len(sorted_entities),
            "entities": sorted_entities
        }

    except Exception as e:
        print(f"Error processing article {article_title}: {str(e)}")
        return {
            "category": article_data["category"],
            "error": str(e)
        }

def save_and_summarize_results(results: Dict, output_path: str):
    """Save results to file and print summary."""
    print("\nSaving results to JSON file...")
    output = {
        "timestamp": datetime.now().isoformat(),
        "analysis_results": results
    }

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
            print("  Appears in:", ", ".join(
                f"{app.get('section', '')} {app.get('paragraph', '')}"
                for app in entity["appearances"]
            ))


def main(processing_mode='paragraph'):
    """
    Main function to process articles with context, either by paragraph or by section.
    Args:
        processing_mode: Either 'paragraph' or 'section'
    """

    print("Starting entity extraction process...")
    load_dotenv("/Users/mollyhan/PycharmProjects/Cognitext/.env")

    # Initialize extractor
    print("Loading OpenAI API key...")
    extractor = OptimizedEntityExtractor(os.getenv("OpenAI_API_KEY"), cache_version="8.0", cleanup_interval=3)

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
    articles_processed = 0

    analysis_metadata = {
        "processing_mode": processing_mode,
        "timestamp": datetime.now().isoformat(),
        "total_articles": len(data["articles"])
    }

    # Process each article
    for article_title, article_data in data["articles"].items():
        print(f"\n{'=' * 50}")
        print(f"Processing article: {article_title}")
        print(f"Mode: {processing_mode}-level processing")
        print(f"Category: {article_data['category']}")

    # Process each article
    for article_title, article_data in data["articles"].items():

        # Process based on mode
        if processing_mode == 'paragraph':
            article_results = process_article_by_paragraphs(article_title, article_data, extractor)
        else:
            article_results = process_article_by_sections(article_title, article_data, extractor)

        # Add contextual metadata
        article_results["processing_metadata"] = {
            "mode": processing_mode,
            "structure": {
                "total_sections": len(article_data["sections"]),
                "total_paragraphs": sum(
                    len(content["text"]) +
                    sum(len(subcontent.get("text", []))
                        for subcontent in content.get("subheadings", {}).values())
                    for section in article_data["sections"]
                    for content in section.values()
                ),
                "has_subheadings": any(
                    content.get("subheadings")
                    for section in article_data["sections"]
                    for content in section.values()
                )
            }
        }

        results[article_title] = article_results
        articles_processed += 1

    # Determine output path based on processing mode
    if processing_mode == 'paragraph':
        output_path = "/Users/mollyhan/PycharmProjects/Cognitext/data/entity_analysis_para_results.json"
    else:
        output_path = "/Users/mollyhan/PycharmProjects/Cognitext/data/entity_analysis_sec_results.json"

    # Save results with enhanced metadata
    print("\nSaving results to JSON file...")
    output = {
        "metadata": analysis_metadata,
        "analysis_results": results
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved successfully to {output_path}!")

    # Print enhanced summary
    print("\nFinal Analysis Summary:")
    print("=" * 50)
    print(f"Processing Mode: {processing_mode}")
    print(f"Total Articles Processed: {articles_processed}")

    for article_title, result in results.items():
        print(f"\n{article_title}:")
        print(f"Category: {result['category']}")
        if 'error' in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Total unique entities: {result.get('total_entities', 0)}")
            print("\nTop 5 most frequent entities:")
            for entity in result.get('entities', [])[:5]:
                print(f"\n- {entity['id']}")
                print(f"  Frequency: {entity['frequency']}")
                print(f"  Variants: {', '.join(entity['variants'])}")

            # Enhanced location reporting based on processing mode
            if processing_mode == 'paragraph':
                print("  Appears in paragraphs:", ", ".join(
                    f"P{app.get('paragraph', '')} (Section: {app.get('section', '')})"
                    for app in entity["appearances"]
                ))
            else:
                print("  Appears in sections:", ", ".join(
                    app["section"] for app in entity["appearances"]
                ))

    print("\nProcess completed successfully!")

if __name__ == "__main__":
    main(processing_mode='section')  # or 'paragraph'
