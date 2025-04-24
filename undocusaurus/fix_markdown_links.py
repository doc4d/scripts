import os
import re
import sys
import urllib.parse

def fix_markdown_links(folder_path):
    # Regular expression to find markdown links [text](xx.md)
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)\)")

    # Browse through all files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".md"):
            file_path = os.path.join(folder_path, filename)

            # Read the contents of the file
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()

            # Replace links
            def replace_link(match):
                link_text = match.group(1)
                link_target = match.group(2)

                # Replace '-' with ' ' in the link target
                link_target_fixed = link_target.replace("-", " ")

                # Check if a file with a different case exists
                link_path = os.path.join(folder_path, link_target_fixed)
                for existing_file in os.listdir(folder_path):
                    if existing_file.lower() == link_target_fixed.lower():
                        link_target_fixed = existing_file
                        break

                # Replace spaces with %20 for the link
                link_target_encoded = urllib.parse.quote(link_target_fixed)

                # Return the fixed Markdown link
                return f"[{link_text}]({link_target_encoded})"

            # Apply the link fix to the content
            updated_content = link_pattern.sub(replace_link, content)

            # Write the updated content back to the file
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(updated_content)

            print(f"Processed file: {filename}")

# Example usage
if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else input("Enter the folder path: ")
    if os.path.isdir(folder):
        fix_markdown_links(folder)
    else:
        print("Invalid folder path.")