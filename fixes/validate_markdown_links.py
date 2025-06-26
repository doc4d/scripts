import os
import re
import argparse
from urllib.parse import unquote, quote

def find_markdown_files(folder):
    """Recursively find all Markdown files in a folder."""
    markdown_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".md"):
                markdown_files.append(os.path.join(root, file))
    return markdown_files

def extract_links(markdown_content):
    """Extract links from Markdown content."""
    link_pattern = r'\[.*?\]\((.*?)\)'
    return re.findall(link_pattern, markdown_content)

def validate_link(link, base_folder):
    """Check if the link is valid and attempt to fix it."""
    print(f"Validating link: {link}")
    decoded_link = unquote(link)  # Decode %20 to spaces
    potential_path = os.path.join(base_folder, decoded_link)

    if os.path.exists(potential_path):
        return link  # Link is valid

    # Try case-insensitive match
    folder, target_file = os.path.split(decoded_link)
    folder = os.path.join(base_folder, folder)
    if os.path.isdir(folder) and "https" not in folder:
        print(f"Checking folder: {folder}")
        for filename in os.listdir(folder):
            if filename.lower() == target_file.lower():
                return quote(os.path.join(folder, filename).replace(base_folder + "/", ""))

    # Try replacing hyphens with spaces
    target_file_with_spaces = target_file.replace("-", " ")
    if os.path.isdir(folder) and  "https" not in folder:
        for filename in os.listdir(folder):
            if filename.lower() == target_file_with_spaces.lower():
                return quote(os.path.join(folder, filename).replace(base_folder + "/", ""))

    # Link could not be fixed
    return None

def process_markdown_file(file_path, base_folder):
    """Process a single Markdown file to validate and fix links."""
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    links = extract_links(content)
    fixed_links = {}
    for link in links:
        fixed_link = validate_link(link, base_folder)
        if fixed_link and fixed_link != link:
            fixed_links[link] = fixed_link

    # Replace links in content
    for old_link, new_link in fixed_links.items():
        content = content.replace(f"({old_link})", f"({new_link})")

    # Save changes back to the file
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)

    if fixed_links:
        print(f"Fixed links in {file_path}:")
        for old_link, new_link in fixed_links.items():
            print(f"  {old_link} -> {new_link}")

def main():
    parser = argparse.ArgumentParser(description="Validate and fix links in Markdown files.")
    parser.add_argument("folder", help="The folder containing Markdown files.")
    args = parser.parse_args()

    markdown_files = find_markdown_files(args.folder)
    for markdown_file in markdown_files:
        process_markdown_file(markdown_file, args.folder)

if __name__ == "__main__":
    main()