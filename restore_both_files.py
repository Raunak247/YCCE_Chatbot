#!/usr/bin/env python
"""Restore both index.faiss and index.pkl from backup"""
import pickle
import faiss
from pathlib import Path

# Load the pickled FAISS database  
pkl_path = Path("data/faiss_index/index.pkl.bak")
print(f"Loading from {pkl_path}...")

try:
    with open(pkl_path, 'rb') as f:
        db = pickle.load(f)
    
    print(f"✅ Loaded FAISS database")
    print(f"   Type: {type(db)}")
    
    # Save to output directory
    out_dir = Path("data/faiss_index")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # For FAISS objects, save index using faiss module
    if hasattr(db, 'index'):
        faiss_index = db.index
        faiss.write_index(faiss_index, str(out_dir / "index.faiss"))
        print(f"✅ Saved index.faiss ({faiss_index.ntotal} vectors)")
    
    # Save metadata/embeddings using pickle
    with open(out_dir / "index.pkl", 'wb') as f:
        pickle.dump(db, f)
    print(f"✅ Saved index.pkl")
    
    print("\n✅ SUCCESS: index.faiss and index.pkl restored!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
