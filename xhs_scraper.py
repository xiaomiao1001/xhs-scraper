import requests
from bs4 import BeautifulSoup
import json
import re
import argparse
import sys # Import sys to exit script on error

def scrape_xhs(url):
    """
    Attempts to scrape title, body, and image URLs from a Xiaohongshu post URL.

    Args:
        url (str): The URL of the Xiaohongshu post.

    Returns:
        dict: A dictionary containing 'title', 'body', and 'image_urls',
              or None if scraping fails. Returns empty strings/lists if
              specific elements aren't found.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
    except requests.exceptions.RequestException as e:
        print(f"请求错误: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    title = ""
    body = ""
    image_urls = []

    # --- Attempt to find data ---
    # Xiaohongshu often embeds data in a <script> tag as JSON.
    script_tag = soup.find('script', string=re.compile(r'window\.__INITIAL_STATE__\s*='))

    if script_tag:
        try:
            # Extract JSON string using regex
            json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});?\s*\(function', script_tag.string, re.DOTALL | re.IGNORECASE)
            if json_match:
                json_data = json.loads(json_match.group(1))
                # Navigate through the JSON structure (this structure might change!)
                # The exact path depends heavily on Xiaohongshu's current frontend structure.
                # This is a guess based on common patterns and needs inspection if it fails.
                note_data = json_data.get('note', {}).get('noteDetailMap', {}).get('default', {}).get('note', {})

                title = note_data.get('title', '')
                body = note_data.get('desc', '')
                images_list = note_data.get('imageList', [])
                image_urls = [img.get('url_default', '') or img.get('url', '') for img in images_list if img.get('url_default') or img.get('url')] # Prefer default url if available
                image_urls = [url for url in image_urls if url] # Filter out empty URLs

            else:
                 print("未能从<script>标签中提取JSON数据。")

        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            print(f"解析JSON数据时出错: {e}。 尝试备用方法。")
            # Fallback if JSON parsing fails or structure is different

    # --- Fallback using common HTML tags (less reliable) ---
    if not title:
        title_tag = soup.find('title')
        if title_tag:
            full_title = title_tag.text.strip()
            # Remove the common suffix if present
            suffix = " - 小红书"
            if full_title.endswith(suffix):
                title = full_title[:-len(suffix)].strip()
            else:
                title = full_title
        else:
            # Try common heading tags
            h1_tag = soup.find('h1')
            if h1_tag:
                title = h1_tag.text.strip()

    if not body:
        # Look for the description meta tag first
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        if meta_desc_tag and meta_desc_tag.get('content'):
            body = meta_desc_tag.get('content').strip()
        else:
            # Fallback: Look for divs that might contain the description
            # Common class names might include 'desc', 'content', 'note-content' etc. - highly speculative
            desc_div = soup.find('div', class_=re.compile(r'(desc|content|text)')) # Regex for common class patterns
            if desc_div:
                body = desc_div.get_text(separator='\n', strip=True)

    # Fallback for images if JSON method failed
    if not image_urls:
        # First fallback: Look for Open Graph image meta tags
        og_image_tags = soup.find_all('meta', attrs={'name': 'og:image'})
        if not og_image_tags:
             og_image_tags = soup.find_all('meta', attrs={'property': 'og:image'}) # Also check property attribute

        if og_image_tags:
            for tag in og_image_tags:
                content = tag.get('content')
                if content and content not in image_urls:
                    image_urls.append(content)

        # Second fallback: Look for preload link tags for images (if og:image meta tags not found/empty)
        if not image_urls:
            link_tags = soup.find_all('link', attrs={'rel': 'preload', 'as': 'image'})
            for link in link_tags:
                href = link.get('href')
                if href and href not in image_urls:
                    image_urls.append(href)

        # Third fallback: Look for <img> tags (less likely for main images now)
        if not image_urls:
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src') or img.get('data-src') # Check src and data-src
                if src and ('xiaohongshu.com' in src or src.startswith('http')): # Basic filtering
                    # Avoid tiny icons/logos if possible (simple check)
                    width = img.get('width')
                    height = img.get('height')
                    is_likely_content_img = True
                    if width:
                        try: is_likely_content_img = int(width) > 50
                        except ValueError: pass
                    if height and is_likely_content_img:
                        try: is_likely_content_img = int(height) > 50
                        except ValueError: pass

                    if is_likely_content_img and src not in image_urls:
                        image_urls.append(src)

    return {
        "title": title,
        "body": body,
        "image_urls": image_urls
    }

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Scrape title, body, and image URLs from a Xiaohongshu post URL or text containing a xhslink.com URL.')
    # Change argument name and help text
    parser.add_argument('input_string', type=str, help='The direct Xiaohongshu post URL or a text snippet containing a xhslink.com URL')

    # Parse arguments
    args = parser.parse_args()
    raw_input = args.input_string
    xhs_url = None

    # 1. Try to find a xhslink.com URL in the input string
    xhslink_match = re.search(r"(https?://xhslink\.com/\S+)", raw_input)

    if xhslink_match:
        xhs_url = xhslink_match.group(1)
        print(f"从文本中提取到链接: {xhs_url}")
    else:
        # 2. If no xhslink.com URL found, check if the input itself is a xiaohongshu.com URL
        # Allow both explore and discovery/item paths
        if re.search(r"^https?://(www\\.)?xiaohongshu\\.com/(explore|discovery/item)/\\S+", raw_input):
             xhs_url = raw_input
             print("检测到直接的小红书链接。")
        else:
             # 3. If neither format is found, print error and exit
             print(f"错误：无法从输入中识别有效的小红书链接 (需要 https://www.xiaohongshu.com/... 或包含 https://xhslink.com/... 的文本)。")
             print(f"收到的输入: {raw_input}")
             sys.exit(1) # Exit the script with an error code

    # Proceed only if a URL was successfully determined
    if xhs_url:
        print(f"\n正在尝试抓取: {xhs_url}")
        scraped_data = scrape_xhs(xhs_url)

        if scraped_data:
            print("\n--- 抓取结果 ---")
            print(f"标题: {scraped_data['title']}")
            print("\n正文:")
            print(scraped_data['body'])
            print("\n图片链接:")
            if scraped_data['image_urls']:
                for img_url in scraped_data['image_urls']:
                    print(img_url)
            else:
                print("未找到图片链接。")
            print("---------------")
        else:
            print("抓取失败。")

    # Example with a different URL structure (may or may not work)
    # xhs_url_alt = "https://www.xiaohongshu.com/discovery/item/some_other_id"
    # print(f"\nTrying alternative URL structure (example): {xhs_url_alt}")
    # scraped_data_alt = scrape_xhs(xhs_url_alt)
    # # ... print results ... 