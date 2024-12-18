import docker
import sys
import os

def test_docker_connection():
    # Print environment info
    print(f"Current user: {os.getuid()}")
    print(f"Docker socket path exists: {os.path.exists('/Users/alexandercheng/.orbstack/run/docker.sock')}")
    
    try:
        # Try with explicit socket path
        client = docker.DockerClient(base_url='unix:///Users/alexandercheng/.orbstack/run/docker.sock')
        version = client.version()
        print("Successfully connected to Docker!")
        print(f"Docker version: {version['Version']}")
        
        # Try to run a test container
        print("\nTrying to run hello-world container...")
        output = client.containers.run("hello-world", remove=True)
        print(f"Container output:\n{output.decode('utf-8')}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print(f"Error type: {type(e)}")
        
if __name__ == "__main__":
    test_docker_connection()