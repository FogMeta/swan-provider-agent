import asyncio
import os
import logging
from dotenv import load_dotenv
import file_utils
import graphrag_utils

# Configure logging.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def process_question(query: str) -> str:
    """
    Process a user question:
      1. Update repository and convert markdown.
      2. Build (if needed) and query the GraphRAG index.
      3. Construct the prompt.
      4. Call Meta Llama3 to generate an answer.
    Returns the answer as a string.
    """
    PROJECT_DIRECTORY = os.environ.get("WORK_DIRECTORY", "./ragtest")  # Project directory containing settings.yaml and output folder.
    LOCAL_REPO_PATH = os.path.join(PROJECT_DIRECTORY, "doc_swanchain_repo")
    file_utils.update_repo(LOCAL_REPO_PATH)
    # Converted text files will be saved under the "input" folder.
    CONVERTED_DIR = os.path.join(PROJECT_DIRECTORY, "input")
    file_utils.convert_markdown_to_text(LOCAL_REPO_PATH, CONVERTED_DIR)
    await graphrag_utils.build_index(PROJECT_DIRECTORY, test_mode=False, force_build_graph=False)
    response, context = await graphrag_utils.query_index(PROJECT_DIRECTORY, query, 'global')
    return response

if __name__ == "__main__":
    # Load environment variables from .env file.
    load_dotenv()
    # For testing the agent standalone, uncomment the following lines:
    answer = asyncio.run(process_question("what is computing-provider account?"))
    print("Agent Answer:", answer)
