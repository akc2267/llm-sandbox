import docker
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
import os
import subprocess
from typing import List, Optional
from enum import Enum

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class CommandType(str, Enum):
    PYTHON = "python"
    SHELL = "shell"
    GIT = "git"

class CommandRequest(BaseModel):
    type: CommandType
    commands: List[str]
    work_dir: Optional[str] = "/app/projects"

def init_docker_client():
    try:
        socket_path = os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')
        logger.info(f"Connecting to Docker at: {socket_path}")
        client = docker.DockerClient(base_url=socket_path)
        version = client.version()
        logger.info(f"Successfully connected to Docker at {socket_path}")
        return client, socket_path
    except Exception as e:
        logger.error(f"Failed to connect to Docker: {str(e)}")
        raise

try:
    client, docker_socket = init_docker_client()
except Exception as e:
    logger.error(f"Failed to initialize Docker client: {str(e)}")
    client, docker_socket = None, None

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