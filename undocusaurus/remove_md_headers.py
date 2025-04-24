import os
import re
import sys


def remove_headers_from_md_files(folder_path):
    # Regular expression to match the header pattern
    header_pattern = re.compile(r"---\s*id: .+\s*title: .+\s*---\s*", re.MULTILINE)

    # Browse through all files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".md"):
            file_path = os.path.join(folder_path, filename)

            # Read the contents of the file
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()

            # Remove the header if it matches
            updated_content = header_pattern.sub("", content, count=1).strip()

            # Write the updated content back to the file
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(updated_content)

            print(f"Processed file: {filename}")

# Example usage
if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else input("Enter the folder path: ")
    if os.path.isdir(folder):
        remove_headers_from_md_files(folder)
    else:
        print("Invalid folder path.")