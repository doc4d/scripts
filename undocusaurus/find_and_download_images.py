import os
import re
import argparse
import requests
from urllib.parse import urljoin

def extract_image_links(markdown_content):
    """Extract image links from markdown content."""
    image_links = re.findall(r'!\[.*?\]\((.*?)\)', markdown_content)
    return image_links

def process_markdown_files(folder, base_url=None, download=False):
    """Process all markdown files in the folder to find and optionally download image links."""
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                print(f"Processing: {file_path}")

                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                image_links = extract_image_links(content)
                if image_links:
                    print(f"Found {len(image_links)} image link(s) in {file}:")
                    for link in image_links:
                        link = link.replace('../', '') 
                        resolved_link = urljoin(base_url, link) if base_url and not link.startswith(('http://', 'https://')) else link
                        print(f"  - {resolved_link}")

                        if download:
                            download_image(resolved_link, root)
                else:
                    print(f"No image links found in {file}.")

def download_image(url, save_folder):
    """Download an image from a URL to the specified folder."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Extract the image name from the URL and save it in the folder
        image_name = os.path.basename(url)
        save_path = os.path.join(save_folder, image_name)

        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        print(f"Downloaded: {url} -> {save_path}")
    except requests.RequestException as e:
        print(f"Failed to download {url}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract and optionally download images from Markdown files in a folder.")
    parser.add_argument("folder", help="Path to the folder containing Markdown files.")
    parser.add_argument("--base-url", help="Base URL to resolve relative image links.")
    parser.add_argument("--download", action="store_true", help="Download the images to the folder.")
    args = parser.parse_args()

    if not os.path.isdir(args.folder):
        print(f"The folder '{args.folder}' does not exist or is not a directory.")
        exit(1)

    process_markdown_files(args.folder, base_url=args.base_url, download=args.download)