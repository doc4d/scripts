import os
import re
import sys

def rename_md_files_in_folder(folder_path):
    # Regular expression to match the header pattern
    header_pattern = re.compile(r"---\s*id: .+\s*title: (.+)\s*---", re.MULTILINE)

    # Browse through all files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".md"):
            file_path = os.path.join(folder_path, filename)

            # Read the contents of the file
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()

            # Find the title in the header
            match = header_pattern.search(content)
            if match:
                # Extract the title and clean it for file naming
                title = match.group(1).strip()
                sanitized_title = re.sub(r'[\\/*?:"<>|]', "", title)  # Remove invalid characters

                # Rename the file
                new_filename = f"{sanitized_title}.md"
                new_file_path = os.path.join(folder_path, new_filename)
                os.rename(file_path, new_file_path)
                print(f"Renamed '{filename}' to '{new_filename}'.")
            else:
                print(f"No matching header found in '{filename}'.")

# Example usage
if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else input("Enter the folder path: ")
    if os.path.isdir(folder):
        rename_md_files_in_folder(folder)
    else:
        print("Invalid folder path.")