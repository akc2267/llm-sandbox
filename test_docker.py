import docker

# Use explicit socket path for OrbStack
client = docker.DockerClient(base_url='unix:///Users/alexandercheng/.orbstack/run/docker.sock')
print(client.version())