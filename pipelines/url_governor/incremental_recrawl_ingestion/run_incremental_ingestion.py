"""
Pipeline 2: Incremental Recrawl + New URL Ingestion - Main Entry Point

This pipeline continuously crawls for new URLs, then ingests them.
It runs completely independently from the missing URL ingestion pipeline.

Usage:
    python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py

This WILL:
    ✓ Run the crawler (from crawler.bfs_crawler)
    ✓ Compute new URLs (crawled - discovered)
    ✓ Append new URLs to discovered_urls.json
    ✓ Call ingestion pipeline for new URLs only
    ✓ Update ingested_urls.json with newly ingested URLs
    ✓ Log statistics to console and file

This WILL NOT:
    ✗ Check for missing URLs
    ✗ Trigger missing URL ingestion logic
    ✗ Modify FAISS index directly
    ✗ Modify any existing pipeline code
"""

import sys
import os
from pathlib import Path
from typing import Set, List, Dict, Any
import logging
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipelines.url_governor.incremental_recrawl_ingestion.logger_config import setup_logger, get_logger
from pipelines.url_governor.incremental_recrawl_ingestion.recrawl_monitor import RecrawlMonitor
from pipelines.url_governor.incremental_recrawl_ingestion.json_utils import (
    append_to_json_list, load_json, save_json_atomic
)

# Initialize logger
logger = setup_logger("incremental_ingestion")


