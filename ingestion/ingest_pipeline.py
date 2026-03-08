import os
import json
import hashlib
import shutil

from loaders.loader_routers import route_loader
from vectordb.faiss_stores import upsert_documents
from langchain_text_splitters import RecursiveCharacterTextSplitter


INGEST_TRACK_FILE = "data/ingested_urls.json"
BATCH_SIZE = 50  # Upsert every N documents to avoid memory buildup
MIN_DISK_MB = 500 # Require at least 500 MB free


# -------------------------------------------------
# helpers
# -------------------------------------------------
def load_ingested_urls():
    """Return set of URLs already recorded in ingested_urls.json.

    If the file is missing, empty, or contains invalid JSON, we treat it as
    an empty set. This protects against the situation where the file was
    deleted/cleared but an empty placeholder remains (which previously
    raised a JSONDecodeError and crashed ingestion).
    """
    if os.path.exists(INGEST_TRACK_FILE):
        try:
            with open(INGEST_TRACK_FILE, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if not data:
                    return set()
                return set(json.loads(data))
        except Exception:
            print(f"[WARN] could not read {INGEST_TRACK_FILE}, resetting to empty set")
            return set()
    return set()


def save_ingested_urls(url_set):
    """Save ingested URLs to file (overwrites with complete set)"""
    os.makedirs("data", exist_ok=True)
    with open(INGEST_TRACK_FILE, "w", encoding="utf-8") as f:
        json.dump(list(url_set), f, indent=2)


def append_ingested_url(url):
    """Append a single URL to ingested_urls.json (one-by-one).

    This works even if the file is missing, empty, or contains invalid JSON by
    treating such cases as an empty list. Any failure to write is logged but
    does not interrupt ingestion.
    """
    os.makedirs("data", exist_ok=True)
    try:
        # Load current, tolerating empty or corrupted file
        if os.path.exists(INGEST_TRACK_FILE):
            try:
                with open(INGEST_TRACK_FILE, "r", encoding="utf-8") as f:
                    urls = json.load(f)
            except Exception:
                urls = []
        else:
            urls = []
        
        # Avoid duplicates
        if url not in urls:
            urls.append(url)
            
            # Save atomically
            with open(INGEST_TRACK_FILE, "w", encoding="utf-8") as f:
                json.dump(urls, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to append {url}: {e}")


def check_disk_space():
    """Check available disk space, return MB free."""
    try:
        stat = shutil.disk_usage("data" if os.path.exists("data") else ".")
        free_mb = stat.free / (1024 * 1024)
        return free_mb
    except Exception:
        return float('inf')  # If we can't check, assume plenty


def batch_upsert(chunks, batch_size=BATCH_SIZE):
    """Upsert chunks in batches to manage memory."""
    if not chunks:
        return
    
    print(f"[FAISS] Upserting {len(chunks)} chunks (batch size: {batch_size})...")
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        try:
            upsert_documents(batch)
            print(f"   [OK] Batch {i//batch_size + 1}: {len(batch)} chunks upserted")
        except Exception as e:
            if "No space left" in str(e) or "Errno 28" in str(e):
                print(f"   [WARN] Disk space error at batch {i//batch_size + 1}: {e}")
                free_mb = check_disk_space()
                print(f"   [INFO] Free disk space: {free_mb:.1f} MB")
                raise
            else:
                raise


# -------------------------------------------------
# MAIN INGESTION
# -------------------------------------------------
def ingest_items(items):
    print("[START] Starting ingestion...")
    
    # Capture original state at START (for tracking what's NEW)
    original_ingested = load_ingested_urls()
    
    # Check initial disk space
    free_mb = check_disk_space()
    print(f"[INFO] Available disk space: {free_mb:.1f} MB")
    if free_mb < MIN_DISK_MB:
        print(f"[WARN] WARNING: Low disk space ({free_mb:.1f} MB < {MIN_DISK_MB} MB threshold)")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )

    ingested_urls = load_ingested_urls()
    all_chunks = []
    new_count = 0
    skipped_count = 0
    failed_count = 0
    disk_full = False

    for item in items:
        url = item["url"]
        file_type = item["type"]

        # ✅ DUPLICATE PROTECTION
        if url in ingested_urls:
            print(f"[SKIP] Skipping already ingested: {url}")
            skipped_count += 1
            continue

        try:
            # Check disk space before each item
            free_mb = check_disk_space()
            if free_mb < MIN_DISK_MB:
                print(f"\n[CRIT] DISK SPACE CRITICAL: {free_mb:.1f} MB remaining")
                print(f"   Stopping ingestion to prevent corruption")
                disk_full = True
                break
            
            print(f"[LOAD] Loading: {url}")
            docs = route_loader(url, file_type)

            if not docs:
                # ✅ Mark as ingested even if empty (avoid reprocessing)
                ingested_urls.add(url)
                append_ingested_url(url)
                print(f"   [✓] Added to ingested_urls.json (no content)")
                continue

            chunks = splitter.split_documents(docs)

            for c in chunks:
                c.metadata["source_url"] = url
                c.metadata["file_type"] = file_type

                # optional strong dedup id
                content_hash = hashlib.md5(c.page_content.encode()).hexdigest()
                c.metadata["chunk_id"] = content_hash

            all_chunks.extend(chunks)

            # ✅ mark as ingested immediately (crash safe)
            ingested_urls.add(url)
            new_count += 1
            
            # ✅ APPEND URL ONE-BY-ONE to ingested_urls.json
            append_ingested_url(url)
            print(f"   [✓] Added to ingested_urls.json")

            # ✅ Batch upsert every N documents to manage memory
            if len(all_chunks) >= BATCH_SIZE:
                try:
                    batch_upsert(all_chunks, batch_size=BATCH_SIZE)
                    all_chunks = []  # Clear after upsert
                except Exception as e:
                    if "No space left" in str(e) or "Errno 28" in str(e):
                        print(f"\n[ERR] Disk full error during batch upsert: {e}")
                        disk_full = True
                        break
                    else:
                        raise
            
            # ✅ periodic save (important for heavy runs)
            if new_count % 20 == 0:
                save_ingested_urls(ingested_urls)

        except Exception as e:
            if "No space left" in str(e) or "Errno 28" in str(e):
                print(f"[ERR] Ingestion error at {url}: DISK FULL - {e}")
                free_mb = check_disk_space()
                print(f"   Free disk space: {free_mb:.1f} MB")
                disk_full = True
                failed_count += 1
                break  # Stop processing
            else:
                print(f"[ERR] Ingestion error at {url}: {e}")
                failed_count += 1
                continue

    # -------------------------------------------------
    # FINAL FAISS UPSERT
    # -------------------------------------------------
    if all_chunks:
        print(f"\n[FAISS] Final upsert: {len(all_chunks)} remaining chunks...")
        try:
            batch_upsert(all_chunks, batch_size=BATCH_SIZE)
        except Exception as e:
            if "No space left" in str(e) or "Errno 28" in str(e):
                print(f"[ERR] Disk full during final upsert: {e}")
                disk_full = True
            else:
                raise
    
    # ✅ Get list of newly ingested URLs (for pipeline to append to ingested_urls.json)
    # Track which URLs are actually new
    newly_ingested_urls = [url for url in ingested_urls if url not in original_ingested]
    
    save_ingested_urls(ingested_urls)
    
    print("\n[SUMMARY] Ingestion Summary")
    print(f"   [OK] Newly ingested URLs: {new_count}")
    print(f"   [SKIP] Skipped URLs: {skipped_count}")
    print(f"   [ERR] Failed/Errors: {failed_count}")
    
    if disk_full:
        free_mb = check_disk_space()
        print(f"\n[WARN] DISK SPACE ISSUE DETECTED:")
        print(f"   Current free space: {free_mb:.1f} MB")
        print(f"   Threshold: {MIN_DISK_MB} MB")
        print(f"   → Resume pipeline after freeing disk space")
        print(f"   → Run: python main_initial_crawl.py (will resume from checkpoint)")
    
    # Return the list of newly ingested URLs
    return newly_ingested_urls