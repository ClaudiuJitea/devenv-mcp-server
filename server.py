"""
MCP Dev Environment Server

An MCP server that provisions Docker-based development environments.
Any AI agent can call these tools to create, manage, and inspect
containerized dev environments for any technology stack.
"""

import json

from mcp.server.fastmcp import FastMCP

from docker_manager import DockerManager
from stacks import list_stacks

# ── MCP Server ──────────────────────────────────────────────────────────────

mcp = FastMCP(
    "devenv",
    instructions=(
        "This server manages Docker-based development environments. "
        "Use 'list_supported_stacks' to see available stacks, then "
        "'create_environment' to provision a new one. Each environment "
        "gets its own Docker container. By default environments are "
        "created in isolated mode so source files and dependencies remain "
        "inside the container. You can opt into mapped mode to bind-mount "
        "~/devenv-projects/<project> into /app for direct host editing. "
        "Use 'write_file' and 'read_file' to directly create or read files "
        "inside the container's /app directory. Use 'exec_command' to run "
        "shell commands inside the container (install packages, run tests, etc.). "
        "Use 'export_environment' to produce a portable Docker image tarball."
    ),
)

dm = DockerManager()


# ── Resources ───────────────────────────────────────────────────────────────

@mcp.resource("devenv://stacks")
def stacks_resource() -> str:
    """List of all supported development stacks."""
    return json.dumps(list_stacks(), indent=2)


# ── Tools ───────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_supported_stacks() -> str:
    """
    List all supported technology stacks that can be used to create
    development environments.

    Returns a list of stacks with name, description, base image, and default port.
    """
    stacks = list_stacks()
    lines = []
    for s in stacks:
        lines.append(
            f"• {s['name']} ({s['display_name']}): {s['description']} "
            f"[{s['base_image']}, port {s['default_port']}]"
        )
    return "\n".join(lines)


@mcp.tool()
async def create_environment(
    project_name: str,
    stack: str,
    extra_packages: list[str] | None = None,
    workspace_mode: str = "isolated",
) -> str:
    """
    Create a new Docker-based development environment.

    This will:
    1. Create a project config folder with Dockerfile and docker-compose.yml
    2. Generate stack scaffold files and metadata
    3. Build and start the Docker container
    4. Start the container in one of two modes:
       - isolated (default): app files stay in the container for portability
       - mapped: host folder is bind-mounted for direct local editing

    Args:
        project_name: Name for the project (will be sanitized to lowercase/hyphens)
        stack: Technology stack to use. Run list_supported_stacks to see options.
               Options: flask, django, fastapi, nextjs, vite-react, vite-vue, express,
                        static-html, laravel, symfony, nestjs, bun-hono, rust-axum,
                        go-gin, nginx-static
        extra_packages: Optional list of additional packages to install
                        (pip packages for Python stacks, npm packages for Node stacks)
        workspace_mode: "isolated" (default) or "mapped"

    Returns:
        JSON with creation result including project directory, workspace mode,
        port, and URL.
    """
    result = await dm.create_environment(
        project_name=project_name,
        stack_name=stack,
        extra_packages=extra_packages,
        workspace_mode=workspace_mode,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_environments() -> str:
    """
    List all managed development environments and their current status.

    Returns a list of environments with project name, stack, port, and container status.
    """
    result = await dm.list_environments()
    return json.dumps(result, indent=2)


@mcp.tool()
async def start_environment(project_name: str) -> str:
    """
    Start a previously stopped development environment.

    Args:
        project_name: Name of the project to start.
    """
    result = await dm.start_environment(project_name)
    return json.dumps(result, indent=2)


@mcp.tool()
async def stop_environment(project_name: str) -> str:
    """
    Stop a running development environment without destroying it.

    The container and files are preserved and can be restarted later.

    Args:
        project_name: Name of the project to stop.
    """
    result = await dm.stop_environment(project_name)
    return json.dumps(result, indent=2)


@mcp.tool()
async def destroy_environment(
    project_name: str, remove_files: bool = True
) -> str:
    """
    Destroy a development environment completely.

    Removes Docker containers, images, and volumes.
    By default also removes the project files from disk.

    Args:
        project_name: Name of the project to destroy.
        remove_files: If True (default), also delete the project directory and all files.
    """
    result = await dm.destroy_environment(project_name, remove_files)
    return json.dumps(result, indent=2)


@mcp.tool()
async def exec_command(project_name: str, command: str) -> str:
    """
    Execute a command inside a running development environment container.

    Use this to install additional packages, run scripts, check logs, etc.

    Args:
        project_name: Name of the project whose container to exec into.
        command: Shell command to execute (e.g. 'pip install requests', 'npm list', 'ls -la').
    """
    result = await dm.exec_command(project_name, command)
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_environment_info(project_name: str) -> str:
    """
    Get detailed information about a development environment.

    Returns stack type, port, container status, project files, and access URL.

    Args:
        project_name: Name of the project to inspect.
    """
    result = await dm.get_environment_info(project_name)
    return json.dumps(result, indent=2)


@mcp.tool()
async def write_file(
    project_name: str, file_path: str, content: str
) -> str:
    """
    Write (create or overwrite) a file inside a development environment.

    The file_path is relative to /app inside the container. Parent directories
    are created automatically. Changes are immediately visible to the running container.

    Args:
        project_name: Name of the project.
        file_path: Path relative to /app (e.g. 'src/index.js', 'templates/home.html').
        content: Full file content to write.
    """
    result = await dm.write_file(project_name, file_path, content)
    return json.dumps(result, indent=2)


@mcp.tool()
async def read_file(project_name: str, file_path: str) -> str:
    """
    Read a file from inside a development environment.

    The file_path is relative to /app inside the container.

    Args:
        project_name: Name of the project.
        file_path: Path relative to /app (e.g. 'app.py', 'package.json').
    """
    result = await dm.read_file(project_name, file_path)
    return json.dumps(result, indent=2)


@mcp.tool()
async def export_environment(
    project_name: str,
    output_tar_path: str | None = None,
    image_tag: str | None = None,
) -> str:
    """
    Export an environment as a portable Docker image tar archive.

    Args:
        project_name: Name of the project to export.
        output_tar_path: Optional output path for the tar archive.
        image_tag: Optional Docker tag for the exported snapshot image.

    Note:
        For mapped environments, export captures host-mapped project files into a temporary isolated image before saving the tar.
        Export also generates Linux (.sh) and Windows (.ps1) deploy scripts in the tar folder.
    """
    result = await dm.export_environment(project_name, output_tar_path, image_tag)
    return json.dumps(result, indent=2)


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    """Run the MCP server using stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
