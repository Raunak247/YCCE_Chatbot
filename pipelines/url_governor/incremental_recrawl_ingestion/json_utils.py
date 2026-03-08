"""
JSON Utilities Module

Provides safe, atomic JSON reading and writing to prevent corruption.
Implements backup and rollback strategies.
"""

import json
import logging
from pathlib import Path
from typing import Any, List, Dict
import shutil
from datetime import datetime


logger = logging.getLogger(__name__)


def load_json(filepath: str) -> Any:
    """
    Safely load JSON file with error handling.
    
    Args:
        filepath: Path to JSON file
    
    Returns:
        Parsed JSON data (list or dict)
    
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If JSON is corrupted
        IOError: If file cannot be read
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"JSON file not found: {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.debug(f"Loaded JSON: {filepath} ({len(data)} items)")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON corrupted in {filepath}: {str(e)}")
        raise
    except IOError as e:
        logger.error(f"Cannot read {filepath}: {str(e)}")
        raise


def save_json_atomic(filepath: str, data: Any, create_backup: bool = True) -> None:
    """
    Safely save JSON using atomic write operations.
    
    Process:
    1. Create backup of existing file (if create_backup=True)
    2. Write to temporary file in same directory
    3. Verify temp file contains valid JSON
    4. Replace original file with temp file (atomic operation)
    
    Args:
        filepath: Path where JSON should be saved
        data: Data to serialize (list, dict, etc.)
        create_backup: If True, creates backup before overwriting
    
    Returns:
        None
    
    Raises:
        IOError: If write fails
        json.JSONDecodeError: If generated JSON is invalid
    """
    filepath = Path(filepath)
    temp_path = filepath.parent / f"{filepath.name}.tmp"
    backup_path = filepath.parent / f"{filepath.name}.backup"
    
    try:
        # Create backup if file exists and requested
        if create_backup and filepath.exists():
            try:
                shutil.copy2(filepath, backup_path)
                logger.debug(f"Created backup: {backup_path}")
            except Exception as e:
                logger.warning(f"Failed to create backup: {str(e)}")
        
        # Write to temporary file
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Written temp file: {temp_path}")
        
        # Verify temp file is valid JSON
        with open(temp_path, 'r', encoding='utf-8') as f:
            json.load(f)  # Will raise if invalid
        
        logger.debug(f"Verified temp file is valid JSON")
        
        # Replace original with temp file (atomic on most filesystems)
        # On Windows, this requires removing the old file first
        if filepath.exists():
            filepath.unlink()
        
        temp_path.rename(filepath)
        logger.debug(f"Atomically replaced: {filepath}")
        
        # Clean up backup if replacement succeeded
        if backup_path.exists() and create_backup:
            try:
                backup_path.unlink()
                logger.debug(f"Cleaned up backup")
            except Exception as e:
                logger.warning(f"Failed to remove backup: {str(e)}")
    
    except Exception as e:
        # Clean up temp file on any error
        if temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass
        
        logger.error(f"Failed to save JSON to {filepath}: {str(e)}")
        raise


def append_to_json_list(filepath: str, items: List[str]) -> None:
    """
    Safely append items to a JSON list file.
    
    Args:
        filepath: Path to JSON file containing list
        items: List of items to append
    
    Returns:
        None
    
    Raises:
        FileNotFoundError: If file doesn't exist
        TypeError: If file doesn't contain a list
    """
    filepath = Path(filepath)
    
    try:
        # Load existing data
        data = load_json(str(filepath))
        
        if not isinstance(data, list):
            raise TypeError(f"JSON file at {filepath} does not contain a list")
        
        # Add new items
        data.extend(items)
        
        # Save atomically
        save_json_atomic(str(filepath), data, create_backup=True)
        
        logger.info(f"Appended {len(items)} items to {filepath}")
    
    except Exception as e:
        logger.error(f"Failed to append to {filepath}: {str(e)}")
        raise


def merge_json_lists(filepath: str, new_items: List[str], deduplicate: bool = True) -> Dict[str, Any]:
    """
    Merge new items into JSON list with optional deduplication.
    
    Args:
        filepath: Path to JSON file
        new_items: New items to merge
        deduplicate: If True, removes duplicates using set operations
    
    Returns:
        Dictionary with:
        - 'total': Total items after merge
        - 'added': Number of new items
        - 'duplicates': Number of duplicates removed (if deduplicate=True)
    """
    filepath = Path(filepath)
    
    try:
        # Load existing
        existing = set(load_json(str(filepath)))
        new_set = set(new_items)
        
        if deduplicate:
            # Track duplicates
            duplicates = existing & new_set
            merged = existing | new_set
            result = {
                'total': len(merged),
                'added': len(new_set - existing),
                'duplicates': len(duplicates)
            }
        else:
            merged = existing | new_set
            result = {
                'total': len(merged),
                'added': len(new_set - existing),
                'duplicates': 0
            }
        
        # Save merged list
        save_json_atomic(str(filepath), list(merged), create_backup=True)
        
        logger.info(f"Merged {new_set} items: {result}")
        return result
    
    except Exception as e:
        logger.error(f"Failed to merge JSON lists: {str(e)}")
        raise


def create_json_backup(filepath: str, timestamp: bool = True) -> Path:
    """
    Create a timestamped backup of JSON file.
    
    Args:
        filepath: Path to JSON file
        timestamp: If True, includes timestamp in backup filename
    
    Returns:
        Path to backup file
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    if timestamp:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = filepath.parent / f"{filepath.stem}_{timestamp_str}.backup"
    else:
        backup_path = filepath.parent / f"{filepath.name}.backup"
    
    try:
        shutil.copy2(filepath, backup_path)
        logger.info(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup: {str(e)}")
        raise
