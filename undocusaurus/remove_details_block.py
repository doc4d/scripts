import os
import re
import sys

def remove_details_blocks(folder_path):
    # Regular expression to match <details>...</details> blocks, including multiline content
    details_pattern = re.compile(r"<details>.*?</details>", re.DOTALL)

    # Browse through all files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".md"):
            file_path = os.path.join(folder_path, filename)

            # Read the contents of the file
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()

            # Remove the <details>...</details> blocks
            updated_content = details_pattern.sub("", content).strip()

            # Write the updated content back to the file
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(updated_content)

            print(f"Processed file: {filename}")

# Example usage
if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else input("Enter the folder path: ")
    if os.path.isdir(folder):
        remove_details_blocks(folder)
    else:
        print("Invalid folder path.")