class IncrementalRecrawlIngestionPipeline:
    """
    Pipeline for incremental crawl and new URL ingestion.
    
    Workflow:
    1. Run crawler
    2. Compute new URLs
    3. Update discovered_urls.json
    4. Batch ingest new URLs
    5. Update ingested_urls.json
    6. Log results
    """
    
    def __init__(self, project_root: str = None):
        """
        Initialize pipeline.
        
        Args:
            project_root: Root directory of project (defaults to YCCE_RAG)
        """
        if project_root is None:
            # Find project root (should be YCCE_RAG)
            project_root = Path(__file__).parent.parent.parent.parent
        else:
            project_root = Path(project_root)
        
        self.project_root = project_root
        self.data_dir = project_root / "data"
        self.discovered_path = self.data_dir / "discovered_urls.json"
        self.ingested_path = self.data_dir / "ingested_urls.json"
        
        self.logger = get_logger("incremental_ingestion")
        self.stats = {
            'start_time': None,
            'end_time': None,
            'crawled_count': 0,
            'discovered_before': 0,
            'discovered_after': 0,
            'new_count': 0,
            'ingested_before': 0,
            'ingested_successful': 0,
            'ingestion_failed': [],
            'saturation': 0
        }
    
    def validate_environment(self) -> bool:
        """
        Validate that required files and paths exist.
        
        Returns:
            True if valid, raises exception otherwise
        """
        self.logger.info("Validating environment...")
        
        # Check data directory
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        
        # Check discovered_urls.json
        if not self.discovered_path.exists():
            raise FileNotFoundError(f"discovered_urls.json not found: {self.discovered_path}")
        
        # Check ingested_urls.json
        if not self.ingested_path.exists():
            self.logger.warning(f"ingested_urls.json not found, will create: {self.ingested_path}")
            # Create empty list
            save_json_atomic(str(self.ingested_path), [])
        
        # Check crawler module
        try:
            from crawler.bfs_crawler import bfs_crawl
            self.logger.debug("crawler.bfs_crawler module available")
        except ImportError as e:
            raise ImportError(f"Cannot import crawler: {str(e)}")
        
        # Check ingestion module
        try:
            from ingestion.ingest_pipeline import ingest_items
            self.logger.debug("ingestion.ingest_pipeline module available")
        except ImportError as e:
            raise ImportError(f"Cannot import ingestion pipeline: {str(e)}")
        
        self.logger.info("[OK] Environment validation passed")
        return True
    
    def run_crawler_and_detect_new(self) -> Set[str]:
        """
        Run crawler and detect new URLs.
        
        Returns:
            Set of new URLs found
        """
        self.logger.info("Starting crawler and new URL detection...")
        
        monitor = RecrawlMonitor(str(self.discovered_path))
        
        # Run crawler
        crawled_urls = monitor.run_crawler()
        
        # Validate crawler output
        validation = monitor.validate_crawler_output(crawled_urls)
        
        if not validation['is_valid']:
            raise RuntimeError(f"Crawler validation failed: {validation['warnings']}")
        
        self.stats['crawled_count'] = len(crawled_urls)
        
        # Compute new URLs
        result = monitor.compute_new_urls(crawled_urls)
        
        self.stats['discovered_before'] = result['discovered_count']
        self.stats['new_count'] = result['new_count']
        self.stats['saturation'] = result['saturation']
        
        self.logger.info(f"[OK] New URLs detected: {len(result['new'])} URLs")
        
        return result['new']
    
    def update_discovered_urls(self, new_urls: Set[str]) -> None:
        """
        Append new URLs to discovered_urls.json.
        
        Args:
            new_urls: Set of new URLs to append
        """
        if not new_urls:
            self.logger.info("No new URLs to append to discovered_urls.json")
            return
        
        self.logger.info(f"Updating discovered_urls.json with {len(new_urls)} new URLs...")
        
        try:
            # Get current count
            current_discovered = load_json(str(self.discovered_path))
            current_count = len(current_discovered)
            
            # Append new URLs as list
            append_to_json_list(str(self.discovered_path), list(new_urls))
            
            # Verify update
            updated_discovered = load_json(str(self.discovered_path))
            new_count = len(updated_discovered)
            
            self.logger.info(
                f"[OK] Updated discovered_urls.json: "
                f"{current_count} → {new_count} URLs "
                f"(added {new_count - current_count})"
            )
            
            self.stats['discovered_after'] = new_count
        
        except Exception as e:
            self.logger.error(f"[ERR] Failed to update discovered_urls.json: {str(e)}")
            raise
    
    def ingest_new_urls(self, new_urls: Set[str], batch_size: int = 500) -> Dict[str, Any]:
        """
        Ingest new URLs through existing ingestion pipeline.
        
        Args:
            new_urls: Set of URLs to ingest
            batch_size: How many URLs to send to ingestion per batch
        
        Returns:
            Dictionary with ingestion results
        """
        if not new_urls:
            self.logger.info("No new URLs to ingest")
            return {'successful': 0, 'failed': 0, 'failed_urls': []}
        
        try:
            from ingestion.ingest_pipeline import ingest_items
        except ImportError as e:
            self.logger.error(f"Cannot import ingestion pipeline: {str(e)}")
            raise
        
        # Convert to list of items (format expected by ingest_items)
        new_list = list(new_urls)
        total = len(new_list)
        
        self.logger.info(f"Starting ingestion: {total} URLs")
        
        # Format URLs as items expected by ingest_items
        items = [
            {
                "url": url,
                "type": self._detect_url_type(url)
            }
            for url in new_list
        ]
        
        successful = 0
        failed = 0
        failed_urls = []
        
        try:
            # Call existing ingestion pipeline
            # ingest_items handles batching internally
            self.logger.info(f"Calling ingestion pipeline for {len(items)} URLs...")
            ingest_items(items)
            
            # ingest_items manages its own counter tracking
            # We count as successful if it completed without exception
            successful = total
            
            self.logger.info(f"[OK] Ingestion complete: {successful} URLs processed")
        
        except Exception as e:
            self.logger.error(f"Ingestion failed: {str(e)}")
            failed = total
            failed_urls = new_list
        
        self.stats['ingested_successful'] = successful
        self.stats['ingestion_failed'] = failed_urls
        
        return {
            'successful': successful,
            'failed': failed,
            'failed_urls': failed_urls
        }
    
    def _detect_url_type(self, url: str) -> str:
        """
        Detect URL type based on file extension or content type.
        
        Args:
            url: URL string
        
        Returns:
            Type string: 'pdf', 'html', 'excel', etc.
        """
        url_lower = url.lower()
        
        if '.pdf' in url_lower:
            return 'pdf'
        elif '.xlsx' in url_lower or '.xls' in url_lower:
            return 'excel'
        elif '.docx' in url_lower or '.doc' in url_lower:
            return 'docx'
        else:
            return 'html'  # Default to HTML for web pages
    
    def update_ingested_urls(self, newly_ingested_urls: List[str]) -> None:
        """
        Update ingested_urls.json with newly ingested URLs.
        
        Args:
            newly_ingested_urls: List of URLs that were successfully ingested
        """
        if not newly_ingested_urls:
            self.logger.info("No new URLs to append to ingested_urls.json")
            return
        
        self.logger.info(f"Updating ingested_urls.json with {len(newly_ingested_urls)} new URLs...")
        
        try:
            # Get current ingested count for comparison
            current_ingested = load_json(str(self.ingested_path))
            current_count = len(current_ingested)
            
            # Append new URLs
            append_to_json_list(str(self.ingested_path), newly_ingested_urls)
            
            # Verify update
            updated_ingested = load_json(str(self.ingested_path))
            new_count = len(updated_ingested)
            
            self.logger.info(
                f"[OK] Updated ingested_urls.json: "
                f"{current_count} → {new_count} URLs "
                f"(added {new_count - current_count})"
            )
            
            self.stats['ingested_before'] = current_count
        
        except Exception as e:
            self.logger.error(f"[ERR] Failed to update ingested_urls.json: {str(e)}")
            raise
    
    def run(self) -> Dict[str, Any]:
        """
        Execute complete incremental recrawl and ingestion pipeline.
        
        Returns:
            Dictionary with pipeline execution results
        """
        self.stats['start_time'] = time.time()
        
        try:
            self.logger.info("=" * 70)
            self.logger.info("INCREMENTAL RECRAWL + INGESTION PIPELINE - STARTING")
            self.logger.info("=" * 70)
            
            # Step 1: Validate environment
            self.validate_environment()
            
            # Step 2: Run crawler and detect new URLs
            new_urls = self.run_crawler_and_detect_new()
            
            if not new_urls:
                self.logger.info("[OK] No new URLs found - pipeline complete")
                self.stats['end_time'] = time.time()
                self.stats['discovered_after'] = self.stats['discovered_before']
                return self._format_results(success=True)
            
            # Step 3: Update discovered_urls.json
            self.update_discovered_urls(new_urls)
            
            # Step 4: Ingest new URLs
            ingestion_result = self.ingest_new_urls(new_urls)
            
            # Step 5: Update ingested_urls.json
            if ingestion_result['successful'] > 0:
                # Get list of successfully ingested (first N items from batch)
                successfully_ingested = list(new_urls)[:ingestion_result['successful']]
                self.update_ingested_urls(successfully_ingested)
            
            self.stats['end_time'] = time.time()
            
            self.logger.info("=" * 70)
            self.logger.info("[OK] INCREMENTAL RECRAWL + INGESTION PIPELINE - COMPLETED SUCCESSFULLY")
            self.logger.info("=" * 70)
            
            return self._format_results(success=True)
        
        except Exception as e:
            self.logger.error("=" * 70)
            self.logger.error(f"[ERR] PIPELINE FAILED: {str(e)}")
            self.logger.error("=" * 70)
            self.stats['end_time'] = time.time()
            return self._format_results(success=False, error=str(e))
    
    def _format_results(self, success: bool, error: str = None) -> Dict[str, Any]:
        """
        Format pipeline execution results.
        
        Args:
            success: Whether pipeline succeeded
            error: Error message if failed
        
        Returns:
            Formatted results dictionary
        """
        duration = self.stats['end_time'] - self.stats['start_time'] if self.stats['end_time'] else 0
        
        results = {
            'success': success,
            'error': error,
            'duration_seconds': duration,
            'duration_minutes': round(duration / 60, 2),
            'statistics': {
                'crawled_total': self.stats['crawled_count'],
                'discovered_before': self.stats['discovered_before'],
                'discovered_after': self.stats['discovered_after'],
                'new_found': self.stats['new_count'],
                'newly_ingested': self.stats['ingested_successful'],
                'failed': len(self.stats['ingestion_failed']),
                'saturation': f"{self.stats['saturation']:.2f}%",
                'ingested_before': self.stats['ingested_before']
            }
        }
        
        return results


def main():
    """
    Main entry point for incremental recrawl and ingestion pipeline.
    """
    try:
        # Initialize pipeline
        pipeline = IncrementalRecrawlIngestionPipeline()
        
        # Run pipeline
        results = pipeline.run()
        
        # Log final statistics
        logger = get_logger("incremental_ingestion")
        logger.info(f"\nFinal Statistics:")
        logger.info(f"  Crawled URLs: {results['statistics']['crawled_total']}")
        logger.info(f"  Discovered Before: {results['statistics']['discovered_before']}")
        logger.info(f"  Discovered After: {results['statistics']['discovered_after']}")
        logger.info(f"  New URLs Found: {results['statistics']['new_found']}")
        logger.info(f"  Newly Ingested: {results['statistics']['newly_ingested']}")
        logger.info(f"  Failed: {results['statistics']['failed']}")
        logger.info(f"  Saturation: {results['statistics']['saturation']}")
        logger.info(f"  Duration: {results['duration_minutes']} minutes")
        
        # Exit with appropriate code
        sys.exit(0 if results['success'] else 1)
    
    except Exception as e:
        logger = get_logger("incremental_ingestion")
        logger.error(f"FATAL ERROR: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
