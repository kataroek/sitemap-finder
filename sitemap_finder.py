#!/usr/bin/env python3
"""
Sitemap Finder - A tool to discover sitemaps for a list of domains.
Supports standard and compressed sitemap formats.
"""

import argparse
import csv
import gzip
import io
import json
import re
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin

from tqdm import tqdm

import requests
from requests.exceptions import RequestException

# Common sitemap locations to check
SITEMAP_PATHS = [
    # Standard formats
    '/sitemap.xml',
    '/sitemap_index.xml',
    '/sitemap-index.xml',
    '/sitemapindex.xml',
    '/sitemap.php',
    '/sitemap.txt',
    '/sitemap.html',
    # Compressed formats
    '/sitemap.xml.gz',
    '/sitemap.gz',
    '/sitemap.xml.zip',
    '/sitemap.zip',
    '/sitemap_index.xml.gz',
    '/sitemap-index.xml.gz',
    '/sitemapindex.xml.gz',
    # More specific formats sometimes used
    '/news-sitemap.xml',
    '/news-sitemap.xml.gz',
    '/image-sitemap.xml',
    '/image-sitemap.xml.gz',
    '/video-sitemap.xml',
    '/video-sitemap.xml.gz',
    '/product-sitemap.xml',
    '/product-sitemap.xml.gz',
    '/page-sitemap.xml',
    '/post-sitemap.xml',
    '/category-sitemap.xml',
]

def setup_argparse() -> argparse.Namespace:
    """Set up command line arguments."""
    parser = argparse.ArgumentParser(description='Find sitemaps for a list of domains.')
    parser.add_argument('input_file', help='Text file containing domain names (one per line)')
    parser.add_argument('-o', '--output', help='Output file name (default: sitemaps_output)', default='sitemaps_output')
    parser.add_argument('-f', '--format', choices=['json', 'csv'], default='json', help='Output format (default: json)')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='Request timeout in seconds (default: 10)')
    parser.add_argument('-c', '--concurrency', type=int, default=5, help='Number of concurrent requests (default: 5)')
    return parser.parse_args()

def read_domains(file_path: str) -> List[str]:
    """Read domain names from a file, one per line."""
    try:
        with open(file_path, 'r') as f:
            # Strip whitespace and filter empty lines
            domains = [line.strip() for line in f if line.strip()]
        return domains
    except Exception as e:
        print(f"Error reading domains file: {e}", file=sys.stderr)
        sys.exit(1)

def normalize_domain(domain: str) -> List[str]:
    """Normalize domain name and return both HTTP and HTTPS versions."""
    # Strip any existing protocol
    if domain.startswith(('http://', 'https://')):
        # Extract the domain without protocol
        domain = re.sub(r'^https?://', '', domain)
    
    # Return both HTTP and HTTPS versions
    return [f"http://{domain}", f"https://{domain}"]

def extract_sitemaps_from_robots(robots_content: str) -> Set[str]:
    """Extract sitemap URLs from robots.txt content."""
    sitemap_urls = set()
    # Look for Sitemap: directives in robots.txt
    for line in robots_content.splitlines():
        if line.lower().startswith('sitemap:'):
            sitemap_url = line.split(':', 1)[1].strip()
            if sitemap_url:
                sitemap_urls.add(sitemap_url)
    return sitemap_urls

def is_compressed_format(url: str) -> bool:
    """Check if the URL points to a compressed format."""
    return url.endswith(('.gz', '.zip'))

def get_compression_type(url: str) -> str:
    """Get the compression type from the URL."""
    if url.endswith('.gz'):
        return 'gzip'
    elif url.endswith('.zip'):
        return 'zip'
    else:
        return 'none'

def extract_urls_from_compressed_sitemap(content: bytes, compression_type: str) -> Set[str]:
    """Extract sitemap URLs from compressed content."""
    sitemap_urls = set()
    
    try:
        if compression_type == 'gzip':
            # Decompress gzip content
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
                xml_content = f.read().decode('utf-8', errors='ignore')
        elif compression_type == 'zip':
            # Extract first file from zip archive
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                # Get the first file in the archive
                first_file = z.namelist()[0]
                xml_content = z.read(first_file).decode('utf-8', errors='ignore')
        else:
            return sitemap_urls
        
        # Simple regex to find sitemap URLs
        # This is a basic approach - a proper XML parser would be more robust
        # but this handles most common sitemap formats
        urls = re.findall(r'<loc>([^<]+)</loc>', xml_content)
        sitemap_urls.update(urls)
        
    except Exception as e:
        print(f"Error extracting URLs from compressed sitemap: {e}", file=sys.stderr)
    
    return sitemap_urls

