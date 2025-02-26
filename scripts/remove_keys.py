import json

file_path = '/Users/mollyhan/PycharmProjects/Cognitext/data/entity_analysis_paragraph_results_sample.json'

with open(file_path, 'r') as f:
    data = json.load(f)

def remove_keys(data):
    if isinstance(data, dict):
        # List of keys to remove
        keys_to_remove = ["appearances", "frequency", "section", "section_index", "evidence", "variant", "builds_on", "context", "variants", "section_count"]

        for key in list(data.keys()):
            if key in keys_to_remove:
                del data[key]
            else:
                remove_keys(data[key])
    elif isinstance(data, list):
        for item in data:
            remove_keys(item)


remove_keys(data)

with open("/Users/mollyhan/PycharmProjects/Cognitext/data/cleaned_entity_analysis_paragraph_results_sample.json", "w") as f:
    json.dump(data, f, indent=4)
