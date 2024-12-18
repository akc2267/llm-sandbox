import docker
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
import os
import subprocess
import requests
from typing import List, Optional
from enum import Enum
from fastapi.middleware.cors import CORSMiddleware
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastAPI app instance first
app = FastAPI()

# Then add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CommandType(str, Enum):
    PYTHON = "python"
    SHELL = "shell"
    GIT = "git"

class CommandRequest(BaseModel):
    type: CommandType
    commands: List[str]
    work_dir: Optional[str] = "/app/projects"

class NLCommandRequest(BaseModel):
    command: str
    work_dir: Optional[str] = "/app/projects"

class CommandResponse(BaseModel):
    interpreted_commands: List[str]
    command_type: CommandType
    status: str
    output: str

# Initialize docker client
try:
    socket_path = os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')
    logger.info(f"Connecting to Docker at: {socket_path}")
    client = docker.DockerClient(base_url=socket_path)
    docker_socket = socket_path
    version = client.version()
    logger.info(f"Successfully connected to Docker at {socket_path}")
except Exception as e:
    logger.error(f"Failed to connect to Docker: {str(e)}")
    client = None
    docker_socket = None

def get_command_interpretation(natural_command: str) -> dict:
    """Use Ollama to interpret natural language commands into terminal commands"""
    
    prompt = f"""Given this natural language command: '{natural_command}'
    Convert it into appropriate terminal commands.
    You must choose exactly ONE command_type from these options: "shell", "python", or "git".
    Respond with only valid JSON in this format:
    {{
        "command_type": "shell",  // Must be exactly "shell", "python", or "git"
        "commands": ["command1", "command2"],
        "explanation": "Brief explanation of what these commands will do"
    }}
    """
    
    try:
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "system": "You are a command line assistant that converts natural language into terminal commands. Always respond with valid JSON only. For command_type, always choose exactly one of: 'shell', 'python', or 'git'.",
                "stream": False
            }
        )
        
        if response.status_code != 200:
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500, detail=f"Ollama API error: {response.text}")
            
        try:
            result = response.json()
            
            # Extract the actual JSON response
            if 'response' in result:
                # Clean up the response - sometimes LLMs include markdown code blocks
                json_str = result['response'].strip()
                if json_str.startswith('```json'):
                    json_str = json_str[7:]
                if json_str.startswith('```'):
                    json_str = json_str[3:]
                if json_str.endswith('```'):
                    json_str = json_str[:-3]
                json_str = json_str.strip()
                
                command_data = json.loads(json_str)
            else:
                command_data = result
            
            # Validate and fix command_type
            if 'command_type' not in command_data:
                raise ValueError("Missing command_type in response")
                
            # Ensure command_type is valid
            command_type = command_data['command_type'].lower().strip()
            if command_type not in ['shell', 'python', 'git']:
                # Try to intelligently choose the correct type based on commands
                commands = command_data.get('commands', [])
                if any(cmd.startswith('python') or cmd.endswith('.py') for cmd in commands):
                    command_type = 'python'
                elif any(cmd.startswith('git') for cmd in commands):
                    command_type = 'git'
                else:
                    command_type = 'shell'
                    
            command_data['command_type'] = command_type
            
            # For Python files, adjust the command format
            if command_type == 'python' and 'hello.py' in natural_command.lower():
                command_data['commands'] = [
                    f"echo 'print(\"Hello World\")' > hello.py"
                ]
            
            # Validate other required fields
            if 'commands' not in command_data or not command_data['commands']:
                raise ValueError("Missing or empty commands in response")
            if 'explanation' not in command_data:
                command_data['explanation'] = "Executing the specified commands"
                
            return command_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Ollama response as JSON: {result.get('response', '')}")
            logger.error(str(e))
            raise HTTPException(status_code=500, detail="Failed to parse command interpretation")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to Ollama: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing command: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process command: {str(e)}")

@app.get("/status")
async def get_status():
    """Get detailed status of Docker connection"""
    if not client:
        return {
            "docker_connected": False,
            "error": "Docker client not initialized"
        }
    
    try:
        file_path = docker_socket.replace('unix://', '') if docker_socket else '/var/run/docker.sock'
        
        status = {
            "docker_connected": True,
            "socket_path": docker_socket,
            "socket_exists": os.path.exists(file_path),
            "version": client.version()
        }
        
        if os.path.exists(file_path):
            status["permissions"] = oct(os.stat(file_path).st_mode)[-3:]
        
        containers = client.containers.list()
        status["containers_accessible"] = True
        status["active_containers"] = len(containers)
        
        # Add projects directory status
        projects_dir = "/app/projects"
        status["projects_dir_exists"] = os.path.exists(projects_dir)
        if os.path.exists(projects_dir):
            status["projects_dir_contents"] = os.listdir(projects_dir)
        
        return status
    except Exception as e:
        return {
            "docker_connected": False,
            "error": str(e)
        }

@app.post("/execute")
async def execute_commands(request: CommandRequest):
    """Execute commands in a container based on type"""
    if not client:
        raise HTTPException(status_code=500, detail="Docker client not initialized")
    
    logger.info(f"Executing {request.type} commands:\n{request.commands}")
    
    try:
        command_str = " && ".join(request.commands)
        
        # Ensure projects directory exists
        os.makedirs("/app/projects", exist_ok=True)
        
        # Execute commands directly in the host container
        if request.type == CommandType.PYTHON:
            result = subprocess.run(
                ["python", "-c", command_str],
                cwd=request.work_dir,
                capture_output=True,
                text=True
            )
        else:  # Shell or Git commands
            result = subprocess.run(
                ["/bin/bash", "-c", command_str],
                cwd=request.work_dir,
                capture_output=True,
                text=True
            )
        
        output = result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
        
        return {
            "status": "success" if result.returncode == 0 else "error",
            "output": output
        }
        
    except Exception as e:
        logger.exception("Error executing commands")
        return {
            "status": "error",
            "output": str(e)
        }

@app.post("/nl-execute")
async def nl_execute_endpoint(request: NLCommandRequest):
    """Execute natural language commands"""
    try:
        # Get command interpretation from Ollama
        interpretation = get_command_interpretation(request.command)
        
        # Create command request from interpretation
        cmd_request = CommandRequest(
            type=CommandType(interpretation["command_type"]),
            commands=interpretation["commands"],
            work_dir=request.work_dir
        )
        
        # Execute the interpreted commands
        result = await execute_commands(cmd_request)
        
        return CommandResponse(
            interpreted_commands=interpretation["commands"],
            command_type=cmd_request.type,
            status=result["status"],
            output=f"Interpretation: {interpretation['explanation']}\n\nOutput: {result['output']}"
        )
        
    except Exception as e:
        logger.exception("Error processing natural language command")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/projects")
async def list_projects():
    """List contents of the projects directory"""
    try:
        projects_path = "/app/projects"
        os.makedirs(projects_path, exist_ok=True)
        items = os.listdir(projects_path)
        return {
            "status": "success",
            "contents": items
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }