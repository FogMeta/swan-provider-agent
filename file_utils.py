import os
import re
import subprocess
import logging
import glob
import markdown

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# --------------------
# Helper Functions for Repository & Conversion
# --------------------
def update_repo(local_repo_path: str) -> None:
    """Clone the repository if it doesn't exist, or pull the latest changes."""
    repo_url = os.getenv("REPO_URL")
    if not os.path.exists(local_repo_path):
        logging.info("Cloning repository...")
        subprocess.run(["git", "clone", repo_url, local_repo_path], check=True)
    else:
        logging.info("Repository exists. Pulling latest changes...")
        subprocess.run(["git", "-C", local_repo_path, "pull"], check=True)

def remove_html_tags(text: str) -> str:
    """Remove HTML tags from a string."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def convert_markdown_to_text(input_dir: str, output_dir: str) -> None:
    """
    Convert all Markdown files in the input directory (recursively) to plain-text files.
    Save the resulting .txt files in the output directory.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Count total number of files by extension
    file_counts = {}
    all_files = glob.glob(os.path.join(input_dir, "**/*"), recursive=True)
    for file in all_files:
        if os.path.isfile(file):
            ext = os.path.splitext(file)[1]
            file_counts[ext] = file_counts.get(ext, 0) + 1

    # Print the count of each file type
    for ext, count in file_counts.items():
        print(f"Number of {ext if ext else 'no extension'} files: {count}")
        logging.info("Number of %s files: %d", ext if ext else "no extension", count)

    # Count number of Markdown files
    md_files = glob.glob(os.path.join(input_dir, "**/*.md"), recursive=True)
    logging.info("Number of Markdown files: %d", len(md_files))

    if not md_files:
        logging.error("No markdown files found in %s", input_dir)
        raise ValueError("No markdown files found in input")

    txt_file_count = 0  # Count number of generated text files
    for file in md_files:
        try:
            # Get the relative path and convert it to a filename prefix
            rel_path = os.path.relpath(file, input_dir)
            dir_prefix = os.path.dirname(rel_path).replace(os.sep, '_')
            base_name = os.path.splitext(os.path.basename(file))[0]

            # If the file is in a subdirectory, add the directory prefix
            final_name = f"{dir_prefix}_{base_name}" if dir_prefix else base_name

            with open(file, "r", encoding="utf-8") as f:
                md_text = f.read()
            html = markdown.markdown(md_text)
            text = " ".join(html.splitlines())

            # Remove HTML tags from the text
            clean_text = remove_html_tags(text)

            out_file = os.path.join(output_dir, final_name + ".txt")
            with open(out_file, "w", encoding="utf-8") as out:
                out.write(clean_text)

            txt_file_count += 1  # Increment text file count
        except Exception as e:
            logging.error("Error converting file %s: %s", file, e)
    print(f"Number of generated text files: {txt_file_count}")
    print(f"Converted {len(md_files)} markdown files to text in {output_dir}.")
    logging.info("Number of generated text files: %d", txt_file_count)
    logging.info("Converted %d markdown files to text in %s.", len(md_files), output_dir)