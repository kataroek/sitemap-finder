# Sitemap Finder

A Python tool to discover sitemaps for a list of domains, including compressed sitemap formats.

## Features

- Searches for sitemaps at common locations (XML, PHP, TXT, HTML)
- Supports compressed sitemap formats (.gz and .zip)
- Extracts URLs from inside compressed sitemaps
- Discovers specialized sitemaps (news, image, video, product, etc.)
- Extracts sitemap URLs from robots.txt
- Processes multiple domains concurrently
- Outputs results in JSON or CSV format
- Configurable timeout and concurrency settings

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/sitemap-finder.git
   cd sitemap-finder
   ```

2. Install dependencies:

   ```bash
   # Using pip
   python3 -m pip install -r requirements.txt
   
   # Using bun (if you prefer)
   bun install requests
   ```

## Usage

1. Create a text file with domain names, one per line:

   ```txt
   example.com
   example.org
   https://example.net
   ```

2. Make the script executable (Unix/Linux/MacOS):

   ```bash
   chmod +x sitemap_finder.py
   ```

3. Run the script using one of these methods:

   ```bash
   # Method 1: Using the executable directly
   ./sitemap_finder.py domains.txt
   
   # Method 2: Using Python interpreter
   python3 sitemap_finder.py domains.txt
   ```

4. Using additional options:

   ```bash
   # Output as CSV instead of JSON
   python3 sitemap_finder.py domains.txt -f csv
   
   # Set a custom output filename
   python3 sitemap_finder.py domains.txt -o my_sitemaps
   
   # Increase timeout to 15 seconds and concurrency to 10
   python3 sitemap_finder.py domains.txt -t 15 -c 10
   
   # Combine multiple options
   python3 sitemap_finder.py domains.txt -o custom_results -f csv -t 15 -c 10
   ```

## Command Line Options

- `input_file`: Text file containing domain names (one per line)
- `-o, --output`: Output file name (default: sitemaps_output)
- `-f, --format`: Output format, either json or csv (default: json)
- `-t, --timeout`: Request timeout in seconds (default: 10)
- `-c, --concurrency`: Number of concurrent requests (default: 5)

## Complete Example

```bash
# Create a domains file
echo "example.com\ngithub.com\nwordpress.org" > domains.txt

# Run the script
python3 sitemap_finder.py domains.txt -o my_results -f json
```

This will:
1. Read domains from `domains.txt`
2. Find standard and compressed sitemaps for each domain
3. Extract URLs from any compressed sitemaps found
4. Display progress as each domain is processed
5. Save all results to `my_results.json`
6. Print a summary of the findings

## Output Format

The tool produces a JSON or CSV file with the following information for each domain:

```json
{
  "domain": "example.com",
  "sitemaps": ["https://example.com/sitemap.xml", "https://example.com/sitemap.xml.gz"],
  "nested_urls": ["https://example.com/page1", "https://example.com/page2"],
  "status": "success",
  "error": null
}
```

- `domain`: The domain that was checked
- `sitemaps`: List of sitemap URLs found for the domain
- `nested_urls`: URLs extracted from inside compressed sitemaps
- `status`: Success or error
- `error`: Error message if any

## Troubleshooting

- If you encounter SSL certificate errors, try updating your SSL certificates or add `-t 20` to increase the timeout
- For domains with rate limiting, consider reducing concurrency with `-c 1`
- If the script seems stuck, it might be processing large compressed sitemaps; increase the timeout with `-t 30`
