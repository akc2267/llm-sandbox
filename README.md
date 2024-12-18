# LLM Sandbox

LLM Sandbox is a FastAPI-based service that converts natural language commands into executable terminal commands using Ollama's language models. It provides a safe environment for executing system commands through a REST API.

## Features

- Natural language to terminal command conversion
- Support for Python, shell, and git commands
- Docker containerization
- Project workspace management
- Real-time command execution
- Integration with Ollama for LLM processing

## Prerequisites

- Docker and Docker Compose
- Ollama running locally with llama3.2 model
- Python 3.9+
- Node.js and npm (for frontend development)

## Setup

1. Install Ollama and the llama3.2 model:
```bash
# Install Ollama from https://ollama.ai/
ollama pull llama3.2
ollama serve
```

2. Clone the repository:
```bash
git clone [your-repo-url]
cd llm-sandbox
```

3. Create a `projects` directory:
```bash
mkdir projects
```

4. Build and start the services:
```bash
docker-compose up --build
```

The API will be available at `http://localhost:5001`

## API Endpoints

### Natural Language Command Execution
```http
POST /nl-execute
Content-Type: application/json

{
    "command": "create a new python file called hello.py that prints Hello World",
    "work_dir": "/app/projects"  // optional
}
```

### Direct Command Execution
```http
POST /execute
Content-Type: application/json

{
    "type": "python|shell|git",
    "commands": ["command1", "command2"],
    "work_dir": "/app/projects"  // optional
}
```

### List Projects
```http
GET /projects
```

### Check System Status
```http
GET /status
```

## Project Structure

```
llm-sandbox/
├── docker-compose.yml
├── Dockerfile
├── sandbox.py       # Main FastAPI application
├── projects/        # Workspace directory
└── README.md
```

## Docker Configuration

The service runs in a Docker container with the following configuration:
- Python 3.9 base image
- FastAPI for the REST API
- Volume mounts for Docker socket and project files
- Connection to host machine's Ollama service

## Example Usage

1. Create a Python file:
```bash
curl -X POST http://localhost:5001/nl-execute \
  -H "Content-Type: application/json" \
  -d '{"command": "create a new python file called hello.py that prints Hello World"}'
```

2. Initialize a git repository:
```bash
curl -X POST http://localhost:5001/nl-execute \
  -H "Content-Type: application/json" \
  -d '{"command": "initialize a new git repository and create a README file"}'
```

3. List projects:
```bash
curl http://localhost:5001/projects
```

## Security Considerations

- The sandbox executes commands in a containerized environment
- Limited to specific command types (python, shell, git)
- Projects directory is isolated
- Docker socket access is required for container management

## Development

1. Install development dependencies:
```bash
pip install fastapi uvicorn docker requests
```

2. Run locally:
```bash
uvicorn sandbox:app --reload --port 5000
```

## Error Handling

The API provides detailed error messages and logging for:
- Invalid commands
- LLM processing failures
- Command execution errors
- File system operations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

[Your chosen license]