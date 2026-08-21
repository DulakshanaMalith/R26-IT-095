# Development Guide

This guide covers how to set up the backend environment and run the Exposía API locally. 

Because the backend and machine learning pipelines are fully isolated, you will configure a lightweight Python virtual environment strictly for inference.

## Prerequisites
* Python 3.10+
* Bash/Terminal access

## 1. Setup the Virtual Environment
Navigate to the root of the repository and create a virtual environment specifically inside the `backend/` directory:

```bash
# Create the virtual environment inside backend/
python3 -m venv backend/venv

# Activate it
source backend/venv/bin/activate

# Install the lightweight inference dependencies
pip install -r backend/requirements.txt
```

## 2. Environment Variables
Copy the template `.env` file and fill in any necessary API keys (like OpenAI for the LLM reviewer):

```bash
cp backend/.env.example backend/.env
```

## 3. Running the Server
You can start the backend using the provided bash script. This script automatically routes output logs and binds to port `9000`.

```bash
# Execute from the root directory
bash backend/start_backend.sh
```

### Checking Logs
Because `start_backend.sh` runs the Uvicorn server in the background and redirects output, you can monitor the application boot sequence and API requests by tailing the log file:

```bash
tail -f backend/logs/backend.combined.log
```

## 4. Development Workflow
The API is structured modularly:
* **To add a new endpoint**: Create or edit the relevant domain file in `backend/src/api/routers/`.
* **To add a new data payload**: Define the Pydantic schema in `backend/src/api/schemas.py`.
* **To update business logic**: Modify the shared service helpers in `backend/src/api/services/core_logic.py`.
