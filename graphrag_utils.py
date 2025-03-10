import os
import shutil

# Import Microsoft GraphRAG API and
import graphrag.api as api
import pandas as pd
import requests
import yaml
from graphrag.cli.initialize import initialize_project_at
from graphrag.config.load_config import load_config
from graphrag.index.typing import PipelineRunResult
from pathlib import Path
import subprocess
import logging
import file_utils
import asyncio


def copy_specified_files(src_dir: str, dest_dir: str, files_to_copy: list):
    """
    Copy specified files from directory A to directory B. If the file already exists in
    directory B, its content will be overwritten.

    :param src_dir: Source directory path (directory A)
    :param dest_dir: Destination directory path (directory B)
    :param files_to_copy: List of file names to copy
    """
    # Check if the source directory exists
    if not os.path.exists(src_dir):
        print(f"Source directory {src_dir} does not exist!")
        return

    # If the destination directory doesn't exist, create it
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    # Loop through the list of files to copy
    for filename in files_to_copy:
        src_file = os.path.join(src_dir, filename)
        dest_file = os.path.join(dest_dir, filename)

        # Check if the source file exists
        if os.path.exists(src_file):
            try:
                shutil.copy(src_file, dest_file)  # Copy and overwrite if the file exists
                print(f"Copied {src_file} to {dest_file}")
            except Exception as e:
                print(f"Error copying {src_file} to {dest_file}: {e}")
        else:
            print(f"File {src_file} does not exist, skipping.")


# --------------------
# GraphRAG Indexing
# --------------------
async def build_index(project_directory: str, force_build_graph=False):
    """
    Build the GraphRAG index using the provided configuration and query it to retrieve enriched context.
    Skips index building if output files exist (unless FORCE_BUILD_GRAPH is True).
    If test_mode is True, only use a limited set of files for testing.
    """

    setting_yaml = os.path.join(project_directory, "settings.yaml")
    if os.path.exists(setting_yaml):
        print(f"Project already initialized at {project_directory}")
    else:
        # Initialize workspace
        initialize_project_at(project_directory)
        # Use custom config files
        copy_specified_files(os.getcwd(), project_directory, [".env", "settings.yaml"])

    graphRagConfig = load_config(Path(project_directory), Path(setting_yaml))
    graphRagConfig.storage.base_dir = os.path.join(project_directory, "output")
    graphRagConfig.reporting.base_dir = os.path.join(project_directory, "logs")
    graphRagConfig.embeddings.vector_store['db_uri'] = os.path.join(project_directory, "output/lancedb")
    # Determine the input directory based on test mode
    if get_bool_env_var("TEST_MODE", default=False):
        data_dir = "test_input"
        test_input_dir = os.path.join(project_directory, data_dir)
        os.makedirs(test_input_dir, exist_ok=True)
        # Assume test files are already placed in this directory

        logging.info("Test mode enabled. Using test input directory: %s", test_input_dir)
    else:
        data_dir = "input"
        abs_input_dir = os.path.join(project_directory, data_dir)
        LOCAL_REPO_PATH = os.path.join(project_directory, "doc_swanchain_repo")
        file_utils.update_repo(LOCAL_REPO_PATH)
        # Converted text files will be saved under the "input" folder.
        file_utils.convert_markdown_to_text(LOCAL_REPO_PATH, abs_input_dir)
        logging.info("Using input directory: %s", abs_input_dir)
    if not has_files(abs_input_dir):
        raise ValueError(f"No files found in {abs_input_dir}, cannot build index.\n")
        return

    # Define output file paths.
    output_folder = os.path.join(project_directory, "output")
    entities_path = os.path.join(output_folder, "create_final_entities.parquet")
    communities_path = os.path.join(output_folder, "create_final_communities.parquet")
    community_reports_path = os.path.join(output_folder, "create_final_community_reports.parquet")

    if not force_build_graph and os.path.exists(entities_path) and os.path.exists(communities_path) and os.path.exists \
                (community_reports_path):
        logging.info("Index already built, skipping index build.")
    else:
        logging.info("Building GraphRAG index...")
        try:
            index_result: list[PipelineRunResult] = await api.build_index(config=graphRagConfig)
            for workflow_result in index_result:
                if workflow_result.errors:
                    logging.error("Workflow '%s' encountered errors: %s", workflow_result.workflow,
                                  workflow_result.errors)
                else:
                    logging.info("Workflow '%s' succeeded. Details: %s", workflow_result.workflow,
                                 workflow_result.__dict__)
        except Exception as e:
            logging.error("Exception during index building: %s", e)
            raise


async def update_index(project_directory: str):
    logging.info("Updating build GraphRAG index...")
    try:
        settings_path = os.path.join(project_directory, "settings.yaml")
        await run_graphrag_update(config_path=settings_path, root_path=project_directory, verbose=True)
        logging.info("Updated build GraphRAG index...")
    except Exception as e:
        logging.error("Exception during index building: %s", e)
        raise


