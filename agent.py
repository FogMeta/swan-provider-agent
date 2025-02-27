import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile,HTTPException
import uvicorn
import graphrag_utils
from pathlib import Path
import asyncio
import nest_asyncio
from pydantic import BaseModel
from typing import Optional

# Apply nest_asyncio to solve event loop issues
nest_asyncio.apply()

# Configure logging.
pid = os.getpid()
logging.basicConfig(filename=f'process_server_{pid}.log', level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
# API routes
app = FastAPI(title="GraphRAG API", description="API for RAG operations")


@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    try:
        PROJECT_DIRECTORY = os.environ.get("WORK_DIRECTORY", "./ragtest")
        UPLOAD_DIR = Path(PROJECT_DIRECTORY) / "input"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        file_content = await file.read()
        file_location = UPLOAD_DIR / file.filename
        with open(file_location, "wb") as f:
            f.write(file_content)
        await graphrag_utils.update_index(PROJECT_DIRECTORY)
        return {"message": f"File '{file.filename}' has been uploaded successfully.",
                "file_location": str(file_location)}
    except Exception as e:
        return {"error": str(e)}


class QueryRequest(BaseModel):
    query: str
    mode: str = "global"


class Response(BaseModel):
    status: str
    data: Optional[str] = None
    message: Optional[str] = None


@app.post("/query", response_model=Response)
async def query(request: QueryRequest):
    try:
        PROJECT_DIRECTORY = os.environ.get("WORK_DIRECTORY", "./ragtest")
        response, context = await graphrag_utils.query_index(PROJECT_DIRECTORY, request.query, request.mode)
        print("response:", response)
        print("context:",context)
        return Response(status="success", data=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def process_question(query: str) -> str:
    """
    Process a user question:
      1. Update repository and convert markdown.
      2. Build (if needed) and query the GraphRAG index.
      3. Construct the prompt.
      4. Call Meta Llama3 to generate an answer.
    Returns the answer as a string.
    """
    PROJECT_DIRECTORY = os.environ.get("WORK_DIRECTORY","./ragtest")
    response, context = await graphrag_utils.query_index(PROJECT_DIRECTORY, query, 'global')
    return graphrag_utils.get_chat_response(response)['data']


async def handler_data():
    PROJECT_DIRECTORY = os.environ.get("WORK_DIRECTORY", "./ragtest")
    try:
        force_build = graphrag_utils.get_bool_env_var("FORCE_BUILD_GRAPH", default=False)
        await graphrag_utils.build_index(PROJECT_DIRECTORY, force_build)
    except Exception as e:
        logging.error("Stopping index processing. Exception: %s", e)
        return


async def main():
    asyncio.create_task(handler_data())
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()


def mask_string(s: str, visible_start: int, visible_end: int) -> str:
    return s[:visible_start] + '*' * (len(s) - visible_start - visible_end) + s[-visible_end:]


if __name__ == "__main__":
    # Load environment variables from .env file.
    load_dotenv()

    TEST_MODE = False
    FORCE_BUILD_GRAPH = False

    WORKING_DIR = os.environ.get("TEST_MODE")
    print(f"TEST_MODE: {TEST_MODE}")
    FORCE_BUILD_GRAPH = os.environ.get("FORCE_BUILD_GRAPH")
    print(f"FORCE_BUILD_GRAPH: {FORCE_BUILD_GRAPH}")
    WORKING_DIR = os.environ.get("WORK_DIRECTORY")
    print(f"WORKING_DIR: {WORKING_DIR}")
    REPO_URL = os.environ.get("REPO_URL")
    print(f"REPO_URL: {REPO_URL}")

    LLM_API_KEY = mask_string(os.environ.get("LLM_API_KEY"), 3, 3)
    print(f"LLM_API_KEY: {LLM_API_KEY}")
    LLM_MODEL = os.environ.get("LLM_MODEL")
    print(f"LLM_MODEL: {LLM_MODEL}")
    LLM_API_BASE = os.environ.get("LLM_API_BASE")
    print(f"LLM_API_BASE: {LLM_API_BASE}")

    EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL")
    print(f"EMBEDDING_MODEL: {EMBEDDING_MODEL}")
    EMBEDDING_API_KEY = mask_string(os.environ.get("EMBEDDING_API_KEY"), 3, 3)
    print(f"EMBEDDING_API_KEY: {EMBEDDING_API_KEY}")
    EMBEDDING_MODEL_BASE_URL = os.environ.get("EMBEDDING_API_BASE")
    print(f"EMBEDDING_MODEL_BASE_URL: {EMBEDDING_MODEL_BASE_URL}")

    asyncio.run(main())
