from pathlib import Path
import pickle
import hashlib
import json
import time
import os
from typing import List, Dict


class CacheManager:
    def __init__(self, cache_dir="cache", version="5.0"):  # Added version parameter
        self.version = version
        self.base_cache_dir = Path(cache_dir)
        self.cache_dir = self.base_cache_dir / f"v{version}"  # Add version to path
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create versioned subdirectories
        self.entity_cache_dir = self.cache_dir / "entities"
        self.comparison_cache_dir = self.cache_dir / "comparisons"
        self.entity_cache_dir.mkdir(exist_ok=True)
        self.comparison_cache_dir.mkdir(exist_ok=True)

    def _get_cache_key(self, text):
        """Generate cache key for text."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _normalize_entity_list(self, entity_list: List[Dict]) -> List[Dict]:
        """Normalize entity list to ensure consistent cache keys."""
        return sorted([
            {
                "entity": str(item["entity"]).lower().strip(),
                "variants": sorted(str(v).lower().strip() for v in item.get("variants", []))
            }
            for item in entity_list
        ], key=lambda x: x["entity"])

    def _get_comparison_cache_key(self, list1: List[Dict], list2: List[Dict]) -> str:
        """Generate a unique cache key for a comparison of two entity lists."""
        normalized_list1 = self._normalize_entity_list(list1)
        normalized_list2 = self._normalize_entity_list(list2)

        combined = json.dumps([normalized_list1, normalized_list2], sort_keys=True)
        return hashlib.sha256(combined.encode()).hexdigest()

    def get_cached_entities(self, text):
        cache_key = self._get_cache_key(text)
        cache_file = self.entity_cache_dir / f"{cache_key}.pkl"

        if cache_file.exists():
            with cache_file.open('rb') as f:
                return pickle.load(f)
        return None

    def cache_entities(self, text, entities):
        cache_key = self._get_cache_key(text)
        cache_file = self.entity_cache_dir / f"{cache_key}.pkl"

        with cache_file.open('wb') as f:
            pickle.dump(entities, f)

    def get_cached_comparison(self, list1, list2):
        cache_key = self._get_comparison_cache_key(list1, list2)
        cache_file = self.comparison_cache_dir / f"{cache_key}.pkl"

        if cache_file.exists():
            with cache_file.open('rb') as f:
                return pickle.load(f)
        return None

    def cache_comparison(self, list1, list2, result):
        cache_key = self._get_comparison_cache_key(list1, list2)
        cache_file = self.comparison_cache_dir / f"{cache_key}.pkl"

        with cache_file.open('wb') as f:
            pickle.dump(result, f)

    def cleanup_old_cache(self, days=30):
        """Delete cache files older than specified days."""
        now = time.time()
        for cache_file in self.base_cache_dir.rglob("*.pkl"):
            if os.stat(cache_file).st_mtime < now - days * 86400:
                cache_file.unlink()

    def clear_current_cache(self):
        """Clear all cache files for current version."""
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.rglob("*.pkl"):
                cache_file.unlink()

    def list_cache_versions(self):
        """List all available cache versions."""
        versions = []
        if self.base_cache_dir.exists():
            for dir in self.base_cache_dir.iterdir():
                if dir.is_dir() and dir.name.startswith('v'):
                    versions.append(dir.name[1:])  # Remove 'v' prefix
        return sorted(versions)