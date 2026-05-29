#!/usr/bin/env python3
"""
Docusaurusify - Add Docusaurus headers to Markdown files and fix links

This script processes Markdown files in a specified folder and adds
Docusaurus-compatible headers with id and title metadata. It also fixes
markdown links according to specific rules for Docusaurus compatibility.
"""

import os
import sys
import argparse
import shutil
import glob
import re


def generate_header(file_name, title):
    """Generate Docusaurus header with id and title."""
    id_value = file_name.lower().replace(" ", "-").replace(".md", "")
    return f"---\nid: {id_value}\ntitle: {title}\n---\n\n"


def normalize_filename(filename):
    """Normalize filename to lowercase and replace spaces with dashes."""
    name, ext = os.path.splitext(filename)
    normalized_name = name.lower().replace(" ", "-")
    return f"{normalized_name}{ext}"


def get_output_path(input_path, base_input_path, output_dir):
    """Determine the output path based on the rules."""
    rel_path = os.path.relpath(input_path, base_input_path)
    
    # Handle README.md -> overview.md
    if os.path.basename(rel_path).lower() == "readme.md":
        rel_path = os.path.join(os.path.dirname(rel_path), "overview.md")
    
    # Check if file is in Documentation/Classes before removing Documentation
    is_classes_file = False
    path_parts = rel_path.split(os.sep)
    if (len(path_parts) >= 3 and 
        path_parts[0].lower() == "documentation" and 
        path_parts[1].lower() == "classes"):
        is_classes_file = True
    
    # Remove Documentation/ from path if present
    if len(path_parts) > 0 and path_parts[0].lower() == "documentation":
        rel_path = os.path.join(*path_parts[1:]) if len(path_parts) > 1 else ""
    
    # Normalize filename (but not for Classes files)
    if rel_path:
        dir_path = os.path.dirname(rel_path)
        filename = os.path.basename(rel_path)
        
        if is_classes_file:
            # Keep original filename for Classes files
            normalized_filename = filename
        else:
            # Normalize filename for other files
            normalized_filename = normalize_filename(filename)
            
        rel_path = os.path.join(dir_path, normalized_filename) if dir_path else normalized_filename
    
    return os.path.join(output_dir, rel_path)


def convert_admonitions(content):
    """Convert GitHub-style admonitions to Docusaurus admonition syntax.

    Converts:
        > [!TIP]
        > Title or content
        >
        > More content

    To:
        :::tip Title or content

        More content

        :::
    """
    lines = content.split('\n')
    result = []
    i = 0

    admonition_types = {'TIP': 'tip', 'NOTE': 'note', 'WARNING': 'warning',
                        'CAUTION': 'caution', 'IMPORTANT': 'danger'}

    while i < len(lines):
        # Check for GitHub admonition start: > [!TYPE]
        match = re.match(r'^>\s*\[!(TIP|NOTE|WARNING|CAUTION|IMPORTANT)\]\s*$', lines[i])
        if match:
            admonition_type = admonition_types[match.group(1)]
            i += 1

            # Collect all lines that are part of this blockquote
            block_lines = []
            while i < len(lines) and re.match(r'^>', lines[i]):
                # Strip the leading > and optional space
                line = re.sub(r'^>\s?', '', lines[i])
                block_lines.append(line)
                i += 1

            # Find the title (first non-empty line)
            title = ''
            content_start = 0
            for j, line in enumerate(block_lines):
                if line.strip():
                    title = line.strip()
                    content_start = j + 1
                    break

            # Collect remaining content lines
            body_lines = block_lines[content_start:]

            # Strip leading/trailing empty lines from body
            while body_lines and not body_lines[0].strip():
                body_lines.pop(0)
            while body_lines and not body_lines[-1].strip():
                body_lines.pop()

            # Build the Docusaurus admonition
            result.append(f':::{admonition_type} {title}')
            if body_lines:
                result.append('')
                result.extend(body_lines)
            result.append('')
            result.append(':::')
        else:
            result.append(lines[i])
            i += 1

    return '\n'.join(result)


def fix_markdown_links(content, file_path, base_input_path, is_readme_file=False):
    """Fix markdown links according to the specified rules."""
    
    def replace_link(match):
        link_text = match.group(1)
        link_url = match.group(2)
        
        # Rule 1: For README.md (copied to overview.md), remove "Documentation/" from links
        if is_readme_file and link_url.startswith("Documentation/"):
            new_url = link_url[len("Documentation/"):]
            return f"[{link_text}]({new_url})"
        
        # Rule 2: Update links pointing to readme.md to point to overview.md
        if link_url.endswith("readme.md") or link_url.endswith("README.md"):
            # Replace the filename part with overview.md
            new_url = re.sub(r'readme\.md$|README\.md$', 'overview.md', link_url, flags=re.IGNORECASE)
            
            # Rule 3: For files originally in Documentation, remove one "../" level
            rel_path = os.path.relpath(file_path, base_input_path)
            path_parts = rel_path.split(os.sep)
            
            if (len(path_parts) >= 2 and 
                path_parts[0].lower() == "documentation" and 
                new_url.startswith("../")):
                # Remove one level of "../" since the file will be moved up one directory level
                new_url = new_url[3:]  # Remove "../"
                
            return f"[{link_text}]({new_url})"
        
        # Return unchanged if no rules apply
        return match.group(0)
    
    # Pattern to match markdown links [text](url)
    link_pattern = r'\[([^\]]*)\]\(([^)]+)\)'
    
    return re.sub(link_pattern, replace_link, content)


