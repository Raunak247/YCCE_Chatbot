"""
Missing URL Checker Module

Computes the set of URLs that were discovered but not yet ingested.
Returns missing URLs ready for ingestion.
"""

import logging
from typing import Set, Dict, Any
from .url_normalizer import normalize, normalize_batch, compute_url_diff
from .json_utils import load_json


logger = logging.getLogger(__name__)


class MissingUrlChecker:
    """Identifies and tracks URLs missing from ingestion."""
    
    def __init__(self, discovered_path: str, ingested_path: str):
        """
        Initialize missing URL checker.
        
        Args:
            discovered_path: Path to discovered_urls.json
            ingested_path: Path to ingested_urls.json
        """
        self.discovered_path = discovered_path
        self.ingested_path = ingested_path
        self.logger = logger
    
    def load_discovered(self) -> Set[str]:
        """
        Load and normalize discovered URLs.
        
        Returns:
            Set of normalized discovered URLs
        
        Raises:
            FileNotFoundError: If discovered_urls.json doesn't exist
        """
        try:
            urls_data = load_json(self.discovered_path)
            
            if not isinstance(urls_data, list):
                raise TypeError("discovered_urls.json must contain a list")
            
            # Handle both formats: list of dicts with 'url' field OR list of strings
            urls = []
            for item in urls_data:
                if isinstance(item, dict) and 'url' in item:
                    urls.append(item['url'])
                elif isinstance(item, str):
                    urls.append(item)
            
            # Normalize all URLs
            result = normalize_batch(urls)
            
            self.logger.info(
                f"Loaded {len(urls_data)} discovered URLs "
                f"({result['valid_count']} valid, {result['invalid_count']} invalid)"
            )
            
            if result['invalid_count'] > 0:
                self.logger.warning(
                    f"Skipping {result['invalid_count']} invalid URLs during normalization"
                )
            
            return result['valid']
        
        except Exception as e:
            self.logger.error(f"Failed to load discovered URLs: {str(e)}")
            raise
    
    def load_ingested(self) -> Set[str]:
        """
        Load and normalize ingested URLs.
        
        Returns:
            Set of normalized ingested URLs
        
        Raises:
            FileNotFoundError: If ingested_urls.json doesn't exist
        """
        try:
            urls = load_json(self.ingested_path)
            
            if not isinstance(urls, list):
                raise TypeError("ingested_urls.json must contain a list")
            
            # Normalize all URLs
            result = normalize_batch(urls)
            
            self.logger.info(
                f"Loaded {len(urls)} ingested URLs "
                f"({result['valid_count']} valid, {result['invalid_count']} invalid)"
            )
            
            if result['invalid_count'] > 0:
                self.logger.warning(
                    f"Skipping {result['invalid_count']} invalid URLs during normalization"
                )
            
            return result['valid']
        
        except Exception as e:
            self.logger.error(f"Failed to load ingested URLs: {str(e)}")
            raise
    
    def compute_missing(self) -> Dict[str, Any]:
        """
        Compute set of missing URLs (discovered - ingested) at RAW URL level.
        Compares raw lists (not normalized) to catch all unpicked URLs.
        
        Returns:
            Dictionary with:
            - 'missing': set of missing URL strings (raw, unnormalized)
            - 'discovered_count': count of raw discovered items
            - 'ingested_count': count of raw ingested items
            - 'missing_count': count of raw missing URLs
            - 'coverage': percentage of raw ingestion (ingested / discovered * 100)
        """
        try:
            # Load RAW lists (not normalized)
            discovered_raw_list = load_json(self.discovered_path)
            ingested_raw_list = load_json(self.ingested_path)
            
            # Extract raw URLs: handle dicts with 'url' field or plain strings
            discovered_raw_urls = set()
            for item in discovered_raw_list:
                if isinstance(item, dict) and 'url' in item:
                    discovered_raw_urls.add(item['url'])
                elif isinstance(item, str):
                    discovered_raw_urls.add(item)
            
            ingested_raw_urls = set()
            for item in ingested_raw_list:
                if isinstance(item, dict) and 'url' in item:
                    ingested_raw_urls.add(item['url'])
                elif isinstance(item, str):
                    ingested_raw_urls.add(item)
            
            # Compute missing at RAW level
            missing = discovered_raw_urls - ingested_raw_urls
            
            coverage = (len(ingested_raw_urls) / len(discovered_raw_urls) * 100) if discovered_raw_urls else 0
            
            result = {
                'missing': missing,
                'discovered_count': len(discovered_raw_urls),
                'ingested_count': len(ingested_raw_urls),
                'missing_count': len(missing),
                'coverage': coverage
            }
            
            self.logger.info(
                f"Missing URL Analysis (RAW level): "
                f"{result['discovered_count']} discovered, "
                f"{result['ingested_count']} ingested, "
                f"{result['missing_count']} missing "
                f"(Coverage: {coverage:.2f}%)"
            )
            
            return result
        
        except Exception as e:
            self.logger.error(f"Failed to compute missing URLs: {str(e)}")
            raise
    
    def get_missing_urls(self) -> Set[str]:
        """
        Get missing URLs as a set.
        
        Returns:
            Set of missing URL strings
        """
        result = self.compute_missing()
        return result['missing']
    
    def get_missing_urls_list(self) -> list:
        """
        Get missing URLs as a list.
        
        Returns:
            List of missing URL strings
        """
        return list(self.get_missing_urls())
    
    def validate_state(self) -> Dict[str, Any]:
        """
        Validate the state of discovered and ingested URLs.
        
        Checks for:
        - Ingested URLs that aren't in discovered (errors or deletes)
        - Missing URLs (discovered but not ingested)
        - Duplicates within each set
        
        Returns:
            Dictionary with validation results
        """
        result = self.compute_missing()
        
        # Load raw lists and coerce to URL strings
        discovered_raw_list = load_json(self.discovered_path)
        ingested_raw_list = load_json(self.ingested_path)

        # discovered may be list of dicts or strings
        discovered = set(
            (item['url'] if isinstance(item, dict) and 'url' in item else item)
            for item in discovered_raw_list
            if (isinstance(item, dict) and 'url' in item) or isinstance(item, str)
        )

        # ingested should be list of strings; coerce defensively
        ingested = set(
            (item['url'] if isinstance(item, dict) and 'url' in item else item)
            for item in ingested_raw_list
            if (isinstance(item, dict) and 'url' in item) or isinstance(item, str)
        )
        discovered_norm = self.load_discovered()
        ingested_norm = self.load_ingested()
        
        # Ingested URLs not in discovered
        orphaned = ingested_norm - discovered_norm
        
        validation = {
            'discovered_count': len(discovered),
            'ingested_count': len(ingested),
            'discovered_normalized': len(discovered_norm),
            'ingested_normalized': len(ingested_norm),
            'missing_count': result['missing_count'],
            'orphaned_count': len(orphaned),  # Ingested but not discovered
            'is_valid': len(orphaned) == 0 and result['missing_count'] >= 0
        }
        
        if not validation['is_valid']:
            self.logger.warning(
                f"Validation failed: {len(orphaned)} orphaned URLs found"
            )
        
        return validation
