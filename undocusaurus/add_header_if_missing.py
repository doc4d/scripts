import os
import sys

def add_header_to_md_files(folder_path):
    # Browse through all files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".md"):
            file_path = os.path.join(folder_path, filename)

            # Read the contents of the file
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.readlines()

            # Check if the first non-empty line is a header
            has_header = any(line.startswith("# ") for line in content if line.strip())

            # If no header, add one with the file name (excluding .md)
            if not has_header:
                file_name_without_extension = os.path.splitext(filename)[0]
                header = f"# {file_name_without_extension}\n\n"
                updated_content = header + "".join(content)

                # Write the updated content back to the file
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(updated_content)

                print(f"Added header to: {filename}")
            else:
                print(f"Header already exists in: {filename}")

# Example usage
if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else input("Enter the folder path: ")
    if os.path.isdir(folder):
        add_header_to_md_files(folder)
    else:
        print("Invalid folder path.")