def clean_output_directory(output_dir, force=False, verbose=False):
    """Clean the output directory, asking for confirmation unless force is True."""
    if not os.path.exists(output_dir):
        return True
    
    # Check if directory has any files
    has_files = False
    try:
        for root, dirs, files in os.walk(output_dir):
            if files:
                has_files = True
                break
    except Exception as e:
        print(f"Error checking output directory: {e}", file=sys.stderr)
        return False
    
    if not has_files:
        if verbose:
            print(f"Output directory '{output_dir}' is already empty.")
        return True
    
    if not force:
        print(f"Output directory '{output_dir}' contains files.")
        response = input("Do you want to remove all existing files? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Operation cancelled.")
            return False
    
    # Remove all contents
    try:
        shutil.rmtree(output_dir)
        if verbose:
            print(f"Cleaned output directory: {output_dir}")
        return True
    except Exception as e:
        print(f"Error cleaning output directory: {e}", file=sys.stderr)
        return False


def process_markdown_files(folder_path, output_dir, verbose=False):
    """Process all Markdown files in the specified folder and add Docusaurus headers."""
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    # Create output directory if it doesn't exist
    try:
        os.makedirs(output_dir, exist_ok=True)
        if verbose:
            print(f"Output directory: {output_dir}")
    except Exception as e:
        print(f"Error creating output directory '{output_dir}': {e}", file=sys.stderr)
        sys.exit(1)
    
    # Find all markdown files recursively
    markdown_files = []
    try:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # Skip files that start with underscore (private files)
                if file.startswith("_"):
                    if verbose:
                        print(f"Skipping private file: {file}")
                    continue
                    
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    markdown_files.append(full_path)
        
        if not markdown_files:
            print("No Markdown files found in the specified folder.")
            return
        
        print(f"Found {len(markdown_files)} Markdown file(s) to process.")
        
    except PermissionError:
        print(f"Error: Permission denied accessing folder '{folder_path}'.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Unable to read folder '{folder_path}': {e}", file=sys.stderr)
        sys.exit(1)
    
    for file_path in markdown_files:
        file_name = os.path.basename(file_path)
        
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                lines = file.readlines()
        except Exception as e:
            print(f"Error reading {file_name}: {e}")
            error_count += 1
            continue
        
        # Find the first title (#)
        title = None
        for line in lines:
            if line.startswith("# "):  # Look for level 1 title
                title = line[2:].strip()
                break
        
        # Determine output path
        output_path = get_output_path(file_path, folder_path, output_dir)
        
        # Create output directory structure if needed
        output_dir_path = os.path.dirname(output_path)
        if output_dir_path:
            try:
                os.makedirs(output_dir_path, exist_ok=True)
            except Exception as e:
                print(f"Error creating directory for {file_name}: {e}")
                error_count += 1
                continue
        
        # Fix markdown links in content
        content = "".join(lines)
        is_readme_file = os.path.basename(file_path).lower() == "readme.md"
        fixed_content = fix_markdown_links(content, file_path, folder_path, is_readme_file)
        fixed_content = convert_admonitions(fixed_content)
        
        if title:
            # Generate the header using the normalized filename for ID
            normalized_filename = os.path.basename(output_path)
            header = generate_header(normalized_filename, title)
            
            # Check if header already exists
            if not lines or not lines[0].startswith("---"):
                try:
                    # Write file with header and fixed links to output directory
                    with open(output_path, "w", encoding="utf-8") as file:
                        file.write(header + fixed_content)
                    
                    if verbose:
                        print(f"✓ Header added and links fixed: {file_name} -> {os.path.relpath(output_path, output_dir)}")
                    processed_count += 1
                except Exception as e:
                    print(f"Error writing to {os.path.basename(output_path)}: {e}")
                    error_count += 1
            else:
                # Copy file with fixed links if header already exists
                try:
                    with open(output_path, "w", encoding="utf-8") as file:
                        file.write(fixed_content)
                    if verbose:
                        print(f"- Header already present, links fixed: {file_name} -> {os.path.relpath(output_path, output_dir)}")
                    skipped_count += 1
                except Exception as e:
                    print(f"Error writing to {os.path.basename(output_path)}: {e}")
                    error_count += 1
        else:
            # Copy file with fixed links if no title found
            try:
                with open(output_path, "w", encoding="utf-8") as file:
                    file.write(fixed_content)
                if verbose:
                    print(f"⚠ No title found, links fixed: {file_name} -> {os.path.relpath(output_path, output_dir)}")
                error_count += 1
            except Exception as e:
                print(f"Error writing to {os.path.basename(output_path)}: {e}")
                error_count += 1
    
    # Summary
    print(f"\nSummary:")
    print(f"  Files processed (headers added, links fixed): {processed_count}")
    print(f"  Files skipped (already had headers, links fixed): {skipped_count}")
    print(f"  Files with errors: {error_count}")


def main():
    """Main function to handle command line arguments and execute the script."""
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Add Docusaurus headers to Markdown files and fix links for Docusaurus compatibility.",
        epilog="Example: python docusaurusify.py /path/to/markdown/folder",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "folder_path",
        help="Path to the folder containing Markdown files"
    )
    
    parser.add_argument(
        "-o", "--output",
        dest="output_dir",
        help="Output directory for processed files (default: <folder_path>/docusaurus)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force overwrite output directory without confirmation"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.join(args.folder_path, "docusaurus")
    
    # Check if folder exists
    if not os.path.exists(args.folder_path):
        print(f"Error: The folder '{args.folder_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.isdir(args.folder_path):
        print(f"Error: '{args.folder_path}' is not a directory.", file=sys.stderr)
        sys.exit(1)
    
    # Clean output directory
    if not clean_output_directory(output_dir, args.force, args.verbose):
        sys.exit(1)
    
    # Process the markdown files
    print(f"Processing Markdown files in: {args.folder_path}")
    process_markdown_files(args.folder_path, output_dir, args.verbose)
    print("Processing complete!")


if __name__ == "__main__":
    main()
