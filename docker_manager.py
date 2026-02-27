"""
Docker Manager for MCP Dev Environment Server.

Manages the lifecycle of Docker-based development environments:
create, start, stop, destroy, list, exec, and inspect.
"""

import asyncio
import json
import os
import shutil
from pathlib import Path

from stacks import StackTemplate, get_stack, list_stacks

# Base directory where all project folders are created
PROJECTS_BASE = Path.cwd()

# Label used to identify containers managed by this server
MANAGED_LABEL = "devenv-mcp.managed=true"


def _compose_file(project_dir: Path) -> Path:
    return project_dir / "docker-compose.yml"


def _generate_compose(
    project_name: str, stack: StackTemplate, extra_ports: list[str] | None = None
) -> str:
    """Generate docker-compose.yml content for a project."""
    ports = [f"{stack.default_port}:{stack.default_port}"]
    if extra_ports:
        ports.extend(extra_ports)

    ports_yaml = "\n".join(f'      - "{p}"' for p in ports)

    uid = os.getuid()
    gid = os.getgid()

    return f"""\
services:
  {project_name}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: devenv-{project_name}
    user: "{uid}:{gid}"
    environment:
      - HOME=/tmp
    volumes:
      - .:{stack.workdir}
    ports:
{ports_yaml}
    working_dir: {stack.workdir}
    stdin_open: true
    tty: true
    restart: unless-stopped
    labels:
      - "devenv-mcp.managed=true"
      - "devenv-mcp.stack={stack.name}"
      - "devenv-mcp.project={project_name}"
"""


