import requests
from bs4 import BeautifulSoup
import json
import re
from typing import Optional, Dict, List, Union

def extract_xhs_url(text: str) -> Optional[str]:
    """
    Extract Xiaohongshu URL from text, supporting both direct xiaohongshu.com URLs
    and xhslink.com short URLs.
    
    Args:
        text (str): Input text that may contain a Xiaohongshu URL
        
    Returns:
        Optional[str]: Extracted URL or None if no valid URL found
    """
    # Try to find a xhslink.com URL in the input string
    xhslink_match = re.search(r"(https?://xhslink\.com/\S+)", text)
    if xhslink_match:
        return xhslink_match.group(1)

    # Check if the input itself is a xiaohongshu.com URL
    if re.search(r"^https?://(www\.)?xiaohongshu\.com/(explore|discovery/item)/\S+", text):
        return text

    return None

def scrape_xhs(url: str) -> Optional[Dict[str, Union[str, List[str]]]]:
    """
    Attempts to scrape title, body, and image URLs from a Xiaohongshu post URL.

    Args:
        url (str): The URL of the Xiaohongshu post.

    Returns:
        Optional[Dict[str, Union[str, List[str]]]]: A dictionary containing 'title', 'body', and 'image_urls',
              or None if scraping fails.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    title = ""
    body = ""
    image_urls = []

    # Try to extract from JSON data first
    script_tag = soup.find('script', string=re.compile(r'window\.__INITIAL_STATE__\s*='))
    if script_tag:
        try:
            json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});?\s*\(function', script_tag.string, re.DOTALL | re.IGNORECASE)
            if json_match:
                json_data = json.loads(json_match.group(1))
                note_data = json_data.get('note', {}).get('noteDetailMap', {}).get('default', {}).get('note', {})
                title = note_data.get('title', '')
                body = note_data.get('desc', '')
                images_list = note_data.get('imageList', [])
                image_urls = [img.get('url_default', '') or img.get('url', '') for img in images_list if img.get('url_default') or img.get('url')]
                image_urls = [url for url in image_urls if url]
        except (json.JSONDecodeError, AttributeError, KeyError):
            pass

    # Fallback to HTML parsing if needed
    if not title:
        title_tag = soup.find('title')
        if title_tag:
            full_title = title_tag.text.strip()
            suffix = " - 小红书"
            if full_title.endswith(suffix):
                title = full_title[:-len(suffix)].strip()
            else:
                title = full_title

    if not body:
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        if meta_desc_tag and meta_desc_tag.get('content'):
            body = meta_desc_tag.get('content').strip()

    if not image_urls:
        # Try Open Graph image meta tags
        og_image_tags = soup.find_all('meta', attrs={'name': 'og:image'}) or \
                       soup.find_all('meta', attrs={'property': 'og:image'})
        
        if og_image_tags:
            image_urls = [tag.get('content') for tag in og_image_tags if tag.get('content')]
        else:
            # Try preload link tags
            link_tags = soup.find_all('link', attrs={'rel': 'preload', 'as': 'image'})
            image_urls = [link.get('href') for link in link_tags if link.get('href')]

    return {
        "title": title,
        "body": body,
        "image_urls": image_urls
    } 