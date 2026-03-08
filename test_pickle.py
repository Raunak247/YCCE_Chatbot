import pickle
import os

pkl_path = r'e:\YCCE_RAG\data\faiss_index\index.pkl'
print(f'File exists: {os.path.exists(pkl_path)}')
print(f'File size: {os.path.getsize(pkl_path)} bytes')

# Try to read the pickle
with open(pkl_path, 'rb') as f:
    data = pickle.load(f)
    print(f'Pickle loaded successfully!')
    print(f'Type: {type(data)}')
    if isinstance(data, dict):
        print(f'Keys: {list(data.keys())}')
    print('SUCCESS: FAISS pickle file is readable!')
