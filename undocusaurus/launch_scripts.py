import os
import sys
import subprocess

def launch_scripts(target_folder):
    # Directory containing the scripts
    scripts_folder = os.path.dirname(os.path.abspath(__file__))
    scripts_to_run = ["rename_md_files.py", "remove_md_headers.py", "fix_markdown_links.py", "add_header_if_missing.py", "remove_details_block.py", "remove history detail block"]

    # Check if the target folder exists
    if not os.path.isdir(target_folder):
        print(f"The target folder '{target_folder}' does not exist.")
        return

    # Iterate through the scripts and run them
    for script in scripts_to_run:
        script_path = os.path.join(scripts_folder, script)

        # Check if the script exists
        if not os.path.isfile(script_path):
            print(f"Script '{script}' not found in the '{scripts_folder}' folder. Skipping...")
            continue

        # Execute the script with the target folder as a parameter
        try:
            print(f"Running '{script}' with target folder '{target_folder}'...")
            subprocess.run([sys.executable, script_path, target_folder], check=True)
            print(f"'{script}' executed successfully.\n")
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while running '{script}': {e}\n")

# Example usage
if __name__ == "__main__":
    target_folder = folder = sys.argv[1] if len(sys.argv) > 1 else input("Enter the folder path: ")
    launch_scripts(target_folder)