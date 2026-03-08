"""
URL Normalization Module

Normalizes URLs for consistent comparison across pipelines.
Handles lowercase, trailing slash removal, fragment removal.
"""

from urllib.parse import urlparse, urlunparse


def normalize(url: str, remove_query_params: bool = False) -> str:
    """
    Normalize URL for comparison purposes.
    Never raises errors - always returns a best-effort normalized URL.
    
    Rules applied:
    1. Convert to lowercase
    2. Remove URL fragment (#section)
    3. Strip trailing slash
    4. Optional: remove query parameters
    5. Add http:// scheme if missing
    
    Args:
        url: URL string to normalize
        remove_query_params: If True, removes query string (?key=value)
    
    Returns:
        Normalized URL string (empty string if input is invalid)
    """
    if not url or not isinstance(url, str):
        return ""  # Return empty string instead of raising
    
    url = url.strip()
    if not url:
        return ""
    
    try:
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        
        # Parse URL
        parsed = urlparse(url)
        
        # If parsing failed (no netloc), return original
        if not parsed.netloc:
            return url
        
        # Lowercase scheme and netloc
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Remove query params if requested
        query = "" if remove_query_params else parsed.query.lower()
        
        # Reconstruct without fragment
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, ""))
        
        # Strip trailing slash
        normalized = normalized.rstrip('/')
        
        return normalized
    
    except Exception:
        # Return best-effort: lowercase, stripped
        return url.lower().strip()


def normalize_batch(urls: list, remove_query_params: bool = False) -> dict:
    """
    Normalize a batch of URLs efficiently.
    
    Args:
        urls: List of URL strings
        remove_query_params: If True, removes query strings
    
    Returns:
        Dictionary with:
        - 'valid': set of normalized URLs
        - 'invalid': list of URLs that failed normalization
    """
    valid = set()
    invalid = []
    
    for url in urls:
        normalized = normalize(url, remove_query_params)
        # Skip empty strings but don't count as invalid
        if normalized:
            valid.add(normalized)
        elif url and isinstance(url, str) and url.strip():
            # URL was provided but couldn't be normalized
            invalid.append(url)
    
    return {
        'valid': valid,
        'invalid': invalid,
        'valid_count': len(valid),
        'invalid_count': len(invalid)
    }


def compute_url_diff(set_a: set, set_b: set) -> dict:
    """
    Compute set differences efficiently for large URL collections.
    
    Args:
        set_a: First set of URLs
        set_b: Second set of URLs
    
    Returns:
        Dictionary with:
        - 'in_a_not_b': URLs in A but not in B
        - 'in_b_not_a': URLs in B but not in A
        - 'in_both': URLs in both
    """
    set_a_normalized = {normalize(url) for url in set_a if url}
    set_b_normalized = {normalize(url) for url in set_b if url}
    
    return {
        'in_a_not_b': set_a_normalized - set_b_normalized,
        'in_b_not_a': set_b_normalized - set_a_normalized,
        'in_both': set_a_normalized & set_b_normalized
    }