def check_robots_txt(base_url: str, timeout: int) -> Set[str]:
    """Check robots.txt for sitemap directives."""
    sitemap_urls = set()
    try:
        robots_url = urljoin(base_url, '/robots.txt')
        response = requests.get(robots_url, timeout=timeout, headers={'User-Agent': 'SitemapFinder/1.0'})
        if response.status_code == 200:
            sitemap_urls = extract_sitemaps_from_robots(response.text)
    except RequestException:
        pass
    return sitemap_urls

def check_common_locations(base_url: str, timeout: int) -> Tuple[Set[str], Set[str]]:
    """Check common sitemap locations."""
    sitemap_urls = set()
    compressed_sitemaps = set()
    
    for path in SITEMAP_PATHS:
        try:
            sitemap_url = urljoin(base_url, path)
            response = requests.head(sitemap_url, timeout=timeout, headers={'User-Agent': 'SitemapFinder/1.0'})
            
            if response.status_code == 200:
                sitemap_urls.add(sitemap_url)
                if is_compressed_format(sitemap_url):
                    compressed_sitemaps.add(sitemap_url)
        except RequestException:
            continue
    
    return sitemap_urls, compressed_sitemaps

def fetch_compressed_sitemaps(compressed_sitemaps: Set[str], timeout: int) -> Set[str]:
    """Fetch and extract URLs from compressed sitemaps."""
    all_urls = set()
    
    # Create a simplified progress bar for compressed sitemaps
    if compressed_sitemaps:
        print(f"\nProcessing {len(compressed_sitemaps)} compressed sitemaps...")
        compressed_progress = tqdm(
            total=len(compressed_sitemaps),
            desc="Extracting URLs",
            unit="file",
            leave=False,
            ncols=80,
            bar_format="{desc}: {percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt}"
        )
    
    for url in compressed_sitemaps:
        try:
            compression_type = get_compression_type(url)
            response = requests.get(url, timeout=timeout)
            
            if response.status_code == 200:
                urls = extract_urls_from_compressed_sitemap(response.content, compression_type)
                all_urls.update(urls)
                
                # Don't show postfix for each compressed sitemap to reduce clutter
        except Exception as e:
            print(f"Error fetching compressed sitemap {url}: {e}", file=sys.stderr)
        
        # Update progress bar
        if compressed_sitemaps:
            compressed_progress.update(1)
    
    # Close progress bar
    if compressed_sitemaps:
        compressed_progress.close()
    
    return all_urls

def find_sitemaps_for_domain(domain: str, timeout: int) -> Dict:
    """Find all sitemaps for a domain using both HTTP and HTTPS protocols."""
    result = {
        'domain': domain,
        'sitemaps': [],
        'nested_urls': [],  # URLs found inside compressed sitemaps
        'status': 'success',
        'error': None
    }
    
    print(f"\n🔎 Checking domain: {domain}")
    
    try:
        # Get both HTTP and HTTPS versions of the domain
        normalized_domains = normalize_domain(domain)
        all_sitemap_urls = set()
        all_compressed_sitemaps = set()
        
        for normalized_domain in normalized_domains:
            protocol = "HTTPS" if normalized_domain.startswith("https") else "HTTP"
            print(f"  ┌─ Testing {protocol} protocol")
            
            try:
                # First check robots.txt for sitemap directives
                print(f"  ├─ Checking robots.txt")
                sitemap_urls = check_robots_txt(normalized_domain, timeout)
                if sitemap_urls:
                    print(f"  │  ✓ Found {len(sitemap_urls)} sitemap(s) in robots.txt")
                all_sitemap_urls.update(sitemap_urls)
                
                # Then check common sitemap locations
                print(f"  ├─ Checking common locations")
                common_sitemaps, compressed_sitemaps = check_common_locations(normalized_domain, timeout)
                if common_sitemaps:
                    print(f"  │  ✓ Found {len(common_sitemaps)} sitemap(s) in common locations")
                if compressed_sitemaps:
                    print(f"  │  ✓ Found {len(compressed_sitemaps)} compressed sitemap(s)")
                    
                all_sitemap_urls.update(common_sitemaps)
                all_compressed_sitemaps.update(compressed_sitemaps)
            except RequestException:
                print(f"  │  ✗ {protocol} connection failed")
                # Continue with the other protocol if one fails
                continue
            print(f"  └─ {protocol} check complete")
                
        # Extract URLs from compressed sitemaps
        if all_compressed_sitemaps:
            print(f"  ┌─ Processing {len(all_compressed_sitemaps)} compressed sitemap(s)")
            nested_urls = fetch_compressed_sitemaps(all_compressed_sitemaps, timeout)
            result['nested_urls'] = list(nested_urls)
            print(f"  └─ Extracted {len(nested_urls)} URLs from compressed sitemaps")
        
        result['sitemaps'] = list(all_sitemap_urls)
        
    except Exception as e:
        # Simplify error message
        error_msg = "Connection failed" if isinstance(e, RequestException) else "Processing error"
        result['status'] = 'error'
        result['error'] = error_msg
    
    return result

