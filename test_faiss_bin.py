import os
import numpy as np

# Test if faiss binary index is valid
faiss_path = r'e:\YCCE_RAG\data\faiss_index\index.faiss'
print(f'FAISS file exists: {os.path.exists(faiss_path)}')
print(f'FAISS file size: {os.path.getsize(faiss_path)} bytes')

# Try to load FAISS index
try:
    import faiss
    index = faiss.read_index(faiss_path)
    print(f'FAISS index loaded successfully!')
    print(f'Number of vectors: {index.ntotal}')
    print(f'Dimension: {index.d}')
    print('SUCCESS: FAISS binary index is valid!')
except Exception as e:
    print(f'ERROR loading FAISS: {e}')
