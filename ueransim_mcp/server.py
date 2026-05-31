"""UERANSIM MCP Server - UERANSIM Tool using FastMCP with structured output"""

import subprocess
import sys
import re
import random
import string
import time
import os
from typing import List, Optional
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("UERANSIM MCP Server")
print("UERANSIM MCP Server initialized", file=sys.stderr)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_container_runtime():
    """Get Docker as the container runtime.

    Returns:
        str: "docker"
    """
    try:
        result = subprocess.run(["docker", "version"], capture_output=True, text=True)
        if result.returncode == 0:
            return "docker"
        else:
            print(f"docker error: {result.stderr}", file=sys.stderr)
            raise RuntimeError("Docker is not available")
    except FileNotFoundError:
        print("docker not found", file=sys.stderr)
        raise RuntimeError("Docker is not installed or not in PATH")

def generate_random_suffix(length: int = 4) -> str:
    """Generate a random alphanumeric suffix for container names.
    
    Args:
        length: Length of the suffix (default: 4)
        
    Returns:
        Random alphanumeric string
    """
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def run_container_command(command: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a Docker command with proper environment setup.

    Args:
        command: List of command parts
        **kwargs: Additional arguments to pass to subprocess.run

    Returns:
        CompletedProcess: Result of the command execution
    """
    env = os.environ.copy()

    if 'PATH' not in env:
        env['PATH'] = '/usr/local/bin:/usr/bin:/bin'
    else:
        path_dirs = env['PATH'].split(':')
        for directory in ['/usr/local/bin', '/usr/bin', '/bin']:
            if directory not in path_dirs:
                env['PATH'] = f"{directory}:{env['PATH']}"

    if 'env' not in kwargs:
        kwargs['env'] = env

    return subprocess.run(command, **kwargs)

def detect_image_os(image_name: str) -> str:
    """Detect the operating system of a Docker image."""
    container_runtime = get_container_runtime()

    # Run the container and check /etc/os-release
    os_release_cmd = [container_runtime, "run", "--rm", image_name, "cat", "/etc/os-release"]
    result = run_container_command(os_release_cmd, capture_output=True, text=True)

    if result.returncode == 0:
        output = result.stdout.lower()
        if "alpine" in output:
            return "alpine"
        elif "ubuntu" in output:
            return "ubuntu"
    return "unknown"

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_ip(ip: str) -> bool:
    """Validate that a string is a valid IP address.
    
    Args:
        ip: The IP address to validate
        
    Returns:
        True if valid, otherwise raises ValueError
        
    Raises:
        ValueError: If the IP address is not valid
    """
    ip_pattern = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
    match = ip_pattern.match(ip)
    
    if not match:
        raise ValueError(f"Invalid IP format: {ip}. Must be in format x.x.x.x with numbers only.")
    
    # Check that each octet is between 0-255
    for octet in match.groups():
        if int(octet) > 255:
            raise ValueError(f"Invalid IP: {ip}. Each octet must be between 0-255.")
    
    return True

def validate_container_id(container_id: str) -> bool:
    """Validate that a container identifier is valid.
    
    Args:
        container_id: The container ID to validate
        
    Returns:
        True if valid, otherwise raises ValueError
        
    Raises:
        ValueError: If the container ID is not valid
    """
    # Docker container IDs are hexadecimal strings
    if not re.match(r'^[0-9a-fA-F]+$', container_id):
        raise ValueError(f"Invalid container ID: {container_id}. Must be a hexadecimal string.")
    
    return True

def validate_container_name(name: str, prefix: Optional[str] = None) -> bool:
    """Validate that a container name is valid.
    
    Args:
        name: The container name to validate
        prefix: Optional prefix that the name should have
        
    Returns:
        True if valid, otherwise raises ValueError
        
    Raises:
        ValueError: If the container name is not valid
    """
    # Check for empty name
    if not name:
        raise ValueError("Container name cannot be empty.")
    
    # Container names should contain only a-z, A-Z, 0-9, _ and -
    pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
    if not pattern.match(name):
        raise ValueError(f"Invalid container name: {name}. Use only letters, numbers, underscores and hyphens.")
    
    # Check for prefix if specified
    if prefix:
        if not name.startswith(f"{prefix}-"):
            raise ValueError(f"Container name must start with '{prefix}-', got: {name}")
    
    return True

def validate_existing_container(container_id_or_name: str) -> bool:
    """Validate that a container exists and is accessible.
    
    Args:
        container_id_or_name: The container ID or name to validate
        
    Returns:
        True if valid and exists, otherwise raises ValueError
        
    Raises:
        ValueError: If the container doesn't exist or is not accessible
    """
    try:
        # First validate the format
        if re.match(r'^[0-9a-fA-F]+$', container_id_or_name) and (len(container_id_or_name) == 12 or len(container_id_or_name) == 64):
            validate_container_id(container_id_or_name)
        else:
            # Basic name validation without prefix since we don't know the type
            if not re.match(r'^[a-zA-Z0-9_-]+$', container_id_or_name):
                raise ValueError(f"Invalid container name format: {container_id_or_name}")
        
        # Check if container exists using docker inspect
        container_runtime = get_container_runtime()
        inspect_cmd = [container_runtime, "inspect", container_id_or_name]
        
        result = run_container_command(inspect_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise ValueError(f"Container {container_id_or_name} not found or not accessible")
        
        return True
        
    except subprocess.SubprocessError as e:
        raise ValueError(f"Failed to validate container {container_id_or_name}: {str(e)}")
    except FileNotFoundError:
        raise ValueError("Container runtime (Docker) not found")

# ============================================================================
# PYDANTIC MODELS FOR STRUCTURED OUTPUT
# ============================================================================

# gNB Models
class GnbConfiguration(BaseModel):
    """gNB configuration structure."""
    link_ip: str = Field(description="Link interface IP address")
    ngap_ip: str = Field(description="NGAP interface IP address") 
    gtp_ip: str = Field(description="GTP interface IP address")
    amf_address: str = Field(description="AMF IP address")
    amf_port: str = Field(description="AMF port")

class GnbContainer(BaseModel):
    """gNB container information structure."""
    id: str = Field(description="Container ID")
    name: str = Field(description="Container name")
    status: str = Field(description="Container status")
    created: str = Field(description="Creation timestamp")

class GnbCreateResponse(BaseModel):
    """gNB creation response structure."""
    status: str = Field(description="Operation status")
    container_id: str = Field(description="Created container ID")
    container_name: str = Field(description="Container name")
    configuration: GnbConfiguration = Field(description="Container configuration")
    message: Optional[str] = Field(description="Additional message", default=None)

class GnbListResponse(BaseModel):
    """gNB list response structure."""
    status: str = Field(description="Operation status")
    containers: List[GnbContainer] = Field(description="List of gNB containers")
    count: int = Field(description="Number of containers")
    message: Optional[str] = Field(description="Additional message", default=None)

class GnbOperationResponse(BaseModel):
    """Generic gNB operation response structure."""
    status: str = Field(description="Operation status (success/error)")
    message: str = Field(description="Operation message")
    container: Optional[str] = Field(description="Container ID or name", default=None)
    logs: Optional[str] = Field(description="Container logs", default=None)

# UE Models
class UeConfiguration(BaseModel):
    """UE configuration structure."""
    gnb_search_list: str = Field(description="gNB search list IP addresses")

class UeContainer(BaseModel):
    """UE container information structure."""
    id: str = Field(description="Container ID")
    name: str = Field(description="Container name")
    status: str = Field(description="Container status")
    created: str = Field(description="Creation timestamp")

class UeCreateResponse(BaseModel):
    """UE creation response structure."""
    status: str = Field(description="Operation status")
    container_id: str = Field(description="Created container ID")
    container_name: str = Field(description="Container name")
    configuration: UeConfiguration = Field(description="Container configuration")
    message: Optional[str] = Field(description="Additional message", default=None)

class UeListResponse(BaseModel):
    """UE list response structure."""
    status: str = Field(description="Operation status")
    containers: List[UeContainer] = Field(description="List of UE containers")
    count: int = Field(description="Number of containers")
    message: Optional[str] = Field(description="Additional message", default=None)

class UeOperationResponse(BaseModel):
    """Generic UE operation response structure."""
    status: str = Field(description="Operation status (success/error)")
    message: str = Field(description="Operation message")
    container: Optional[str] = Field(description="Container ID or name", default=None)
    logs: Optional[str] = Field(description="Container logs", default=None)


# ============================================================================
# GNB TOOLS
# ============================================================================

@mcp.tool()
def create_gnb(amf_address: str = "127.0.0.5", 
               amf_port: str = "38412", 
               container_name: Optional[str] = None) -> GnbCreateResponse:
    """Create a new gNB container.
    
    Args:
        amf_address: AMF IP address
        amf_port: AMF port
        container_name: Optional container name
    
    Returns:
        GnbCreateResponse: Information about the new container
    """
    try:
        # Validate AMF IP parameter
        validate_ip(amf_address)
        
        # Get container runtime (docker)
        container_runtime = get_container_runtime()
        
        # Create container command
        terminal_command = [container_runtime, "run", "-d"]

        # Add network configuration to avoid port conflicts
        # terminal_command.extend(["--network", "host"])

        # Add name if specified, otherwise generate one
        if container_name:
            validate_container_name(container_name, "gnb")
            terminal_command.extend(["--name", container_name])
        else:
            container_name = f"gnb-{generate_random_suffix()}"
            terminal_command.extend(["--name", container_name])

        # Add the Docker image name
        terminal_command.append("ghcr.io/apelgroup/mcp-ueransim-new/ueransim-gnb:latest")
        
        # Execute command to create container
        result = run_container_command(terminal_command, capture_output=True, text=True)

        if result.returncode != 0:
            return GnbCreateResponse(
                status="error",
                container_id="",
                container_name="",
                configuration=GnbConfiguration(
                    link_ip="",
                    ngap_ip="",
                    gtp_ip="",
                    amf_address=amf_address,
                    amf_port=amf_port
                ),
                message=result.stderr
            )
        
        container_id = result.stdout.strip()
        
        # Step 1: Get container IP using docker inspect
        inspect_command = [
            container_runtime, "inspect", "-f", 
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", 
            container_id
        ]
        inspect_result = run_container_command(inspect_command, capture_output=True, text=True)
        
        if inspect_result.returncode != 0:
            return GnbCreateResponse(
                status="error",
                container_id=container_id,
                container_name=container_name,
                configuration=GnbConfiguration(
                    link_ip="",
                    ngap_ip="",
                    gtp_ip="",
                    amf_address=amf_address,
                    amf_port=amf_port
                ),
                message=f"Failed to get container IP: {inspect_result.stderr}"
            )
        
        container_ip = inspect_result.stdout.strip()
        
        # Step 2: Update configuration file with container IP and AMF settings
        # Update linkIp with container IP
        link_cmd = [
            container_runtime, "exec", container_id,
            "sed", "-i", f"s/linkIp: .*/linkIp: {container_ip}/",
            "/etc/ueransim/open5gs-gnb.yaml"
        ]
        link_result = run_container_command(link_cmd, capture_output=True, text=True)
        
        if link_result.returncode != 0:
            return GnbCreateResponse(
                status="error",
                container_id=container_id,
                container_name=container_name,
                configuration=GnbConfiguration(
                    link_ip=container_ip,
                    ngap_ip=container_ip,
                    gtp_ip=container_ip,
                    amf_address=amf_address,
                    amf_port=amf_port
                ),
                message=f"Failed to update linkIp: {link_result.stderr}"
            )
        
        # Update ngapIp with container IP
        ngap_cmd = [
            container_runtime, "exec", container_id,
            "sed", "-i", f"s/ngapIp: .*/ngapIp: {container_ip}/",
            "/etc/ueransim/open5gs-gnb.yaml"
        ]
        ngap_result = run_container_command(ngap_cmd, capture_output=True, text=True)
        
        if ngap_result.returncode != 0:
            return GnbCreateResponse(
                status="error",
                container_id=container_id,
                container_name=container_name,
                configuration=GnbConfiguration(
                    link_ip=container_ip,
                    ngap_ip=container_ip,
                    gtp_ip=container_ip,
                    amf_address=amf_address,
                    amf_port=amf_port
                ),
                message=f"Failed to update ngapIp: {ngap_result.stderr}"
            )
        
        # Update gtpIp with container IP
        gtp_cmd = [
            container_runtime, "exec", container_id,
            "sed", "-i", f"s/gtpIp: .*/gtpIp: {container_ip}/",
            "/etc/ueransim/open5gs-gnb.yaml"
        ]
        gtp_result = run_container_command(gtp_cmd, capture_output=True, text=True)
        
        if gtp_result.returncode != 0:
            return GnbCreateResponse(
                status="error",
                container_id=container_id,
                container_name=container_name,
                configuration=GnbConfiguration(
                    link_ip=container_ip,
                    ngap_ip=container_ip,
                    gtp_ip=container_ip,
                    amf_address=amf_address,
                    amf_port=amf_port
                ),
                message=f"Failed to update gtpIp: {gtp_result.stderr}"
            )
        
        # Update AMF address (matches the "- address: ..." line inside amfConfigs)
        amf_cmd = [
            container_runtime, "exec", container_id,
            "sed", "-i", f"s/- address: .*/- address: {amf_address}/",
            "/etc/ueransim/open5gs-gnb.yaml"
        ]
        amf_result = run_container_command(amf_cmd, capture_output=True, text=True)
        
        if amf_result.returncode != 0:
            return GnbCreateResponse(
                status="error",
                container_id=container_id,
                container_name=container_name,
                configuration=GnbConfiguration(
                    link_ip=container_ip,
                    ngap_ip=container_ip,
                    gtp_ip=container_ip,
                    amf_address=amf_address,
                    amf_port=amf_port
                ),
                message=f"Failed to update AMF address: {amf_result.stderr}"
            )
        
        return GnbCreateResponse(
            status="success",
            container_id=container_id,
            container_name=container_name,
            configuration=GnbConfiguration(
                link_ip=container_ip,
                ngap_ip=container_ip,
                gtp_ip=container_ip,
                amf_address=amf_address,
                amf_port=amf_port
            )
        )
    except ValueError as e:
        # Validation errors from validate_ip() or validate_container_name()
        return GnbCreateResponse(
            status="error",
            container_id="",
            container_name="",
            configuration=GnbConfiguration(
                link_ip="",
                ngap_ip="",
                gtp_ip="",
                amf_address=amf_address,
                amf_port=amf_port
            ),
            message=str(e)
        )
    except Exception as e:
        # Handle container creation failures and other unexpected errors
        error_msg = str(e)
        if "not found" in error_msg.lower():
            error_msg = "Container runtime (Docker) not found or not accessible"
        elif "permission" in error_msg.lower():
            error_msg = f"Permission denied: {error_msg}"
        
        return GnbCreateResponse(
            status="error",
            container_id="",
            container_name="",
            configuration=GnbConfiguration(
                link_ip="",
                ngap_ip="",
                gtp_ip="",
                amf_address=amf_address,
                amf_port=amf_port
            ),
            message=error_msg
        )


@mcp.tool()
def list_gnbs() -> GnbListResponse:
    """List all gNB containers.
    
    Returns:
        GnbListResponse: List of gNB containers
    """
    try:
        container_runtime = get_container_runtime()
        terminal_command = [
            container_runtime, "ps", "-a", "--filter", "name=gnb-", 
            "--format", "{{.ID}}|{{.Names}}|{{.Status}}|{{.CreatedAt}}"
        ]

        result = run_container_command(terminal_command, capture_output=True, text=True)

        if result.returncode != 0:
            return GnbListResponse(
                status="error",
                containers=[],
                count=0,
                message=result.stderr
            )
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                id, name, status, created = line.split('|', 3)
                containers.append(GnbContainer(
                    id=id,
                    name=name,
                    status=status,
                    created=created
                ))
        
        return GnbListResponse(
            status="success",
            containers=containers,
            count=len(containers)
        )
    except Exception as e:
        # Handle all errors with smart error message detection
        error_msg = str(e)
        if "not found" in error_msg.lower() or "command not found" in error_msg.lower():
            error_msg = "Container runtime (Docker) not found"
        elif "permission" in error_msg.lower():
            error_msg = f"Permission denied: {error_msg}"
        elif "invalid" in error_msg.lower() or "format" in error_msg.lower():
            error_msg = f"Output parsing error: {error_msg}"
        
        return GnbListResponse(
            status="error",
            containers=[],
            count=0,
            message=error_msg
        )


@mcp.tool()
def delete_gnb(container_id_or_name: str) -> GnbOperationResponse:
    """Delete a gNB container.
    
    Args:
        container_id_or_name: Container ID or name to delete
        
    Returns:
        GnbOperationResponse: Deletion status
    """
    try:
        # Check if it's ID or name
        if re.match(r'^[0-9a-fA-F]+$', container_id_or_name) and (len(container_id_or_name) == 12 or len(container_id_or_name) == 64):
            validate_container_id(container_id_or_name)
        else:
            validate_container_name(container_id_or_name, "gnb")
            
        # Get container runtime
        container_runtime = get_container_runtime()

        # Stop and remove container
        stop_cmd = [container_runtime, "stop", container_id_or_name]
        result = run_container_command(stop_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return GnbOperationResponse(
                status="error",
                message=f"Failed to stop container: {result.stderr}",
                container=container_id_or_name
            )

        rm_cmd = [container_runtime, "rm", container_id_or_name]
        result = run_container_command(rm_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return GnbOperationResponse(
                status="error", 
                message=f"Failed to remove container: {result.stderr}",
                container=container_id_or_name
            )
        
        return GnbOperationResponse(
            status="success", 
            message=f"Container {container_id_or_name} successfully deleted",
            container=container_id_or_name
        )
    except ValueError as e:
        # Validation errors from validate_container_id() or validate_container_name()
        return GnbOperationResponse(
            status="error",
            message=str(e),
            container=container_id_or_name
        )
    except Exception as e:
        # Handle container operations and other errors
        error_msg = str(e)
        if "not found" in error_msg.lower():
            error_msg = f"Container {container_id_or_name} not found"
        elif "permission" in error_msg.lower():
            error_msg = f"Permission denied: {error_msg}"
        elif "already stopped" in error_msg.lower():
            error_msg = f"Container {container_id_or_name} is already stopped"
        
        return GnbOperationResponse(
            status="error",
            message=error_msg,
            container=container_id_or_name
        )


@mcp.tool()
def get_gnb_logs(container_id_or_name: str, lines: int = 100) -> GnbOperationResponse:
    """Get logs from a gNB container.
    
    Args:
        container_id_or_name: Container ID or name
        lines: Number of lines to retrieve (default: 100)
        
    Returns:
        GnbOperationResponse: Container logs
    """
    try:
        # Check if it's ID or name
        if re.match(r'^[0-9a-fA-F]+$', container_id_or_name) and (len(container_id_or_name) == 12 or len(container_id_or_name) == 64):
            validate_container_id(container_id_or_name)
        else:
            validate_container_name(container_id_or_name, "gnb")
        
        # Get container runtime
        container_runtime = get_container_runtime()

        # Execute command to retrieve logs
        terminal_command = [container_runtime, "logs", f"--tail={lines}", container_id_or_name]
        result = run_container_command(terminal_command, capture_output=True, text=True)

        if result.returncode != 0:
            return GnbOperationResponse(
                status="error",
                message=result.stderr,
                container=container_id_or_name
            )
        
        return GnbOperationResponse(
            status="success",
            message="Logs retrieved successfully",
            container=container_id_or_name,
            logs=result.stdout
        )
    except Exception as e:
        return GnbOperationResponse(
            status="error",
            message=str(e),
            container=container_id_or_name
        )


@mcp.tool()
def attach_gnb_to_core(container_id_or_name: str, amf_address: str = "127.0.0.5") -> GnbOperationResponse:
    """Attach a gNB container to the network core.
    
    Args:
        container_id_or_name: gNB container ID or name
        amf_address: AMF IP address (default: 127.0.0.5)
        
    Returns:
        GnbOperationResponse: Connection status
    """
    try:
        # Validate parameters
        validate_ip(amf_address)
        
        # Check if it's ID or name
        if re.match(r'^[0-9a-fA-F]+$', container_id_or_name) and (len(container_id_or_name) == 12 or len(container_id_or_name) == 64):
            validate_container_id(container_id_or_name)
        else:
            validate_container_name(container_id_or_name, "gnb")
        
        # Get container runtime
        container_runtime = get_container_runtime()
        
        # Command to change AMF address in amfConfigs section
        amf_cmd = [
            container_runtime, "exec", container_id_or_name, 
            "sed", "-i", f"s/- address: .*/- address: {amf_address}/", 
            "/etc/ueransim/open5gs-gnb.yaml"
        ]
        result_amf = run_container_command(amf_cmd, capture_output=True, text=True)
        
        if result_amf.returncode != 0:
            return GnbOperationResponse(
                status="error",
                message=f"Failed to update AMF address: {result_amf.stderr}",
                container=container_id_or_name
            )
        
        # Start nr-gnb process with the updated configuration using nohup for background execution with logs
        gnb_exec_cmd = [
            container_runtime, "exec", "-d", container_id_or_name, "sh", "-c",
            "nohup /usr/local/bin/nr-gnb -c /etc/ueransim/open5gs-gnb.yaml > /proc/1/fd/1 2>&1 &"
        ]
        gnb_exec_result = run_container_command(gnb_exec_cmd, capture_output=True, text=True)
        
        if gnb_exec_result.returncode != 0:
            return GnbOperationResponse(
                status="error",
                message=f"Failed to start nr-gnb process: {gnb_exec_result.stderr}",
                container=container_id_or_name
            )
        
        # Wait a moment for process to start
        time.sleep(2)
        
        # Check if process is running
        gnb_status_cmd = [container_runtime, "exec", container_id_or_name, "sh", "-c", "pgrep -f nr-gnb && echo 'gNB process is running' || echo 'gNB process not found'"]
        gnb_status_result = run_container_command(gnb_status_cmd, capture_output=True, text=True)
        
        process_status = "Process started successfully" if gnb_status_result.returncode == 0 and "process is running" in gnb_status_result.stdout else "Process may not be running"
        
        return GnbOperationResponse(
            status="success",
            message=f"Container {container_id_or_name} successfully connected to core with AMF address {amf_address}. nr-gnb process started. {process_status}",
            container=container_id_or_name,
            logs=gnb_status_result.stdout if gnb_status_result.returncode == 0 else None
        )
    except Exception as e:
        return GnbOperationResponse(
            status="error",
            message=str(e),
            container=container_id_or_name
        )


# ============================================================================
# COMMON TOOLS
# ============================================================================

@mcp.tool()
def inspect_container_ip(container_id_or_name: str) -> GnbOperationResponse:
    """Inspect container IP address using docker inspect command.
    
    Args:
        container_id_or_name: Container ID or name to inspect
        
    Returns:
        GnbOperationResponse: Container IP information
    """
    try:
        # Validate that container exists and is accessible
        validate_existing_container(container_id_or_name)
        
        # Get container runtime
        container_runtime = get_container_runtime()
        
        # Use docker inspect to get container IP
        inspect_cmd = [
            container_runtime, "inspect", "-f", 
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", 
            container_id_or_name
        ]
        
        result = run_container_command(inspect_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return GnbOperationResponse(
                status="error",
                message=f"Failed to inspect container: {result.stderr}",
                container=container_id_or_name
            )
        
        container_ip = result.stdout.strip()
        
        # Check if IP was found
        if not container_ip:
            return GnbOperationResponse(
                status="error",
                message=f"No IP address found for container {container_id_or_name}",
                container=container_id_or_name
            )
        
        return GnbOperationResponse(
            status="success",
            message=f"Container {container_id_or_name} IP address: {container_ip}",
            container=container_id_or_name,
            logs=container_ip
        )
        
    except ValueError as e:
        # Validation errors from validate_existing_container()
        return GnbOperationResponse(
            status="error",
            message=str(e),
            container=container_id_or_name
        )
    except Exception as e:
        # Handle container operations and other errors
        error_msg = str(e)
        if "not found" in error_msg.lower():
            error_msg = f"Container {container_id_or_name} not found or not accessible"
        elif "permission" in error_msg.lower():
            error_msg = f"Permission denied: {error_msg}"
        elif "command not found" in error_msg.lower():
            error_msg = "Container runtime (Docker) not found"
        
        return GnbOperationResponse(
            status="error",
            message=error_msg,
            container=container_id_or_name
        )


# ============================================================================
# UE TOOLS
# ============================================================================

@mcp.tool()
def create_ue(gnb_search_list: str = "127.0.0.1", container_name: Optional[str] = None) -> UeCreateResponse:
    """Create a new UE container.
    
    Args:
        gnb_search_list: gNB search list IP address (or "auto" to use first available gNB)
        container_name: Optional container name
    
    Returns:
        UeCreateResponse: Information about the new container
    """
    try:
        # If gnb_search_list is "auto", find the first available gNB container
        if gnb_search_list == "auto":
            # Get list of gNB containers
            gnb_list = list_gnbs()
            if gnb_list.status == "success" and gnb_list.count > 0:
                # Get IP of the first gNB container
                first_gnb = gnb_list.containers[0]
                ip_result = inspect_container_ip(first_gnb.name)
                if ip_result.status == "success":
                    gnb_search_list = ip_result.logs
                    print(f"Auto-detected gNB IP: {gnb_search_list}", file=sys.stderr)
                else:
                    gnb_search_list = "127.0.0.1"  # fallback
                    print(f"Failed to get gNB IP, using fallback: {gnb_search_list}", file=sys.stderr)
            else:
                gnb_search_list = "127.0.0.1"  # fallback
                print(f"No gNB containers found, using fallback: {gnb_search_list}", file=sys.stderr)
        
        # Validate parameters
        validate_ip(gnb_search_list)
        
        # Get container runtime (docker)
        container_runtime = get_container_runtime()
        
        # Check if the image is Alpine or Ubuntu based
        os_type = detect_image_os("ghcr.io/apelgroup/mcp-ueransim-new/ueransim-ue:latest")
        is_alpine = os_type == "alpine"

        print(f"Detected image type: {'Alpine' if is_alpine else 'Ubuntu'}", file=sys.stderr)
        
        # Create container command
        terminal_command = [container_runtime, "run", "-d"]
        
        # Add name if specified, otherwise generate one
        if container_name:
            validate_container_name(container_name, "ue")
            terminal_command.extend(["--name", container_name])
        else:
            container_name = f"ue-{generate_random_suffix()}"
            terminal_command.extend(["--name", container_name])
        
        # Add required capabilities and devices for UE container based on image type
        if is_alpine:
            # Alpine image: use --privileged instead of --device /dev/net/tun
            terminal_command.extend([
                "--privileged",
                "--cap-add=NET_ADMIN",
                "--network", "host",
                "ghcr.io/apelgroup/mcp-ueransim-new/ueransim-ue:latest"
            ])
        else:
            # Ubuntu image: use --device /dev/net/tun
            terminal_command.extend([
                "--cap-add=NET_ADMIN",
                "--device", "/dev/net/tun",
                "--network", "host",
                "ghcr.io/apelgroup/mcp-ueransim-new/ueransim-ue:latest"
            ])
        
        print(f"Container creation command: {' '.join(terminal_command)}", file=sys.stderr)
        
        # Execute command
        result = run_container_command(terminal_command, capture_output=True, text=True)
        
        if result.returncode != 0:
            return UeCreateResponse(
                status="error",
                container_id="",
                container_name="",
                configuration=UeConfiguration(gnb_search_list=gnb_search_list),
                message=result.stderr
            )
        
        container_id = result.stdout.strip()
        
        # Update the gnbSearchList in the container's configuration file
        # Note: gnbSearchList is in YAML array format, so we need to update the IP address in the array
        update_cmd = [
            container_runtime, "exec", container_id,
            "sed", "-i", f"s/- 127\\.0\\.0\\.1/- {gnb_search_list}/",
            "/etc/ueransim/open5gs-ue.yaml"
        ]
        update_result = run_container_command(update_cmd, capture_output=True, text=True)
        
        if update_result.returncode != 0:
            return UeCreateResponse(
                status="error",
                container_id=container_id,
                container_name=container_name,
                configuration=UeConfiguration(gnb_search_list=gnb_search_list),
                message=f"Container created but failed to update gnbSearchList: {update_result.stderr}"
            )
        
        return UeCreateResponse(
            status="success",
            container_id=container_id,
            container_name=container_name or container_id[:12],
            configuration=UeConfiguration(gnb_search_list=gnb_search_list)
        )
    except Exception as e:
        return UeCreateResponse(
            status="error",
            container_id="",
            container_name="",
            configuration=UeConfiguration(gnb_search_list=gnb_search_list if 'gnb_search_list' in locals() else "127.0.0.1"),
            message=str(e)
        )


@mcp.tool()
def list_ues() -> UeListResponse:
    """List all UE containers.
    
    Returns:
        UeListResponse: List of UE containers
    """
    try:
        container_runtime = get_container_runtime()
        terminal_command = [
            container_runtime, "ps", "-a", "--filter", "name=ue-", 
            "--format", "{{.ID}}|{{.Names}}|{{.Status}}|{{.CreatedAt}}"
        ]

        result = run_container_command(terminal_command, capture_output=True, text=True)
        
        if result.returncode != 0:
            return UeListResponse(
                status="error",
                containers=[],
                count=0,
                message=result.stderr
            )
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                id, name, status, created = line.split('|', 3)
                containers.append(UeContainer(
                    id=id,
                    name=name,
                    status=status,
                    created=created
                ))
        
        return UeListResponse(
            status="success",
            containers=containers,
            count=len(containers)
        )
    except Exception as e:
        return UeListResponse(
            status="error",
            containers=[],
            count=0,
            message=str(e)
        )


@mcp.tool()
def delete_ue(container_id_or_name: str) -> UeOperationResponse:
    """Delete a UE container.
    
    Args:
        container_id_or_name: Container ID or name to delete
        
    Returns:
        UeOperationResponse: Deletion status
    """
    try:
        # Check if it's ID or name
        if re.match(r'^[0-9a-fA-F]+$', container_id_or_name) and (len(container_id_or_name) == 12 or len(container_id_or_name) == 64):
            validate_container_id(container_id_or_name)
        else:
            validate_container_name(container_id_or_name, "ue")
        
        # Get container runtime
        container_runtime = get_container_runtime()
            
        # Stop and remove container
        stop_cmd = [container_runtime, "stop", container_id_or_name]
        result = run_container_command(stop_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return UeOperationResponse(
                status="error",
                message=f"Failed to stop container: {result.stderr}",
                container=container_id_or_name
            )
        
        rm_cmd = [container_runtime, "rm", container_id_or_name]
        result = run_container_command(rm_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return UeOperationResponse(
                status="error", 
                message=f"Failed to remove container: {result.stderr}",
                container=container_id_or_name
            )
        
        return UeOperationResponse(
            status="success", 
            message=f"Container {container_id_or_name} successfully deleted",
            container=container_id_or_name
        )
    except Exception as e:
        return UeOperationResponse(
            status="error",
            message=str(e),
            container=container_id_or_name
        )


@mcp.tool()
def get_ue_logs(container_id_or_name: str, lines: int = 100) -> UeOperationResponse:
    """Get logs from a UE container.
    
    Args:
        container_id_or_name: Container ID or name
        lines: Number of lines to retrieve (default: 100)
        
    Returns:
        UeOperationResponse: Container logs
    """
    try:
        # Check if it's ID or name
        if re.match(r'^[0-9a-fA-F]+$', container_id_or_name) and (len(container_id_or_name) == 12 or len(container_id_or_name) == 64):
            validate_container_id(container_id_or_name)
        else:
            validate_container_name(container_id_or_name, "ue")
        
        # Get container runtime
        container_runtime = get_container_runtime()
        
        # Execute command to retrieve logs
        terminal_command = [container_runtime, "logs", f"--tail={lines}", container_id_or_name]
        result = run_container_command(terminal_command, capture_output=True, text=True)
        
        if result.returncode != 0:
            return UeOperationResponse(
                status="error",
                message=result.stderr,
                container=container_id_or_name
            )
        
        return UeOperationResponse(
            status="success",
            message="Logs retrieved successfully",
            container=container_id_or_name,
            logs=result.stdout
        )
    except Exception as e:
        return UeOperationResponse(
            status="error",
            message=str(e),
            container=container_id_or_name
        )


@mcp.tool()
def attach_ue_to_gnb(ue_container_id_or_name: str, gnb_container_id_or_name: str) -> UeOperationResponse:
    """Attach a UE container to a gNB container.
    
    Args:
        ue_container_id_or_name: UE container ID or name
        gnb_container_id_or_name: gNB container ID or name
        
    Returns:
        UeOperationResponse: Connection status
    """
    try:
        # Check if it's ID or name for UE
        if re.match(r'^[0-9a-fA-F]+$', ue_container_id_or_name) and (len(ue_container_id_or_name) == 12 or len(ue_container_id_or_name) == 64):
            validate_container_id(ue_container_id_or_name)
        else:
            validate_container_name(ue_container_id_or_name, "ue")

        # Check if it's ID or name for gNB
        if re.match(r'^[0-9a-fA-F]+$', gnb_container_id_or_name) and (len(gnb_container_id_or_name) == 12 or len(gnb_container_id_or_name) == 64):
            validate_container_id(gnb_container_id_or_name)
        else:
            validate_container_name(gnb_container_id_or_name, "gnb")
        
        # Get container runtime
        container_runtime = get_container_runtime()

        # Retrieve the gNB container's IP and update the UE's gnbSearchList so it
        # actually connects to the specified gNB
        gnb_ip_result = inspect_container_ip(gnb_container_id_or_name)
        if gnb_ip_result.status != "success" or not gnb_ip_result.logs:
            return UeOperationResponse(
                status="error",
                message=f"Could not determine IP for gNB container {gnb_container_id_or_name}: {gnb_ip_result.message}",
                container=ue_container_id_or_name
            )
        gnb_ip = gnb_ip_result.logs.strip()

        update_cmd = [
            container_runtime, "exec", ue_container_id_or_name,
            "sed", "-i", f"s/- .*/- {gnb_ip}/",
            "/etc/ueransim/open5gs-ue.yaml"
        ]
        update_result = run_container_command(update_cmd, capture_output=True, text=True)
        if update_result.returncode != 0:
            return UeOperationResponse(
                status="error",
                message=f"Failed to update gnbSearchList with gNB IP {gnb_ip}: {update_result.stderr}",
                container=ue_container_id_or_name
            )

        # Start nr-ue process in UE container using nohup for background execution with logs
        ue_exec_cmd = [
            container_runtime, "exec", "-d", ue_container_id_or_name, "sh", "-c",
            "nohup /usr/local/bin/nr-ue -c /etc/ueransim/open5gs-ue.yaml > /proc/1/fd/1 2>&1 &"
        ]
        ue_exec_result = run_container_command(ue_exec_cmd, capture_output=True, text=True)
        
        if ue_exec_result.returncode != 0:
            return UeOperationResponse(
                status="error",
                message=f"Failed to start nr-ue in UE container: {ue_exec_result.stderr}",
                container=ue_container_id_or_name
            )
        
        # Wait a moment for connection to establish
        time.sleep(3)
        
        # Check connection status by examining process outputs
        # Check gNB process output
        gnb_output_cmd = [container_runtime, "exec", gnb_container_id_or_name, "ps", "aux"]
        gnb_ps_result = run_container_command(gnb_output_cmd, capture_output=True, text=True)
        
        # Check UE process output  
        ue_output_cmd = [container_runtime, "exec", ue_container_id_or_name, "ps", "aux"]
        ue_ps_result = run_container_command(ue_output_cmd, capture_output=True, text=True)
        
        # Get actual process outputs by checking if processes are running
        gnb_process_running = False
        ue_process_running = False
        
        if gnb_ps_result.returncode == 0 and "nr-gnb" in gnb_ps_result.stdout:
            gnb_process_running = True
            
        if ue_ps_result.returncode == 0 and "nr-ue" in ue_ps_result.stdout:
            ue_process_running = True
        
        # Try to get some output from the processes by checking /tmp or /var/log if available
        gnb_status_cmd = [container_runtime, "exec", gnb_container_id_or_name, "sh", "-c", "pgrep -f nr-gnb && echo 'gNB process is running' || echo 'gNB process not found'"]
        gnb_status_result = run_container_command(gnb_status_cmd, capture_output=True, text=True)
        
        ue_status_cmd = [container_runtime, "exec", ue_container_id_or_name, "sh", "-c", "pgrep -f nr-ue && echo 'UE process is running' || echo 'UE process not found'"]
        ue_status_result = run_container_command(ue_status_cmd, capture_output=True, text=True)
        
        # Analyze process status
        connection_success = False
        connection_details = []
        
        if gnb_status_result.returncode == 0:
            if "process is running" in gnb_status_result.stdout:
                connection_details.append("gNB: nr-gnb process is active")
                connection_success = True
            else:
                connection_details.append("gNB: nr-gnb process not running")
        
        if ue_status_result.returncode == 0:
            if "process is running" in ue_status_result.stdout:
                connection_details.append("UE: nr-ue process is active")
                connection_success = True
            else:
                connection_details.append("UE: nr-ue process not running")
        
        # Prepare response message
        status_msg = "Processes are running" if connection_success else "Some processes may not be running"
        detailed_msg = f"UE container {ue_container_id_or_name} attached to gNB container {gnb_container_id_or_name}. {status_msg}. Details: {'; '.join(connection_details)}"
        
        # Combine process outputs for logs
        process_output = f"gNB process check:\n{gnb_status_result.stdout}\n\nUE process check:\n{ue_status_result.stdout}"
        if gnb_ps_result.returncode == 0:
            process_output += f"\n\ngNB processes:\n{gnb_ps_result.stdout}"
        if ue_ps_result.returncode == 0:
            process_output += f"\n\nUE processes:\n{ue_ps_result.stdout}"
        
        return UeOperationResponse(
            status="success" if connection_success else "warning",
            message=detailed_msg,
            container=ue_container_id_or_name,
            logs=process_output
        )
        
    except Exception as e:
        return UeOperationResponse(
            status="error",
            message=str(e),
            container=ue_container_id_or_name
        )


@mcp.tool()
def edit_exist_container(container_id_or_name: str, 
                        config_type: str = "gnb_search_list",
                        config_value: str = "127.0.0.1") -> UeOperationResponse:
    """Edit configuration of an existing container.
    
    Args:
        container_id_or_name: Container ID or name to edit
        config_type: Type of configuration to change (gnb_search_list, ngap_ip, gtp_ip, amf_ip)
        config_value: New configuration value
        
    Returns:
        UeOperationResponse: Operation status
    """
    try:
        # Validate that container exists and is accessible
        validate_existing_container(container_id_or_name)
        
        # Validate config value based on type
        if config_type in ["gnb_search_list", "ngap_ip", "gtp_ip", "amf_ip"]:
            validate_ip(config_value)
        
        # Get container runtime
        container_runtime = get_container_runtime()
        
        # Container already validated by validate_existing_container, no need to check again
        
        # Apply configuration based on type
        if config_type == "gnb_search_list":
            # Update UE configuration
            config_cmd = [
                container_runtime, "exec", container_id_or_name,
                "sed", "-i", f"s/- 127\\.0\\.0\\.1/- {config_value}/",
                "/etc/ueransim/open5gs-ue.yaml"
            ]
        elif config_type == "ngap_ip":
            # Update gNB NGAP IP
            config_cmd = [
                container_runtime, "exec", container_id_or_name,
                "sed", "-i", f"s/ngapIp: .*/ngapIp: {config_value}/",
                "/etc/ueransim/open5gs-gnb.yaml"
            ]
        elif config_type == "gtp_ip":
            # Update gNB GTP IP
            config_cmd = [
                container_runtime, "exec", container_id_or_name,
                "sed", "-i", f"s/gtpIp: .*/gtpIp: {config_value}/",
                "/etc/ueransim/open5gs-gnb.yaml"
            ]
        elif config_type == "amf_ip":
            # Update gNB AMF IP address (matches the "- address: ..." line inside amfConfigs)
            config_cmd = [
                container_runtime, "exec", container_id_or_name,
                "sed", "-i", f"s/- address: .*/- address: {config_value}/",
                "/etc/ueransim/open5gs-gnb.yaml"
            ]
        else:
            return UeOperationResponse(
                status="error",
                message=f"Unsupported config type: {config_type}",
                container=container_id_or_name
            )
        
        # Execute configuration change
        config_result = run_container_command(config_cmd, capture_output=True, text=True)
        
        if config_result.returncode != 0:
            return UeOperationResponse(
                status="error",
                message=f"Failed to update {config_type}: {config_result.stderr}",
                container=container_id_or_name
            )
        
        # Add success message to logs
        log_cmd = [
            container_runtime, "exec", container_id_or_name,
            "sh", "-c", f"echo 'Configuration updated: {config_type}={config_value}' >> /var/log/ueransim.log"
        ]
        run_container_command(log_cmd)
        
        # Echo success to demonstrate completion
        success_cmd = [
            container_runtime, "exec", container_id_or_name,
            "sh", "-c", "echo 'success'"
        ]
        success_result = run_container_command(success_cmd, capture_output=True, text=True)
        
        return UeOperationResponse(
            status="success",
            message=f"Container {container_id_or_name} configuration updated: {config_type}={config_value}",
            container=container_id_or_name,
            logs=success_result.stdout if success_result.returncode == 0 else None
        )
        
    except ValueError as e:
        # Validation errors from validate_existing_container() or validate_ip()
        return UeOperationResponse(
            status="error",
            message=str(e),
            container=container_id_or_name
        )
    except Exception as e:
        # Handle container operations and configuration errors
        error_msg = str(e)
        if "not found" in error_msg.lower():
            error_msg = f"Container {container_id_or_name} not found or not accessible"
        elif "permission" in error_msg.lower():
            error_msg = f"Permission denied: {error_msg}"
        elif "no such file" in error_msg.lower():
            error_msg = "Configuration file not found in container"
        elif "command not found" in error_msg.lower():
            error_msg = "Container runtime (Docker) not found"
        
        return UeOperationResponse(
            status="error",
            message=error_msg,
            container=container_id_or_name
        )


# ============================================================================
# KUBERNETES UTILITY FUNCTIONS
# ============================================================================

def get_k8s_client():
    """Load kubeconfig and return a CoreV1Api client.

    Tries in-cluster config first (when running inside a Pod), then falls back
    to the local ~/.kube/config.

    Returns:
        kubernetes.client.CoreV1Api
    """
    from kubernetes import client, config
    from kubernetes.config.config_exception import ConfigException

    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()

    return client.CoreV1Api()


def exec_in_pod(v1, pod_name: str, namespace: str, command: List[str]) -> tuple:
    """Execute a command inside a running pod.

    Args:
        v1: CoreV1Api instance
        pod_name: Pod name
        namespace: Kubernetes namespace
        command: Command list to execute

    Returns:
        (stdout, stderr) strings

    Raises:
        RuntimeError: If the stream raises an unexpected error
    """
    from kubernetes.stream import stream

    resp = stream(
        v1.connect_get_namespaced_pod_exec,
        pod_name,
        namespace,
        command=command,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    )
    return resp, ""


def wait_for_pod_running(v1, pod_name: str, namespace: str, timeout: int = 60) -> bool:
    """Poll until the pod reaches Running phase or timeout expires.

    Args:
        v1: CoreV1Api instance
        pod_name: Pod name
        namespace: Kubernetes namespace
        timeout: Seconds to wait (default: 60)

    Returns:
        True if Running within timeout, False otherwise
    """
    for _ in range(timeout):
        try:
            pod = v1.read_namespaced_pod(pod_name, namespace)
            if pod.status.phase == "Running":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


# ============================================================================
# KUBERNETES GNB TOOLS
# ============================================================================

@mcp.tool()
def k8s_create_gnb(
    amf_address: str = "127.0.0.5",
    amf_port: str = "38412",
    pod_name: Optional[str] = None,
    namespace: str = "ueransim",
    gnb_image: str = "ghcr.io/apelgroup/mcp-ueransim-new/ueransim-gnb:latest",
    image_pull_secret: str = "ghcr-pull-secret",
) -> GnbCreateResponse:
    """Create a new gNB Pod in Kubernetes.

    Args:
        amf_address: AMF IP address
        amf_port: AMF port
        pod_name: Optional pod name (auto-generated if omitted)
        namespace: Kubernetes namespace (default: ueransim)
        gnb_image: Container image for the gNB
        image_pull_secret: Name of the K8s docker-registry secret for pulling the image

    Returns:
        GnbCreateResponse: Information about the created pod
    """
    from kubernetes import client
    from kubernetes.client.rest import ApiException

    try:
        validate_ip(amf_address)

        if pod_name:
            validate_container_name(pod_name, "gnb")
        else:
            pod_name = f"gnb-{generate_random_suffix()}"

        v1 = get_k8s_client()

        pod_body = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                namespace=namespace,
                labels={"app": "ueransim", "type": "gnb"},
            ),
            spec=client.V1PodSpec(
                image_pull_secrets=[client.V1LocalObjectReference(name=image_pull_secret)],
                containers=[
                    client.V1Container(
                        name="gnb",
                        image=gnb_image,
                        image_pull_policy="IfNotPresent",
                        command=["tail", "-f", "/dev/null"],
                        security_context=client.V1SecurityContext(
                            capabilities=client.V1Capabilities(add=["NET_ADMIN"])
                        ),
                    )
                ]
            ),
        )

        v1.create_namespaced_pod(namespace=namespace, body=pod_body)

        if not wait_for_pod_running(v1, pod_name, namespace):
            return GnbCreateResponse(
                status="error",
                container_id=pod_name,
                container_name=pod_name,
                configuration=GnbConfiguration(
                    link_ip="", ngap_ip="", gtp_ip="",
                    amf_address=amf_address, amf_port=amf_port,
                ),
                message=f"Pod {pod_name} did not reach Running state within 60s",
            )

        pod = v1.read_namespaced_pod(pod_name, namespace)
        pod_ip = pod.status.pod_ip or ""

        for field, pattern in [
            ("linkIp", f"s/linkIp: .*/linkIp: {pod_ip}/"),
            ("ngapIp", f"s/ngapIp: .*/ngapIp: {pod_ip}/"),
            ("gtpIp",  f"s/gtpIp: .*/gtpIp: {pod_ip}/"),
        ]:
            exec_in_pod(v1, pod_name, namespace,
                        ["sed", "-i", pattern, "/etc/ueransim/open5gs-gnb.yaml"])

        exec_in_pod(v1, pod_name, namespace,
                    ["sed", "-i", f"s/- address: .*/- address: {amf_address}/",
                     "/etc/ueransim/open5gs-gnb.yaml"])

        return GnbCreateResponse(
            status="success",
            container_id=pod_name,
            container_name=pod_name,
            configuration=GnbConfiguration(
                link_ip=pod_ip,
                ngap_ip=pod_ip,
                gtp_ip=pod_ip,
                amf_address=amf_address,
                amf_port=amf_port,
            ),
        )

    except ValueError as e:
        return GnbCreateResponse(
            status="error",
            container_id="",
            container_name="",
            configuration=GnbConfiguration(
                link_ip="", ngap_ip="", gtp_ip="",
                amf_address=amf_address, amf_port=amf_port,
            ),
            message=str(e),
        )
    except ApiException as e:
        return GnbCreateResponse(
            status="error",
            container_id="",
            container_name="",
            configuration=GnbConfiguration(
                link_ip="", ngap_ip="", gtp_ip="",
                amf_address=amf_address, amf_port=amf_port,
            ),
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
        )
    except Exception as e:
        return GnbCreateResponse(
            status="error",
            container_id="",
            container_name="",
            configuration=GnbConfiguration(
                link_ip="", ngap_ip="", gtp_ip="",
                amf_address=amf_address, amf_port=amf_port,
            ),
            message=str(e),
        )


@mcp.tool()
def k8s_list_gnbs(namespace: str = "ueransim") -> GnbListResponse:
    """List all gNB pods in the given Kubernetes namespace.

    Args:
        namespace: Kubernetes namespace (default: ueransim)

    Returns:
        GnbListResponse: List of gNB pods
    """
    from kubernetes.client.rest import ApiException

    try:
        v1 = get_k8s_client()
        pod_list = v1.list_namespaced_pod(namespace, label_selector="type=gnb")

        containers = []
        for pod in pod_list.items:
            containers.append(GnbContainer(
                id=pod.metadata.name,
                name=pod.metadata.name,
                status=pod.status.phase or "Unknown",
                created=str(pod.metadata.creation_timestamp),
            ))

        return GnbListResponse(
            status="success",
            containers=containers,
            count=len(containers),
        )

    except ApiException as e:
        return GnbListResponse(
            status="error",
            containers=[],
            count=0,
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
        )
    except Exception as e:
        return GnbListResponse(
            status="error",
            containers=[],
            count=0,
            message=str(e),
        )


@mcp.tool()
def k8s_delete_gnb(pod_name: str, namespace: str = "ueransim") -> GnbOperationResponse:
    """Delete a gNB pod from Kubernetes.

    Args:
        pod_name: Pod name to delete
        namespace: Kubernetes namespace (default: ueransim)

    Returns:
        GnbOperationResponse: Deletion status
    """
    from kubernetes import client
    from kubernetes.client.rest import ApiException

    try:
        validate_container_name(pod_name, "gnb")

        v1 = get_k8s_client()
        v1.delete_namespaced_pod(
            pod_name, namespace, body=client.V1DeleteOptions(grace_period_seconds=0)
        )

        return GnbOperationResponse(
            status="success",
            message=f"Pod {pod_name} deleted from namespace {namespace}",
            container=pod_name,
        )

    except ValueError as e:
        return GnbOperationResponse(status="error", message=str(e), container=pod_name)
    except ApiException as e:
        return GnbOperationResponse(
            status="error",
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
            container=pod_name,
        )
    except Exception as e:
        return GnbOperationResponse(status="error", message=str(e), container=pod_name)


@mcp.tool()
def k8s_get_gnb_logs(
    pod_name: str, lines: int = 100, namespace: str = "ueransim"
) -> GnbOperationResponse:
    """Get logs from a gNB pod.

    Args:
        pod_name: Pod name
        lines: Number of log lines to retrieve (default: 100)
        namespace: Kubernetes namespace (default: ueransim)

    Returns:
        GnbOperationResponse: Pod logs
    """
    from kubernetes.client.rest import ApiException

    try:
        validate_container_name(pod_name, "gnb")

        v1 = get_k8s_client()
        logs = v1.read_namespaced_pod_log(pod_name, namespace, tail_lines=lines)

        return GnbOperationResponse(
            status="success",
            message="Logs retrieved successfully",
            container=pod_name,
            logs=logs,
        )

    except ValueError as e:
        return GnbOperationResponse(status="error", message=str(e), container=pod_name)
    except ApiException as e:
        return GnbOperationResponse(
            status="error",
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
            container=pod_name,
        )
    except Exception as e:
        return GnbOperationResponse(status="error", message=str(e), container=pod_name)


@mcp.tool()
def k8s_attach_gnb_to_core(
    pod_name: str,
    amf_address: str = "127.0.0.5",
    namespace: str = "ueransim",
) -> GnbOperationResponse:
    """Update the AMF address in a gNB pod and start the nr-gnb process.

    Args:
        pod_name: gNB pod name
        amf_address: AMF IP address (default: 127.0.0.5)
        namespace: Kubernetes namespace (default: ueransim)

    Returns:
        GnbOperationResponse: Connection status
    """
    from kubernetes.client.rest import ApiException

    try:
        validate_ip(amf_address)
        validate_container_name(pod_name, "gnb")

        v1 = get_k8s_client()

        exec_in_pod(v1, pod_name, namespace,
                    ["sed", "-i", f"s/- address: .*/- address: {amf_address}/",
                     "/etc/ueransim/open5gs-gnb.yaml"])

        exec_in_pod(v1, pod_name, namespace,
                    ["sh", "-c",
                     "nohup /usr/local/bin/nr-gnb -c /etc/ueransim/open5gs-gnb.yaml"
                     " > /proc/1/fd/1 2>&1 &"])

        time.sleep(2)

        status_out, _ = exec_in_pod(
            v1, pod_name, namespace,
            ["sh", "-c", "pgrep -f nr-gnb && echo 'gNB process is running'"
                         " || echo 'gNB process not found'"],
        )

        process_running = "process is running" in status_out

        return GnbOperationResponse(
            status="success" if process_running else "warning",
            message=(
                f"Pod {pod_name} connected to core with AMF {amf_address}. "
                f"{'nr-gnb started.' if process_running else 'nr-gnb may not be running.'}"
            ),
            container=pod_name,
            logs=status_out,
        )

    except ValueError as e:
        return GnbOperationResponse(status="error", message=str(e), container=pod_name)
    except ApiException as e:
        return GnbOperationResponse(
            status="error",
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
            container=pod_name,
        )
    except Exception as e:
        return GnbOperationResponse(status="error", message=str(e), container=pod_name)


# ============================================================================
# KUBERNETES COMMON TOOLS
# ============================================================================

@mcp.tool()
def k8s_inspect_pod_ip(pod_name: str, namespace: str = "ueransim") -> GnbOperationResponse:
    """Get the IP address of a Kubernetes pod.

    Args:
        pod_name: Pod name
        namespace: Kubernetes namespace (default: ueransim)

    Returns:
        GnbOperationResponse: Pod IP in the logs field
    """
    from kubernetes.client.rest import ApiException

    try:
        v1 = get_k8s_client()
        pod = v1.read_namespaced_pod(pod_name, namespace)
        pod_ip = pod.status.pod_ip

        if not pod_ip:
            return GnbOperationResponse(
                status="error",
                message=f"No IP address found for pod {pod_name}",
                container=pod_name,
            )

        return GnbOperationResponse(
            status="success",
            message=f"Pod {pod_name} IP address: {pod_ip}",
            container=pod_name,
            logs=pod_ip,
        )

    except ApiException as e:
        return GnbOperationResponse(
            status="error",
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
            container=pod_name,
        )
    except Exception as e:
        return GnbOperationResponse(status="error", message=str(e), container=pod_name)


# ============================================================================
# KUBERNETES UE TOOLS
# ============================================================================

@mcp.tool()
def k8s_create_ue(
    gnb_search_list: str = "127.0.0.1",
    pod_name: Optional[str] = None,
    namespace: str = "ueransim",
    ue_image: str = "ghcr.io/apelgroup/mcp-ueransim-new/ueransim-ue:latest",
    image_pull_secret: str = "ghcr-pull-secret",
) -> UeCreateResponse:
    """Create a new UE pod in Kubernetes.

    Args:
        gnb_search_list: gNB IP for Radio Link Simulation (or "auto" to use first gNB)
        pod_name: Optional pod name (auto-generated if omitted)
        namespace: Kubernetes namespace (default: ueransim)
        ue_image: Container image for the UE
        image_pull_secret: Name of the K8s docker-registry secret for pulling the image

    Returns:
        UeCreateResponse: Information about the created pod
    """
    from kubernetes import client
    from kubernetes.client.rest import ApiException

    try:
        if gnb_search_list == "auto":
            gnb_list = k8s_list_gnbs(namespace)
            if gnb_list.status == "success" and gnb_list.count > 0:
                ip_result = k8s_inspect_pod_ip(gnb_list.containers[0].name, namespace)
                gnb_search_list = ip_result.logs if ip_result.status == "success" else "127.0.0.1"
            else:
                gnb_search_list = "127.0.0.1"
            print(f"Auto-detected gNB IP: {gnb_search_list}", file=sys.stderr)

        validate_ip(gnb_search_list)

        if pod_name:
            validate_container_name(pod_name, "ue")
        else:
            pod_name = f"ue-{generate_random_suffix()}"

        v1 = get_k8s_client()

        pod_body = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                namespace=namespace,
                labels={"app": "ueransim", "type": "ue"},
            ),
            spec=client.V1PodSpec(
                host_network=True,
                image_pull_secrets=[client.V1LocalObjectReference(name=image_pull_secret)],
                containers=[
                    client.V1Container(
                        name="ue",
                        image=ue_image,
                        image_pull_policy="IfNotPresent",
                        command=["tail", "-f", "/dev/null"],
                        security_context=client.V1SecurityContext(
                            privileged=True,
                            capabilities=client.V1Capabilities(add=["NET_ADMIN"]),
                        ),
                        volume_mounts=[
                            client.V1VolumeMount(
                                name="tun-device", mount_path="/dev/net/tun"
                            )
                        ],
                    )
                ],
                volumes=[
                    client.V1Volume(
                        name="tun-device",
                        host_path=client.V1HostPathVolumeSource(
                            path="/dev/net/tun", type="CharDevice"
                        ),
                    )
                ],
            ),
        )

        v1.create_namespaced_pod(namespace=namespace, body=pod_body)

        if not wait_for_pod_running(v1, pod_name, namespace):
            return UeCreateResponse(
                status="error",
                container_id=pod_name,
                container_name=pod_name,
                configuration=UeConfiguration(gnb_search_list=gnb_search_list),
                message=f"Pod {pod_name} did not reach Running state within 60s",
            )

        exec_in_pod(v1, pod_name, namespace,
                    ["sed", "-i", f"s/- .*/- {gnb_search_list}/",
                     "/etc/ueransim/open5gs-ue.yaml"])

        return UeCreateResponse(
            status="success",
            container_id=pod_name,
            container_name=pod_name,
            configuration=UeConfiguration(gnb_search_list=gnb_search_list),
        )

    except ValueError as e:
        return UeCreateResponse(
            status="error",
            container_id="",
            container_name="",
            configuration=UeConfiguration(gnb_search_list=gnb_search_list),
            message=str(e),
        )
    except ApiException as e:
        return UeCreateResponse(
            status="error",
            container_id="",
            container_name="",
            configuration=UeConfiguration(gnb_search_list=gnb_search_list),
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
        )
    except Exception as e:
        return UeCreateResponse(
            status="error",
            container_id="",
            container_name="",
            configuration=UeConfiguration(
                gnb_search_list=gnb_search_list if 'gnb_search_list' in locals() else "127.0.0.1"
            ),
            message=str(e),
        )


@mcp.tool()
def k8s_list_ues(namespace: str = "ueransim") -> UeListResponse:
    """List all UE pods in the given Kubernetes namespace.

    Args:
        namespace: Kubernetes namespace (default: ueransim)

    Returns:
        UeListResponse: List of UE pods
    """
    from kubernetes.client.rest import ApiException

    try:
        v1 = get_k8s_client()
        pod_list = v1.list_namespaced_pod(namespace, label_selector="type=ue")

        containers = []
        for pod in pod_list.items:
            containers.append(UeContainer(
                id=pod.metadata.name,
                name=pod.metadata.name,
                status=pod.status.phase or "Unknown",
                created=str(pod.metadata.creation_timestamp),
            ))

        return UeListResponse(
            status="success",
            containers=containers,
            count=len(containers),
        )

    except ApiException as e:
        return UeListResponse(
            status="error",
            containers=[],
            count=0,
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
        )
    except Exception as e:
        return UeListResponse(status="error", containers=[], count=0, message=str(e))


@mcp.tool()
def k8s_delete_ue(pod_name: str, namespace: str = "ueransim") -> UeOperationResponse:
    """Delete a UE pod from Kubernetes.

    Args:
        pod_name: Pod name to delete
        namespace: Kubernetes namespace (default: ueransim)

    Returns:
        UeOperationResponse: Deletion status
    """
    from kubernetes import client
    from kubernetes.client.rest import ApiException

    try:
        validate_container_name(pod_name, "ue")

        v1 = get_k8s_client()
        v1.delete_namespaced_pod(
            pod_name, namespace, body=client.V1DeleteOptions(grace_period_seconds=0)
        )

        return UeOperationResponse(
            status="success",
            message=f"Pod {pod_name} deleted from namespace {namespace}",
            container=pod_name,
        )

    except ValueError as e:
        return UeOperationResponse(status="error", message=str(e), container=pod_name)
    except ApiException as e:
        return UeOperationResponse(
            status="error",
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
            container=pod_name,
        )
    except Exception as e:
        return UeOperationResponse(status="error", message=str(e), container=pod_name)


@mcp.tool()
def k8s_get_ue_logs(
    pod_name: str, lines: int = 100, namespace: str = "ueransim"
) -> UeOperationResponse:
    """Get logs from a UE pod.

    Args:
        pod_name: Pod name
        lines: Number of log lines to retrieve (default: 100)
        namespace: Kubernetes namespace (default: ueransim)

    Returns:
        UeOperationResponse: Pod logs
    """
    from kubernetes.client.rest import ApiException

    try:
        validate_container_name(pod_name, "ue")

        v1 = get_k8s_client()
        logs = v1.read_namespaced_pod_log(pod_name, namespace, tail_lines=lines)

        return UeOperationResponse(
            status="success",
            message="Logs retrieved successfully",
            container=pod_name,
            logs=logs,
        )

    except ValueError as e:
        return UeOperationResponse(status="error", message=str(e), container=pod_name)
    except ApiException as e:
        return UeOperationResponse(
            status="error",
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
            container=pod_name,
        )
    except Exception as e:
        return UeOperationResponse(status="error", message=str(e), container=pod_name)


@mcp.tool()
def k8s_attach_ue_to_gnb(
    ue_pod_name: str,
    gnb_pod_name: str,
    namespace: str = "ueransim",
) -> UeOperationResponse:
    """Update the UE's gnbSearchList with the gNB pod IP and start the nr-ue process.

    Args:
        ue_pod_name: UE pod name
        gnb_pod_name: gNB pod name
        namespace: Kubernetes namespace (default: ueransim)

    Returns:
        UeOperationResponse: Connection status
    """
    from kubernetes.client.rest import ApiException

    try:
        validate_container_name(ue_pod_name, "ue")
        validate_container_name(gnb_pod_name, "gnb")

        v1 = get_k8s_client()

        gnb_ip_result = k8s_inspect_pod_ip(gnb_pod_name, namespace)
        if gnb_ip_result.status != "success" or not gnb_ip_result.logs:
            return UeOperationResponse(
                status="error",
                message=f"Could not determine IP for gNB pod {gnb_pod_name}: {gnb_ip_result.message}",
                container=ue_pod_name,
            )
        gnb_ip = gnb_ip_result.logs.strip()

        exec_in_pod(v1, ue_pod_name, namespace,
                    ["sed", "-i", f"s/- .*/- {gnb_ip}/",
                     "/etc/ueransim/open5gs-ue.yaml"])

        exec_in_pod(v1, ue_pod_name, namespace,
                    ["sh", "-c",
                     "nohup /usr/local/bin/nr-ue -c /etc/ueransim/open5gs-ue.yaml"
                     " > /proc/1/fd/1 2>&1 &"])

        time.sleep(3)

        gnb_status, _ = exec_in_pod(
            v1, gnb_pod_name, namespace,
            ["sh", "-c", "pgrep -f nr-gnb && echo 'gNB process is running'"
                         " || echo 'gNB process not found'"],
        )
        ue_status, _ = exec_in_pod(
            v1, ue_pod_name, namespace,
            ["sh", "-c", "pgrep -f nr-ue && echo 'UE process is running'"
                         " || echo 'UE process not found'"],
        )

        gnb_running = "process is running" in gnb_status
        ue_running = "process is running" in ue_status
        both_running = gnb_running and ue_running

        details = []
        details.append("gNB: nr-gnb active" if gnb_running else "gNB: nr-gnb not running")
        details.append("UE: nr-ue active" if ue_running else "UE: nr-ue not running")

        return UeOperationResponse(
            status="success" if both_running else "warning",
            message=(
                f"UE pod {ue_pod_name} attached to gNB pod {gnb_pod_name} "
                f"(gNB IP: {gnb_ip}). {'; '.join(details)}"
            ),
            container=ue_pod_name,
            logs=f"gNB check:\n{gnb_status}\n\nUE check:\n{ue_status}",
        )

    except ValueError as e:
        return UeOperationResponse(status="error", message=str(e), container=ue_pod_name)
    except ApiException as e:
        return UeOperationResponse(
            status="error",
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
            container=ue_pod_name,
        )
    except Exception as e:
        return UeOperationResponse(status="error", message=str(e), container=ue_pod_name)


@mcp.tool()
def k8s_edit_pod_config(
    pod_name: str,
    config_type: str = "gnb_search_list",
    config_value: str = "127.0.0.1",
    namespace: str = "ueransim",
) -> UeOperationResponse:
    """Edit configuration inside an existing pod.

    Args:
        pod_name: Pod name to edit
        config_type: One of gnb_search_list, ngap_ip, gtp_ip, amf_ip
        config_value: New value (IP address)
        namespace: Kubernetes namespace (default: ueransim)

    Returns:
        UeOperationResponse: Operation status
    """
    from kubernetes.client.rest import ApiException

    try:
        v1 = get_k8s_client()
        v1.read_namespaced_pod(pod_name, namespace)

        if config_type in ["gnb_search_list", "ngap_ip", "gtp_ip", "amf_ip"]:
            validate_ip(config_value)

        if config_type == "gnb_search_list":
            cmd = ["sed", "-i", f"s/- .*/- {config_value}/",
                   "/etc/ueransim/open5gs-ue.yaml"]
        elif config_type == "ngap_ip":
            cmd = ["sed", "-i", f"s/ngapIp: .*/ngapIp: {config_value}/",
                   "/etc/ueransim/open5gs-gnb.yaml"]
        elif config_type == "gtp_ip":
            cmd = ["sed", "-i", f"s/gtpIp: .*/gtpIp: {config_value}/",
                   "/etc/ueransim/open5gs-gnb.yaml"]
        elif config_type == "amf_ip":
            cmd = ["sed", "-i", f"s/- address: .*/- address: {config_value}/",
                   "/etc/ueransim/open5gs-gnb.yaml"]
        else:
            return UeOperationResponse(
                status="error",
                message=f"Unsupported config type: {config_type}",
                container=pod_name,
            )

        exec_in_pod(v1, pod_name, namespace, cmd)

        return UeOperationResponse(
            status="success",
            message=f"Pod {pod_name} configuration updated: {config_type}={config_value}",
            container=pod_name,
        )

    except ValueError as e:
        return UeOperationResponse(status="error", message=str(e), container=pod_name)
    except ApiException as e:
        return UeOperationResponse(
            status="error",
            message=f"Kubernetes API error: {e.reason} (status {e.status})",
            container=pod_name,
        )
    except Exception as e:
        return UeOperationResponse(status="error", message=str(e), container=pod_name)


# ============================================================================
# SERVER STARTUP
# ============================================================================

def start_server():
    """Start the MCP server."""
    mcp.run()


if __name__ == "__main__":
    start_server()