async def run_graphrag_update(config_path: str, root_path: str = ".", verbose: bool = False,
                              memprofile: bool = False, logger: str = "rich", cache: bool = True,
                              skip_validation: bool = False, output_path: str = None):
    # Build the command
    cmd = ["graphrag", "update"]

    # Add options to the command
    if config_path:
        cmd.extend(["--config", config_path])
    if root_path:
        cmd.extend(["--root", root_path])
    if verbose:
        cmd.append("--verbose")
    if memprofile:
        cmd.append("--memprofile")
    if logger:
        cmd.extend(["--logger", logger])
    if not cache:
        cmd.append("--no-cache")
    if skip_validation:
        cmd.append("--skip-validation")
    if output_path:
        cmd.extend(["--output", output_path])

    # Log the full command being executed
    logging.info(f"Running command: {' '.join(cmd)}")

    try:
        # Run the command
        result = subprocess.run(cmd, shell=False, check=True, text=True, capture_output=True)

        # Check if result is successful
        if result.returncode == 0:
            logging.info(f"Command executed successfully, return code: {result.returncode}")
            logging.info(f"Command Output:\n{result.stdout}")
        else:
            logging.error(f"Command failed with return code: {result.returncode}")
            logging.error(f"Error Output:\n{result.stderr}")

        # Return standard output
        return result.stdout

    except subprocess.CalledProcessError as e:
        # Catch errors in command execution
        logging.error(f"Command execution failed with error: {e.stderr}")
        return f"Error occurred: {e.stderr}"

    except Exception as e:
        # Catch any other unexpected errors
        logging.error(f"Unexpected error: {str(e)}")
        return f"Unexpected error: {str(e)}"


# --------------------
# GraphRAG Querying Functions
# --------------------
async def query_index(project_directory: str, query: str, search_mode: str):
    """
    Build the GraphRAG index using the provided configuration and query it to retrieve enriched context.
    Skips index building if output files exist (unless FORCE_BUILD_GRAPH is True).
    If test_mode is True, only use a limited set of files for testing.
    """

    graphrag_config = load_config(root_dir=Path(project_directory))
    graphrag_config.storage.base_dir = os.path.join(project_directory, "output")
    graphrag_config.reporting.base_dir = os.path.join(project_directory, "logs")
    graphrag_config.embeddings.vector_store['db_uri'] = os.path.join(project_directory, "output/lancedb")
    # Define index file paths.
    output_folder = os.path.join(project_directory, "output")
    entities_path = os.path.join(output_folder, "create_final_entities.parquet")
    communities_path = os.path.join(output_folder, "create_final_communities.parquet")
    community_reports_path = os.path.join(output_folder, "create_final_community_reports.parquet")
    nodes_path = os.path.join(output_folder, "create_final_nodes.parquet")
    text_units_path = os.path.join(output_folder, "create_final_text_units.parquet")
    relationships_path = os.path.join(output_folder, "create_final_relationships.parquet")

    try:
        entities = pd.read_parquet(entities_path)
        communities = pd.read_parquet(communities_path)
        community_reports = pd.read_parquet(community_reports_path)
        nodes = pd.read_parquet(nodes_path)
        text_units = pd.read_parquet(text_units_path)
        relationships = pd.read_parquet(relationships_path)
    except Exception as e:
        logging.error("Error loading index files: %s", e)
        raise

    if search_mode == 'local':
        print("using local mode to query")
        return await local_search(query, graphrag_config, entities, community_reports, nodes, text_units, relationships)
    elif search_mode == 'global':
        print("using global mode to query")
        return await global_search(query, graphrag_config, entities, communities, community_reports, nodes)
    else:
        logging.error(f"Error not support query mode, %s", search_mode)
        raise


async def global_search(query, graphrag_config, entities, communities, community_reports, nodes):
    try:
        response, context = await api.global_search(
            config=graphrag_config,
            nodes=nodes,
            entities=entities,
            communities=communities,
            community_reports=community_reports,
            community_level=2,
            dynamic_community_selection=False,
            response_type="Multiple Paragraphs",
            query=query,
        )
    except Exception as e:
        logging.error("Error during global search: %s", e)
        raise
    return response, context


async def local_search(query, graphrag_config, entities, community_reports, nodes, text_units, relationships):
    try:
        response, context = await api.local_search(
            config=graphrag_config,
            nodes=nodes,
            entities=entities,
            community_reports=community_reports,
            text_units=text_units,
            relationships=relationships,
            covariates=None,
            community_level=2,
            response_type="Multiple Paragraphs",
            query=query,
        )
    except Exception as e:
        logging.error("Error during local search: %s", e)
        raise
    return response, context


def get_chat_response(message: str, max_tokens: int = 100, temperature: float = 1.0, top_p: float = 0.9,
                      stream: bool = False) -> dict:
    """
    Send a chat request to the NebulaBlock API and get the model's response.

    Parameters:
    - message (str): The user message to send to the model.
    - model (str): The model name to use, default is "deepseek-ai/DeepSeek-R1-Distill-Llama-70B".
    - max_tokens (int): The maximum number of tokens to generate, default is 100.
    - temperature (float): The temperature controlling randomness, default is 1.0.
    - top_p (float): The top-p value controlling result diversity, default is 0.9.
    - stream (bool): Whether to use streaming responses, default is False.

    Returns:
    - dict: The response from the model.
    """

    LLM_MODEL = os.environ.get("LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://inference.nebulablock.com/v1")
    url = LLM_BASE_URL + "/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('LLM_API_KEY')}"
    }

    prompt = """Please summarize the following text while preserving its key points and main ideas. Condense it to a 
    maximum of 3500 characters. Maintain the core message and important details, but remove redundancies and less 
    critical information. \n\n"""

    data = {
        "messages": [
            {"role": "user", "content": prompt + message}
        ],
        "model": LLM_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stream": stream
    }

    try:
        # Send the request
        response = requests.post(url, headers=headers, json=data)

        # Check if the request was successful
        response.raise_for_status()  # Raise an exception for non-2xx status codes

        # Return the JSON response
        return response.json()

    except requests.exceptions.RequestException as e:
        # Handle request errors
        print(f"Error making request: {e}")
        return {"error": str(e)}


def has_files(directory: str) -> bool:
    return any(os.path.isfile(os.path.join(directory, f)) for f in os.listdir(directory))


def get_bool_env_var(var_name: str, default: bool = False) -> bool:
    var_value = os.environ.get(var_name, str(default))
    return var_value.lower() in ['true', '1', 't', 'y', 'yes']
