"""
Recrawl Monitor Module

Monitors crawler execution and detects new URLs that should be ingested.
Compares crawled URLs against discovered set to find deltas.
"""

import logging
from typing import Set, Dict, Any
from .url_normalizer import normalize_batch
from .json_utils import load_json


logger = logging.getLogger(__name__)


class RecrawlMonitor:
    """
    Monitors crawler output and identifies new URLs.
    Coordinates between crawler and ingestion pipeline.
    """
    
    def __init__(self, discovered_path: str):
        """
        Initialize recrawl monitor.
        
        Args:
            discovered_path: Path to discovered_urls.json
        """
        self.discovered_path = discovered_path
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
    
    def run_crawler(self) -> Set[str]:
        """
        Execute the crawler and get URLs it discovered.
        
        Returns:
            Set of normalized URLs from crawler
        
        Raises:
            ImportError: If crawler cannot be imported
            Exception: If crawler execution fails
        """
        try:
            from crawler.bfs_crawler import bfs_crawl
        except ImportError as e:
            self.logger.error(f"Cannot import crawler: {str(e)}")
            raise
        
        self.logger.info("Running crawler...")
        
        try:
            # Execute crawler
            crawled_urls = bfs_crawl()
            
            # Extract URLs from crawler output (list of dicts or strings)
            urls = []
            for item in crawled_urls:
                if isinstance(item, dict) and 'url' in item:
                    urls.append(item['url'])
                elif isinstance(item, str):
                    urls.append(item)
            
            # Normalize URLs
            result = normalize_batch(urls)
            
            self.logger.info(
                f"[OK] Crawler completed: {len(crawled_urls)} URLs found "
                f"({result['valid_count']} valid, {result['invalid_count']} invalid)"
            )
            
            if result['invalid_count'] > 0:
                self.logger.warning(
                    f"Skipping {result['invalid_count']} invalid URLs from crawler"
                )
            
            return result['valid']
        
        except Exception as e:
            self.logger.error(f"[ERR] Crawler failed: {str(e)}")
            raise
    
    def compute_new_urls(self, crawled_urls: Set[str]) -> Dict[str, Any]:
        """
        Compute new URLs (crawled - discovered).
        
        Args:
            crawled_urls: Set of URLs from crawler
        
        Returns:
            Dictionary with:
            - 'new': set of new URL strings
            - 'crawled_count': total crawled
            - 'discovered_count': total discovered
            - 'new_count': count of new
            - 'saturation': percentage of overlap (discovered / crawled * 100)
        """
        try:
            discovered = self.load_discovered()
            
            new_urls = crawled_urls - discovered
            
            saturation = (len(discovered) / len(crawled_urls) * 100) if crawled_urls else 0
            
            result = {
                'new': new_urls,
                'crawled_count': len(crawled_urls),
                'discovered_count': len(discovered),
                'new_count': len(new_urls),
                'saturation': saturation
            }
            
            self.logger.info(
                f"New URL Analysis: "
                f"{result['crawled_count']} crawled, "
                f"{result['discovered_count']} discovered, "
                f"{result['new_count']} new "
                f"(Saturation: {saturation:.2f}%)"
            )
            
            return result
        
        except Exception as e:
            self.logger.error(f"Failed to compute new URLs: {str(e)}")
            raise
    
    def get_new_urls(self, crawled_urls: Set[str]) -> Set[str]:
        """
        Get new URLs as a set.
        
        Args:
            crawled_urls: Set of URLs from crawler
        
        Returns:
            Set of new URL strings
        """
        result = self.compute_new_urls(crawled_urls)
        return result['new']
    
    def get_new_urls_list(self, crawled_urls: Set[str]) -> list:
        """
        Get new URLs as a list.
        
        Args:
            crawled_urls: Set of URLs from crawler
        
        Returns:
            List of new URL strings
        """
        return list(self.get_new_urls(crawled_urls))
    
    def validate_crawler_output(self, crawled_urls: Set[str]) -> Dict[str, Any]:
        """
        Validate crawler output quality.
        
        Checks for:
        - Empty result
        - Very large result (possible crawler error)
        - Duplicate URLs
        
        Returns:
            Dictionary with validation results
        """
        validation = {
            'url_count': len(crawled_urls),
            'is_empty': len(crawled_urls) == 0,
            'is_valid': True,
            'warnings': []
        }
        
        if validation['is_empty']:
            validation['is_valid'] = False
            validation['warnings'].append("Crawler returned empty result")
        
        if len(crawled_urls) > 100000:
            validation['warnings'].append(
                f"Crawler returned unusually large result: {len(crawled_urls)} URLs"
            )
        
        if validation['warnings']:
            for warning in validation['warnings']:
                self.logger.warning(f"  ⚠️  {warning}")
        
        return validation
