#!/usr/bin/env python
"""Test pipeline instantiation and validation"""

from pipelines.url_governor.missing_url_ingestion.run_missing_ingestion import MissingUrlIngestionPipeline

try:
    pipeline = MissingUrlIngestionPipeline()
    print("✓ Pipeline instantiated successfully")
    
    # Test validate_environment
    print("\nValidating environment...")
    pipeline.validate_environment()
    print("✓ Environment validation passed")
    
    # Test compute_missing_urls
    print("\nComputing missing URLs...")
    missing_urls = pipeline.compute_missing_urls()
    print(f"✓ Found {len(missing_urls)} missing URLs")
    
    if missing_urls:
        print(f"  Sample: {list(missing_urls)[:2]}")
    
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