async def _run(cmd: str, cwd: Path | None = None, timeout: int = 300) -> tuple[int, str, str]:
    """Run a shell command asynchronously and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", f"Command timed out after {timeout}s: {cmd}"

    return proc.returncode, stdout.decode(), stderr.decode()


class DockerManager:
    """Manages Docker-based development environments."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else PROJECTS_BASE

    async def create_environment(
        self,
        project_name: str,
        stack_name: str,
        extra_packages: list[str] | None = None,
    ) -> dict:
        """
        Create a new development environment.

        1. Validates input
        2. Creates project directory
        3. Writes Dockerfile, docker-compose.yml, and scaffold files
        4. Builds and starts the container
        5. Runs init commands inside the container
        """
        # Validate stack
        stack = get_stack(stack_name)
        if not stack:
            available = [s["name"] for s in list_stacks()]
            return {
                "success": False,
                "error": f"Unknown stack '{stack_name}'. Available: {', '.join(available)}",
            }

        # Validate project name
        safe_name = project_name.lower().replace(" ", "-")
        project_dir = self.base_dir / safe_name

        if project_dir.exists() and any(project_dir.iterdir()):
            return {
                "success": False,
                "error": f"Project directory already exists and is not empty: {project_dir}",
            }

        # Create project directory
        project_dir.mkdir(parents=True, exist_ok=True)

        # Write Dockerfile
        (project_dir / "Dockerfile").write_text(stack.dockerfile)

        # Write docker-compose.yml
        compose_content = _generate_compose(safe_name, stack)
        _compose_file(project_dir).write_text(compose_content)

        # Write scaffold files
        for filename, content in stack.scaffold_files.items():
            filepath = project_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)

        # Write a .devenv metadata file
        meta = {
            "project_name": safe_name,
            "stack": stack_name,
            "port": stack.default_port,
            "base_image": stack.base_image,
        }
        (project_dir / ".devenv.json").write_text(json.dumps(meta, indent=2))

        # Build and start
        rc, stdout, stderr = await _run(
            "docker compose up -d --build", cwd=project_dir, timeout=600
        )
        if rc != 0:
            return {
                "success": False,
                "error": f"Docker build/start failed:\n{stderr}",
                "project_dir": str(project_dir),
            }

        # Run init commands
        init_results = []
        all_init_commands = list(stack.init_commands)

        # Add extra packages if requested
        if extra_packages:
            if stack.base_image.startswith("python"):
                all_init_commands.append(
                    f"pip install --no-cache-dir {' '.join(extra_packages)}"
                )
            elif stack.base_image.startswith("node"):
                all_init_commands.append(f"npm install {' '.join(extra_packages)}")

        for cmd in all_init_commands:
            rc, stdout, stderr = await _run(
                f"docker compose exec -T {safe_name} sh -c '{cmd}'",
                cwd=project_dir,
                timeout=300,
            )
            init_results.append({
                "command": cmd,
                "success": rc == 0,
                "output": stdout[:500] if stdout else "",
                "error": stderr[:500] if stderr and rc != 0 else "",
            })

        # Restart after init to pick up any new files
        await _run("docker compose restart", cwd=project_dir)

        return {
            "success": True,
            "project_name": safe_name,
            "project_dir": str(project_dir),
            "stack": stack_name,
            "port": stack.default_port,
            "container_name": f"devenv-{safe_name}",
            "url": f"http://localhost:{stack.default_port}",
            "init_results": init_results,
            "message": (
                f"Environment '{safe_name}' created with {stack.display_name}. "
                f"Access at http://localhost:{stack.default_port}"
            ),
        }

    async def start_environment(self, project_name: str) -> dict:
        """Start a stopped environment."""
        project_dir = self.base_dir / project_name
        if not _compose_file(project_dir).exists():
            return {"success": False, "error": f"No environment found: {project_name}"}

        rc, _, stderr = await _run("docker compose up -d", cwd=project_dir)
        if rc != 0:
            return {"success": False, "error": stderr}

        return {"success": True, "message": f"Environment '{project_name}' started."}

    async def stop_environment(self, project_name: str) -> dict:
        """Stop a running environment."""
        project_dir = self.base_dir / project_name
        if not _compose_file(project_dir).exists():
            return {"success": False, "error": f"No environment found: {project_name}"}

        rc, _, stderr = await _run("docker compose stop", cwd=project_dir)
        if rc != 0:
            return {"success": False, "error": stderr}

        return {"success": True, "message": f"Environment '{project_name}' stopped."}

    async def destroy_environment(
        self, project_name: str, remove_files: bool = False
    ) -> dict:
        """Destroy an environment (containers + optionally files)."""
        project_dir = self.base_dir / project_name
        if not _compose_file(project_dir).exists():
            return {"success": False, "error": f"No environment found: {project_name}"}

        rc, _, stderr = await _run(
            "docker compose down -v --rmi local", cwd=project_dir
        )
        if rc != 0:
            return {"success": False, "error": stderr}

        result = {
            "success": True,
            "message": f"Environment '{project_name}' destroyed.",
        }

        if remove_files:
            shutil.rmtree(project_dir, ignore_errors=True)
            result["message"] += f" Project files removed from {project_dir}."

        return result

    async def list_environments(self) -> dict:
        """List all managed environments and their status."""
        if not self.base_dir.exists():
            return {"success": True, "environments": []}

        environments = []
        for item in sorted(self.base_dir.iterdir()):
            if not item.is_dir():
                continue
            compose = _compose_file(item)
            if not compose.exists():
                continue

            # Read metadata
            meta_file = item / ".devenv.json"
            meta = {}
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                except json.JSONDecodeError:
                    pass

            # Get container status
            rc, stdout, _ = await _run(
                "docker compose ps --format json", cwd=item
            )

            status = "unknown"
            if rc == 0 and stdout.strip():
                try:
                    # docker compose ps --format json may return one JSON per line
                    lines = [
                        json.loads(line)
                        for line in stdout.strip().split("\n")
                        if line.strip()
                    ]
                    if lines:
                        status = lines[0].get("State", "unknown")
                except json.JSONDecodeError:
                    status = "error"
            else:
                status = "stopped"

            environments.append({
                "project_name": item.name,
                "project_dir": str(item),
                "stack": meta.get("stack", "unknown"),
                "port": meta.get("port", "unknown"),
                "status": status,
            })

        return {"success": True, "environments": environments}

    async def get_environment_info(self, project_name: str) -> dict:
        """Get detailed information about an environment."""
        project_dir = self.base_dir / project_name
        if not _compose_file(project_dir).exists():
            return {"success": False, "error": f"No environment found: {project_name}"}

        # Read metadata
        meta_file = project_dir / ".devenv.json"
        meta = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except json.JSONDecodeError:
                pass

        # Get container details
        rc, stdout, _ = await _run(
            "docker compose ps --format json", cwd=project_dir
        )

        container_info = {}
        if rc == 0 and stdout.strip():
            try:
                lines = [
                    json.loads(line)
                    for line in stdout.strip().split("\n")
                    if line.strip()
                ]
                if lines:
                    container_info = lines[0]
            except json.JSONDecodeError:
                pass

        # List project files
        files = []
        for f in sorted(project_dir.iterdir()):
            if f.name.startswith("."):
                continue
            files.append(f.name)

        return {
            "success": True,
            "project_name": project_name,
            "project_dir": str(project_dir),
            "stack": meta.get("stack", "unknown"),
            "port": meta.get("port", "unknown"),
            "base_image": meta.get("base_image", "unknown"),
            "container_status": container_info.get("State", "unknown"),
            "container_name": container_info.get("Name", f"devenv-{project_name}"),
            "files": files,
            "url": f"http://localhost:{meta.get('port', '?')}",
        }

    async def exec_command(self, project_name: str, command: str) -> dict:
        """Execute a command inside the environment's container."""
        project_dir = self.base_dir / project_name
        if not _compose_file(project_dir).exists():
            return {"success": False, "error": f"No environment found: {project_name}"}

        service_name = project_name
        rc, stdout, stderr = await _run(
            f"docker compose exec -T {service_name} sh -c '{command}'",
            cwd=project_dir,
            timeout=120,
        )

        return {
            "success": rc == 0,
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": rc,
        }
