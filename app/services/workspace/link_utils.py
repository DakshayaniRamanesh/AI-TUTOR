"""
URL Detection, OpenGraph Metadata Fetching, and Link Classification
"""

import re
import requests
from bs4 import BeautifulSoup

URL_REGEX = re.compile(
    r'^(?:http|ftp)s?://' # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
    r'localhost|' # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
    r'(?::\d+)?' # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE
)

def is_valid_url(text: str) -> bool:
    if not text:
        return False
    return bool(URL_REGEX.match(text.strip()))

def is_video_url(url: str) -> bool:
    url_lower = url.lower()
    video_domains = ['youtube.com', 'youtu.be', 'vimeo.com', 'tiktok.com', 'dailymotion.com']
    video_exts = ['.mp4', '.webm', '.mov', '.m4v', '.avi']
    
    if any(domain in url_lower for domain in video_domains):
        return True
    if any(url_lower.endswith(ext) or ext + '?' in url_lower for ext in video_exts):
        return True
    return False

def fetch_url_metadata(url: str) -> dict:
    """
    Fetches OpenGraph / meta tags for preview card generation.
    """
    result = {
        "title": url,
        "subtitle": "Web Link",
        "image_url": "",
        "source_url": url,
        "is_video": is_video_url(url)
    }
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Extract og:title or title
            og_title = soup.find('meta', property='og:title') or soup.find('meta', name='twitter:title')
            if og_title and og_title.get('content'):
                result['title'] = og_title['content']
            elif soup.title and soup.title.string:
                result['title'] = soup.title.string.strip()
                
            # Extract description
            og_desc = soup.find('meta', property='og:description') or soup.find('meta', name='description')
            if og_desc and og_desc.get('content'):
                result['subtitle'] = og_desc['content'][:140] + ("..." if len(og_desc['content']) > 140 else "")
                
            # Extract og:image
            og_img = soup.find('meta', property='og:image') or soup.find('meta', name='twitter:image')
            if og_img and og_img.get('content'):
                result['image_url'] = og_img['content']
                
    except Exception as err:
        print(f"Error fetching metadata for {url}: {err}")
        
    return result