def process_domains(domains: List[str], timeout: int, concurrency: int) -> List[Dict]:
    """Process multiple domains concurrently with progress bar, checking both HTTP and HTTPS."""
    results = []
    total_domains = len(domains)
    
    # Create simple progress counter instead of a progress bar
    print(f"Processing {total_domains} domains...")
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        # Submit all tasks
        futures = {executor.submit(find_sitemaps_for_domain, domain, timeout): domain for domain in domains}
        
        # Process results as they complete
        for future in as_completed(futures):
            domain = futures[future]
            try:
                result = future.result()
                results.append(result)
                
                # Summary is now printed in the find_sitemaps_for_domain function
                sitemap_count = len(result['sitemaps'])
                print(f"✅ {domain} complete: {sitemap_count} sitemaps found")
            except Exception as e:
                # Simplify error message
                error_msg = "Connection failed" if isinstance(e, RequestException) else "Processing error"
                results.append({
                    'domain': domain,
                    'sitemaps': [],
                    'status': 'error',
                    'error': error_msg
                })
                print(f"❌ {domain} failed: {error_msg}", file=sys.stderr)
            
            # No progress bar to update
    
    # No progress bar to close
    return results

def save_as_json(results: List[Dict], output_file: str):
    """Save results in JSON format."""
    with open(f"{output_file}.json", 'w') as f:
        json.dump(results, f, indent=2)

def save_as_csv(results: List[Dict], output_file: str):
    """Save results in CSV format."""
    with open(f"{output_file}.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Domain', 'Status', 'Error', 'Sitemaps', 'URLs Inside Compressed Sitemaps'])
        
        for result in results:
            writer.writerow([
                result['domain'],
                result['status'],
                result['error'] or '',
                ', '.join(result['sitemaps']),
                ', '.join(result.get('nested_urls', []))
            ])

def main():
    """Main function."""
    args = setup_argparse()
    
    print(f"\n📋 Reading domains from {args.input_file}...")
    domains = read_domains(args.input_file)
    print(f"📊 Found {len(domains)} domains")
    
    print(f"\n🔍 Finding sitemaps using both HTTP and HTTPS [concurrency={args.concurrency}, timeout={args.timeout}s]\n")
    
    results = process_domains(domains, args.timeout, args.concurrency)
    
    if args.format == 'json':
        save_as_json(results, args.output)
        print(f"Results saved to {args.output}.json")
    else:
        save_as_csv(results, args.output)
        print(f"Results saved to {args.output}.csv")
    
    # Print summary with emoji icons for better visual clarity
    total_sitemaps = sum(len(result['sitemaps']) for result in results)
    total_nested_urls = sum(len(result.get('nested_urls', [])) for result in results)
    success_count = sum(1 for result in results if result['status'] == 'success')
    error_count = sum(1 for result in results if result['status'] == 'error')
    compressed_count = sum(1 for result in results if any(is_compressed_format(url) for url in result['sitemaps']))
    
    print(f"\n📊 SUMMARY")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"✓ Processed:       {len(domains)} domains")
    print(f"📄 Total sitemaps:   {total_sitemaps}")
    print(f"🗜️  Compressed maps: {compressed_count} domains")
    print(f"🔗 URLs extracted:  {total_nested_urls}")
    print(f"✅ Success:         {success_count} domains")
    print(f"❌ Errors:          {error_count} domains")

if __name__ == "__main__":
    main()
