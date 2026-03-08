"""
Pipeline 1: Missing URL Ingestion - Main Entry Point

This pipeline ingests all URLs that were discovered but never successfully ingested.
It runs completely independently from the incremental recrawl pipeline.

Usage:
    python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py

This WILL:
    ✓ Read discovered_urls.json and ingested_urls.json
    ✓ Compute missing URLs (discovered - ingested)
    ✓ Call ingestion pipeline for missing URLs only
    ✓ Update ingested_urls.json with newly ingested URLs
    ✓ Log statistics to console and file

This WILL NOT:
    ✗ Run the crawler
    ✗ Trigger incremental recrawl logic
    ✗ Modify discovered_urls.json
    ✗ Modify FAISS index directly
"""

import sys
import os
from pathlib import Path
from typing import Set, List, Dict, Any
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipelines.url_governor.missing_url_ingestion.logger_config import setup_logger, get_logger
from pipelines.url_governor.missing_url_ingestion.missing_checker import MissingUrlChecker
from pipelines.url_governor.missing_url_ingestion.json_utils import append_to_json_list, load_json

# Initialize logger
logger = setup_logger("missing_ingestion")


class MissingUrlIngestionPipeline:
    """
    Pipeline for ingesting missing URLs.
    
    Workflow:
    1. Load discovered and ingested URLs
    2. Compute missing URLs
    3. Batch ingestion
    4. Update ingested_urls.json
    5. Log results
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
        
        self.logger = get_logger("missing_ingestion")
        self.stats = {
            'start_time': None,
            'end_time': None,
            'discovered_count': 0,
            'ingested_before': 0,
            'missing_count': 0,
            'ingested_successful': 0,
            'ingestion_failed': [],
            'coverage_before': 0,
            'coverage_after': 0
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
            from pipelines.url_governor.missing_url_ingestion.json_utils import save_json_atomic
            save_json_atomic(str(self.ingested_path), [])
        
        # Check ingestion module
        try:
            from ingestion.ingest_pipeline import ingest_items
            self.logger.debug("ingestion.ingest_pipeline module available")
        except ImportError as e:
            raise ImportError(f"Cannot import ingestion pipeline: {str(e)}")
        
        self.logger.info("[OK] Environment validation passed")
        return True
    
    def compute_missing_urls(self) -> Set[str]:
        """
        Compute missing URLs using MissingUrlChecker.
        
        Returns:
            Set of missing URLs
        """
        self.logger.info("Computing missing URLs...")
        
        checker = MissingUrlChecker(
            str(self.discovered_path),
            str(self.ingested_path)
        )

        # compute normalized missing set (used for ingestion)
        result = checker.compute_missing()

        # also collect raw + normalized validation state for clearer reporting
        validation = checker.validate_state()

        # Stats: normalized counts used for set math, but surface raw counts too
        self.stats['discovered_count'] = validation['discovered_normalized']
        self.stats['discovered_raw'] = validation['discovered_count']
        self.stats['ingested_before'] = validation['ingested_normalized']
        self.stats['ingested_raw'] = validation['ingested_count']
        self.stats['missing_count'] = result['missing_count']
        self.stats['coverage_before'] = result['coverage']

        self.logger.info(
            f"[OK] Missing URLs computed: {len(result['missing'])} URLs "
            f"(discovered raw: {validation['discovered_count']}, "
            f"discovered normalized: {validation['discovered_normalized']}; "
            f"ingested raw: {validation['ingested_count']}, "
            f"ingested normalized: {validation['ingested_normalized']})"
        )

        return result['missing']
    
    def ingest_missing_urls(self, missing_urls: Set[str], batch_size: int = 500) -> Dict[str, Any]:
        """
        Ingest missing URLs through existing ingestion pipeline.
        
        Args:
            missing_urls: Set of URLs to ingest
            batch_size: How many URLs to send to ingestion per batch
        
        Returns:
            Dictionary with ingestion results
        """
        if not missing_urls:
            self.logger.info("No missing URLs to ingest")
            return {'successful': 0, 'failed': 0, 'newly_ingested_urls': []}
        
        try:
            from ingestion.ingest_pipeline import ingest_items
        except ImportError as e:
            self.logger.error(f"Cannot import ingestion pipeline: {str(e)}")
            raise
        
        # Convert to list of items (format expected by ingest_items)
        missing_list = list(missing_urls)
        total = len(missing_list)
        
        self.logger.info(f"Starting ingestion: {total} URLs")
        
        # Format URLs as items expected by ingest_items
        items = [
            {
                "url": url,
                "type": self._detect_url_type(url)
            }
            for url in missing_list
        ]
        
        successful = 0
        failed = 0
        newly_ingested_urls = []
        
        try:
            # Call existing ingestion pipeline
            self.logger.info(f"Calling ingestion pipeline for {len(items)} URLs...")
            newly_ingested_urls = ingest_items(items)  # Returns list of newly ingested URLs
            
            # newly_ingested_urls is a list of URL strings that were successfully ingested
            successful = len(newly_ingested_urls)
            failed = total - successful
            
            self.logger.info(
                f"[OK] Ingestion complete: {successful} URLs newly ingested"
            )
        
        except Exception as e:
            self.logger.error(f"Ingestion failed: {str(e)}")
            failed = total
            newly_ingested_urls = []
            successful = 0
        
        self.stats['ingested_successful'] = successful
        self.stats['ingestion_failed'] = failed
        
        return {
            'successful': successful,
            'failed': failed,
            'newly_ingested_urls': newly_ingested_urls
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
            self.stats['coverage_after'] = (new_count / self.stats['discovered_count'] * 100)
        
        except Exception as e:
            self.logger.error(f"[ERR] Failed to update ingested_urls.json: {str(e)}")
            raise
    
    def run(self) -> Dict[str, Any]:
        """
        Execute complete missing URL ingestion pipeline.
        
        Returns:
            Dictionary with pipeline execution results
        """
        import time
        self.stats['start_time'] = time.time()
        
        try:
            self.logger.info("=" * 70)
            self.logger.info("MISSING URL INGESTION PIPELINE - STARTING")
            self.logger.info("=" * 70)
            
            # Step 1: Validate environment
            self.validate_environment()
            
            # Step 2: Compute missing URLs
            missing_urls = self.compute_missing_urls()
            
            if not missing_urls:
                self.logger.info("[OK] No missing URLs - pipeline complete")
                self.stats['end_time'] = time.time()
                return self._format_results(success=True)
            
            # Step 3: Ingest missing URLs
            ingestion_result = self.ingest_missing_urls(missing_urls)
            
            # Step 4: Update ingested_urls.json with actually ingested URLs
            if ingestion_result['successful'] > 0 and ingestion_result['newly_ingested_urls']:
                # Only append URLs that were actually newly ingested
                self.update_ingested_urls(ingestion_result['newly_ingested_urls'])
            elif ingestion_result['successful'] == 0:
                self.logger.warning("[WARN] No URLs were successfully ingested")
            
            self.stats['end_time'] = time.time()
            
            self.logger.info("=" * 70)
            self.logger.info("[OK] MISSING URL INGESTION PIPELINE - COMPLETED SUCCESSFULLY")
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
                'discovered_total': self.stats['discovered_count'],
                'ingested_before': self.stats['ingested_before'],
                'missing': self.stats['missing_count'],
                'newly_ingested': self.stats['ingested_successful'],
                'failed': len(self.stats['ingestion_failed']),
                'coverage_before': f"{self.stats['coverage_before']:.2f}%",
                'coverage_after': f"{self.stats['coverage_after']:.2f}%"
            }
        }
        
        return results


def main():
    """
    Main entry point for missing URL ingestion pipeline.
    """
    try:
        # Initialize pipeline
        pipeline = MissingUrlIngestionPipeline()
        
        # Run pipeline
        results = pipeline.run()
        
        # Log final statistics
        logger = get_logger("missing_ingestion")
        logger.info(f"\nFinal Statistics:")
        logger.info(f"  Discovered URLs: {results['statistics']['discovered_total']}")
        logger.info(f"  Previously Ingested: {results['statistics']['ingested_before']}")
        logger.info(f"  Missing URLs: {results['statistics']['missing']}")
        logger.info(f"  Newly Ingested: {results['statistics']['newly_ingested']}")
        logger.info(f"  Failed: {results['statistics']['failed']}")
        logger.info(f"  Coverage Before: {results['statistics']['coverage_before']}")
        logger.info(f"  Coverage After: {results['statistics']['coverage_after']}")
        logger.info(f"  Duration: {results['duration_minutes']} minutes")
        
        # Exit with appropriate code
        sys.exit(0 if results['success'] else 1)
    
    except Exception as e:
        logger = get_logger("missing_ingestion")
        logger.error(f"FATAL ERROR: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
