#!/usr/bin/env python
"""Restore index.faiss from backup"""
import sys
sys.path.insert(0, '.')
from vectordb.vectordb_manager import VectorDBManager

print("📦 Restoring FAISS index from backup...")
try:
    vdb = VectorDBManager()
    if vdb.db:
        print(f"✅ FAISS index loaded: {vdb.db.index.ntotal} vectors")
        # Save to create proper files
        vdb.db.save_local("data/faiss_index")
        print("✅ FAISS index restored and saved")
    else:
        print("❌ Failed to load FAISS index")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
