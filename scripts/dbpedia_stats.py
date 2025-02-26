import json

# Replace this with your actual JSON file or content
with open("/Users/mollyhan/PycharmProjects/Cognitext/data/relations/dbpedia_comparison_results.json", "r") as file:
    json_data = json.load(file)

# Short code to print sources and targets with both source_present and target_present as False
for item in json_data:
    for relation_validation in item.get("relations_validation", []):
        validation = relation_validation.get("validation", {})
        if not validation.get("source_present", True) and not validation.get("target_present", True):
            source = relation_validation["relation"].get("source", "Unknown Source")
            target = relation_validation["relation"].get("target", "Unknown Target")
            print(f"Source: {source}, Target: {target}")



"""
def aggregate_category_statistics(results: list) -> dict:
    # Aggregate statistics by category.
    category_stats = {}

    for article in results:
        category = article["category"]
        if category not in category_stats:
            category_stats[category] = {
                "articles": [],
                "total_relations": 0,
                "proximity_scores": {"score_1": 0, "score_0.5": 0, "score_0": 0},
                "evidence_present": {"true": 0, "false": 0},
                "source_present": {"true": 0, "false": 0},
                "target_present": {"true": 0, "false": 0},
                "coverage": {"found": 0, "total": 0}
            }

        # Add article info
        category_stats[category]["articles"].append({
            "title": article["article"],
            "statistics": article["statistics"]
        })

        # Aggregate statistics
        stats = article["statistics"]
        category_stats[category]["total_relations"] += stats["total_relations"]

        for score_type in ["score_1", "score_0.5", "score_0"]:
            category_stats[category]["proximity_scores"][score_type] += \
                stats["proximity_scores"][score_type]

        for presence_type in ["true", "false"]:
            category_stats[category]["evidence_present"][presence_type] += \
                stats["evidence_present"][presence_type]
            category_stats[category]["source_present"][presence_type] += \
                stats["source_present"][presence_type]
            category_stats[category]["target_present"][presence_type] += \
                stats["target_present"][presence_type]

        category_stats[category]["coverage"]["found"] += stats["coverage"]["found"]
        category_stats[category]["coverage"]["total"] += stats["coverage"]["total"]

    # Calculate percentages for each category
    for category in category_stats:
        total = category_stats[category]["coverage"]["total"]
        if total > 0:
            category_stats[category]["coverage"]["percentage"] = \
                round((category_stats[category]["coverage"]["found"] / total) * 100, 2)

    return category_stats


# Load validation results
with open('/Users/mollyhan/PycharmProjects/Cognitext/data/relations/dbpedia_comparison_results.json', 'r') as f:
    validation_results = json.load(f)

# Generate category statistics
category_statistics = aggregate_category_statistics(validation_results)

# Save category statistics
with open('/Users/mollyhan/PycharmProjects/Cognitext/data/relations/dbpedia_article_statistics.json', 'w', encoding='utf-8') as f:
    json.dump(category_statistics, f, indent=2, ensure_ascii=False)
"""
