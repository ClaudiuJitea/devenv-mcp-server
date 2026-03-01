"""
Docker Manager for MCP Dev Environment Server.

Manages the lifecycle of Docker-based development environments.
"""

import asyncio
import base64
import json
import os
import re
import shlex
import shutil
import uuid
from pathlib import Path, PurePosixPath

from stacks import StackTemplate, get_stack, list_stacks

# Base directory where all project configs are created
PROJECTS_BASE = Path.home() / "devenv-projects"

# Label used to identify containers managed by this server
MANAGED_LABEL = "devenv-mcp.managed=true"

WORKSPACE_MODE_ISOLATED = "isolated"
WORKSPACE_MODE_MAPPED = "mapped"
SUPPORTED_WORKSPACE_MODES = {WORKSPACE_MODE_ISOLATED, WORKSPACE_MODE_MAPPED}
DEFAULT_WORKSPACE_MODE = WORKSPACE_MODE_ISOLATED


def _compose_file(project_dir: Path) -> Path:
    return project_dir / "docker-compose.yml"


def _meta_file(project_dir: Path) -> Path:
    return project_dir / ".devenv.json"


def _sanitize_project_name(project_name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", project_name.lower().strip())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned


def _normalize_workspace_mode(mode: str | None) -> str:
    normalized = (mode or DEFAULT_WORKSPACE_MODE).strip().lower()
    return normalized if normalized in SUPPORTED_WORKSPACE_MODES else ""


def _load_project_meta(project_dir: Path) -> dict:
    meta_path = _meta_file(project_dir)
    if not meta_path.exists():
        return {}

    try:
        meta = json.loads(meta_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    return meta if isinstance(meta, dict) else {}


def _workspace_mode_for_project(project_dir: Path) -> str:
    meta = _load_project_meta(project_dir)
    mode = _normalize_workspace_mode(meta.get("workspace_mode"))
    if mode:
        return mode

    # Backward compatibility with older environments that always used host bind-mounts.
    return WORKSPACE_MODE_MAPPED


def _load_stack_for_project(project_dir: Path) -> StackTemplate | None:
    """Resolve stack template metadata for an existing project."""
    meta = _load_project_meta(project_dir)
    stack_name = meta.get("stack")
    if not isinstance(stack_name, str):
        return None
    return get_stack(stack_name)


def _is_node_or_bun_stack(stack: StackTemplate) -> bool:
    img = stack.base_image.lower()
    return "node" in img or "bun" in img or "oven/bun" in img


def _validate_relative_file_path(file_path: str) -> tuple[bool, str]:
    normalized = file_path.replace("\\", "/").strip()
    if not normalized:
        return False, ""

    relative = PurePosixPath(normalized)
    if relative.is_absolute() or ".." in relative.parts:
        return False, ""

    as_posix = relative.as_posix()
    if as_posix in {"", "."}:
        return False, ""

    return True, as_posix


async def _cleanup_unwritable_node_modules(project_dir: Path) -> tuple[bool, str]:
    """
    Remove stale root-owned node_modules created by older compose configs.

    Returns (cleanup_performed, error_message).
    """
    node_modules = project_dir / "node_modules"
    if not node_modules.exists():
        return False, ""

    if os.access(node_modules, os.W_OK | os.X_OK):
        return False, ""

    quoted_dir = shlex.quote(str(project_dir))
    rc, _, stderr = await _run(
        f"docker run --rm -v {quoted_dir}:/cleanup alpine sh -c 'rm -rf /cleanup/node_modules'",
        timeout=60,
    )
    if rc != 0:
        return False, stderr.strip()

    return True, ""


def _generate_compose(
    project_name: str,
    stack: StackTemplate,
    workspace_mode: str,
    extra_ports: list[str] | None = None,
) -> str:
    """Generate docker-compose.yml content for a project."""
    ports = [f"{stack.default_port}:{stack.default_port}"]
    if extra_ports:
        ports.extend(extra_ports)

    ports_yaml = "\n".join(f'      - "{p}"' for p in ports)

    user_section = ""
    volume_section = ""
    if workspace_mode == WORKSPACE_MODE_MAPPED:
        uid = os.getuid()
        gid = os.getgid()
        user_section = f"    user: \"{uid}:{gid}\"\n"
        volume_section = (
            "    volumes:\n"
            f"      - .:{stack.workdir}\n"
        )
    else:
        # Isolated mode keeps /app inside the container image/layers.
        # Force root runtime user so package managers can write to /app
        # across base images that default to non-root users (e.g. node).
        user_section = "    user: \"0:0\"\n"

    return f"""\
services:
  {project_name}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: devenv-{project_name}
{user_section}{volume_section}    ports:
{ports_yaml}
    working_dir: {stack.workdir}
    stdin_open: true
    tty: true
    restart: unless-stopped
    labels:
      - \"{MANAGED_LABEL}\"
      - \"devenv-mcp.stack={stack.name}\"
      - \"devenv-mcp.project={project_name}\"
      - \"devenv-mcp.workspace_mode={workspace_mode}\"
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


def _migrate_isolated_user_override_if_needed(project_dir: Path, project_name: str) -> bool:
    """
    Remove stale user override from isolated-mode compose files created by older versions.

    Returns True when a migration is applied.
    """
    compose_path = _compose_file(project_dir)
    if not compose_path.exists():
        return False

    workspace_mode = _workspace_mode_for_project(project_dir)
    if workspace_mode != WORKSPACE_MODE_ISOLATED:
        return False

    stack = _load_stack_for_project(project_dir)
    if not stack:
        return False

    try:
        compose_content = compose_path.read_text()
    except OSError:
        return False

    expected_user_line = '\n    user: "0:0"\n'
    if expected_user_line in compose_content:
        return False

    compose_path.write_text(_generate_compose(project_name, stack, workspace_mode))
    return True


def _resolve_project_port(project_dir: Path) -> int:
    """Resolve the primary container port for a project."""
    meta = _load_project_meta(project_dir)
    raw_port = meta.get("port")
    if isinstance(raw_port, int) and raw_port > 0:
        return raw_port

    if isinstance(raw_port, str) and raw_port.isdigit():
        parsed = int(raw_port)
        if parsed > 0:
            return parsed

    stack = _load_stack_for_project(project_dir)
    if stack:
        return stack.default_port

    return 3000


def _write_deploy_scripts(
    output_tar_path: Path,
    project_name: str,
    image_tag: str,
    container_port: int,
) -> dict:
    """
    Generate Linux and Windows helper scripts beside the exported tar.
    """
    script_stem = f"deploy-{project_name}"
    sh_path = output_tar_path.parent / f"{script_stem}.sh"
    ps1_path = output_tar_path.parent / f"{script_stem}.ps1"
    tar_name = output_tar_path.name
    # Keep deployed container names and labels aligned with the app/project name.
    default_container_name = project_name
    default_container_label = project_name

    sh_content = f"""#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
TAR_PATH="${{SCRIPT_DIR}}/{tar_name}"
IMAGE_TAG="{image_tag}"
CONTAINER_NAME="${{1:-{default_container_name}}}"
HOST_PORT="${{2:-{container_port}}}"
CONTAINER_PORT="{container_port}"
CONTAINER_LABEL="${{3:-{default_container_label}}}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but not installed." >&2
  exit 1
fi

if [ ! -f "${{TAR_PATH}}" ]; then
  echo "Tar archive not found: ${{TAR_PATH}}" >&2
  exit 1
fi

echo "Loading image from ${{TAR_PATH}}..."
docker load -i "${{TAR_PATH}}"

if docker ps -a --format '{{{{.Names}}}}' | grep -Fxq "${{CONTAINER_NAME}}"; then
  echo "Removing existing container ${{CONTAINER_NAME}}..."
  docker rm -f "${{CONTAINER_NAME}}" >/dev/null
fi

echo "Starting container ${{CONTAINER_NAME}} on host port ${{HOST_PORT}}..."
docker run -d \
  --name "${{CONTAINER_NAME}}" \
  --label "devenv-mcp.project=${{CONTAINER_LABEL}}" \
  -p "${{HOST_PORT}}:${{CONTAINER_PORT}}" \
  "${{IMAGE_TAG}}"

echo "Done. Open: http://localhost:${{HOST_PORT}}"
"""

    ps1_content = f"""$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TarPath = Join-Path $ScriptDir "{tar_name}"
$ImageTag = "{image_tag}"
$ContainerName = if ($args.Count -ge 1 -and $args[0]) {{ $args[0] }} else {{ "{default_container_name}" }}
$HostPort = if ($args.Count -ge 2 -and $args[1]) {{ $args[1] }} else {{ "{container_port}" }}
$ContainerPort = {container_port}
$ContainerLabel = if ($args.Count -ge 3 -and $args[2]) {{ $args[2] }} else {{ "{default_container_label}" }}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {{
  Write-Error "Docker is required but not installed."
  exit 1
}}

if (-not (Test-Path $TarPath)) {{
  Write-Error "Tar archive not found: $TarPath"
  exit 1
}}

Write-Host "Loading image from $TarPath..."
docker load -i $TarPath

$Existing = (docker ps -a --format "{{{{.Names}}}}") -split "`n" | Where-Object {{ $_ -eq $ContainerName }}
if ($Existing) {{
  Write-Host "Removing existing container $ContainerName..."
  docker rm -f $ContainerName | Out-Null
}}

Write-Host "Starting container $ContainerName on host port $HostPort..."
docker run -d --name $ContainerName --label "devenv-mcp.project=$ContainerLabel" -p "$HostPort:$ContainerPort" $ImageTag | Out-Null

Write-Host "Done. Open: http://localhost:$HostPort"
"""

    sh_path.write_text(sh_content)
    sh_path.chmod(0o755)
    ps1_path.write_text(ps1_content)

    return {
        "linux_sh": str(sh_path),
        "windows_ps1": str(ps1_path),
        "container_port": container_port,
        "default_host_port": container_port,
        "default_container_name": default_container_name,
        "default_container_label": default_container_label,
    }


class DockerManager:
    """Manages Docker-based development environments."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else PROJECTS_BASE

    def _project_dir(self, safe_project_name: str) -> Path:
        return self.base_dir / safe_project_name

    def _normalize_project_name(self, project_name: str) -> tuple[bool, str, str]:
        safe_name = _sanitize_project_name(project_name)
        if not safe_name:
            return (
                False,
                "",
                "Invalid project name. Use letters, numbers, spaces, or hyphens.",
            )
        return True, safe_name, ""

    def _resolve_existing_project(
        self, project_name: str
    ) -> tuple[bool, str, Path | None, str]:
        valid, safe_name, error = self._normalize_project_name(project_name)
        if not valid:
            return False, "", None, error

        project_dir = self._project_dir(safe_name)
        if not _compose_file(project_dir).exists():
            return False, safe_name, None, f"No environment found: {project_name}"

        return True, safe_name, project_dir, ""

    async def _compose_exec(
        self,
        project_dir: Path,
        safe_project_name: str,
        command: str,
        timeout: int = 120,
    ) -> tuple[int, str, str]:
        cmd = (
            f"docker compose exec -T {shlex.quote(safe_project_name)} "
            f"sh -lc {shlex.quote(command)}"
        )
        return await _run(cmd, cwd=project_dir, timeout=timeout)

    async def create_environment(
        self,
        project_name: str,
        stack_name: str,
        extra_packages: list[str] | None = None,
        workspace_mode: str = DEFAULT_WORKSPACE_MODE,
    ) -> dict:
        """
        Create a new development environment.
        """
        stack = get_stack(stack_name)
        if not stack:
            available = [s["name"] for s in list_stacks()]
            return {
                "success": False,
                "error": f"Unknown stack '{stack_name}'. Available: {', '.join(available)}",
            }

        valid, safe_name, error = self._normalize_project_name(project_name)
        if not valid:
            return {"success": False, "error": error}

        normalized_mode = _normalize_workspace_mode(workspace_mode)
        if not normalized_mode:
            return {
                "success": False,
                "error": (
                    f"Invalid workspace_mode '{workspace_mode}'. "
                    f"Use one of: {', '.join(sorted(SUPPORTED_WORKSPACE_MODES))}."
                ),
            }

        project_dir = self._project_dir(safe_name)
        if project_dir.exists() and any(project_dir.iterdir()):
            return {
                "success": False,
                "error": f"Project directory already exists and is not empty: {project_dir}",
            }

        project_dir.mkdir(parents=True, exist_ok=True)

        if stack.scaffold_files:
            for filename, content in stack.scaffold_files.items():
                filepath = project_dir / filename
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(content)

        dockerfile_content = stack.dockerfile
        if extra_packages:
            extra = " ".join(extra_packages)
            if "node" in stack.base_image.lower():
                dockerfile_content += f"\nRUN npm install -g {extra}\n"
            elif "bun" in stack.base_image.lower():
                dockerfile_content += f"\nRUN bun add -g {extra}\n"
            elif "python" in stack.base_image.lower():
                dockerfile_content += f"\nRUN pip install --no-cache-dir {extra}\n"
            elif "alpine" in stack.base_image.lower():
                dockerfile_content += f"\nRUN apk add --no-cache {extra}\n"
            elif "slim" in stack.base_image.lower():
                dockerfile_content += (
                    "\nRUN apt-get update && "
                    f"apt-get install -y {extra} && rm -rf /var/lib/apt/lists/*\n"
                )

        (project_dir / "Dockerfile").write_text(dockerfile_content)

        compose_content = _generate_compose(safe_name, stack, normalized_mode)
        _compose_file(project_dir).write_text(compose_content)

        meta = {
            "project_name": safe_name,
            "stack": stack_name,
            "port": stack.default_port,
            "base_image": stack.base_image,
            "workspace_mode": normalized_mode,
            "host_app_dir": str(project_dir) if normalized_mode == WORKSPACE_MODE_MAPPED else None,
            "config_dir": str(project_dir),
        }
        _meta_file(project_dir).write_text(json.dumps(meta, indent=2))

        rc, stdout, stderr = await _run(
            "docker compose up -d --build", cwd=project_dir, timeout=600
        )
        if rc != 0:
            return {
                "success": False,
                "error": f"Docker build/start failed:\n{stderr}\n{stdout}",
                "config_dir": str(project_dir),
            }

        if stack.init_commands:
            for init_cmd in stack.init_commands:
                cmd_rc, cmd_stdout, cmd_stderr = await self._compose_exec(
                    project_dir,
                    safe_name,
                    init_cmd,
                    timeout=300,
                )
                if cmd_rc != 0:
                    return {
                        "success": False,
                        "error": (
                            f"Init command failed: {init_cmd}\n"
                            f"stdout:\n{cmd_stdout}\n"
                            f"stderr:\n{cmd_stderr}"
                        ),
                        "project_name": safe_name,
                        "config_dir": str(project_dir),
                    }
            await _run("docker compose restart", cwd=project_dir)

        mode_note = (
            "Source files stay inside the container image/layer. "
            "Use read_file/write_file/exec_command to edit and run commands."
            if normalized_mode == WORKSPACE_MODE_ISOLATED
            else f"Application files are bind-mounted at: {project_dir}"
        )

        return {
            "success": True,
            "project_name": safe_name,
            "config_dir": str(project_dir),
            "host_app_dir": str(project_dir)
            if normalized_mode == WORKSPACE_MODE_MAPPED
            else None,
            "workspace_mode": normalized_mode,
            "stack": stack_name,
            "port": stack.default_port,
            "container_name": f"devenv-{safe_name}",
            "url": f"http://localhost:{stack.default_port}",
            "message": (
                f"Environment '{safe_name}' created with {stack.display_name}. "
                f"Mode: {normalized_mode}. {mode_note} "
                f"Access at http://localhost:{stack.default_port}."
            ),
        }

    async def start_environment(self, project_name: str) -> dict:
        found, safe_name, project_dir, error = self._resolve_existing_project(project_name)
        if not found or project_dir is None:
            return {"success": False, "error": error}

        _migrate_isolated_user_override_if_needed(project_dir, safe_name)
        stack = _load_stack_for_project(project_dir)
        workspace_mode = _workspace_mode_for_project(project_dir)
        if stack and _is_node_or_bun_stack(stack) and workspace_mode == WORKSPACE_MODE_MAPPED:
            _, cleanup_error = await _cleanup_unwritable_node_modules(project_dir)
            if cleanup_error:
                return {
                    "success": False,
                    "error": (
                        "Failed to clean stale node_modules permissions. "
                        f"Details: {cleanup_error}"
                    ),
                }

        rc, _, stderr = await _run("docker compose up -d", cwd=project_dir)
        if rc != 0:
            return {"success": False, "error": stderr}

        return {
            "success": True,
            "project_name": safe_name,
            "message": "Environment started.",
        }

    async def stop_environment(self, project_name: str) -> dict:
        found, safe_name, project_dir, error = self._resolve_existing_project(project_name)
        if not found or project_dir is None:
            return {"success": False, "error": error}

        rc, _, stderr = await _run("docker compose stop", cwd=project_dir)
        if rc != 0:
            return {"success": False, "error": stderr}

        return {
            "success": True,
            "project_name": safe_name,
            "message": "Environment stopped.",
        }

    async def destroy_environment(self, project_name: str, remove_files: bool = True) -> dict:
        found, safe_name, project_dir, error = self._resolve_existing_project(project_name)
        if not found or project_dir is None:
            return {"success": False, "error": error}

        # Full teardown: stop/remove containers + volumes + service images.
        down_rc, _, down_stderr = await _run(
            "docker compose down -v --rmi all --remove-orphans",
            cwd=project_dir,
        )

        # Defensive cleanup in case compose metadata drifted.
        container_name = f"devenv-{safe_name}"
        await _run(f"docker rm -f {shlex.quote(container_name)}", timeout=60)

        # Remove any remaining containers carrying the project label.
        label_rc, label_stdout, label_stderr = await _run(
            (
                "docker ps -aq "
                f"--filter label={shlex.quote(f'devenv-mcp.project={safe_name}')}"
            ),
            timeout=60,
        )
        if label_rc == 0 and label_stdout.strip():
            for cid in {line.strip() for line in label_stdout.splitlines() if line.strip()}:
                await _run(f"docker rm -f {shlex.quote(cid)}", timeout=60)

        # Remove associated images, including default export tags for this app.
        image_ids: set[str] = set()
        image_queries = [
            f"docker images -q --filter label={shlex.quote(f'com.docker.compose.project={safe_name}')}",
            f"docker images -q --filter reference={shlex.quote(f'devenv-{safe_name}:*')}",
            f"docker images -q --filter reference={shlex.quote(f'devenv-export-{safe_name}:*')}",
        ]
        for query in image_queries:
            img_rc, img_stdout, _ = await _run(query, timeout=60)
            if img_rc == 0 and img_stdout.strip():
                image_ids.update(line.strip() for line in img_stdout.splitlines() if line.strip())

        for image_id in image_ids:
            await _run(f"docker rmi -f {shlex.quote(image_id)}", timeout=120)

        if down_rc != 0 and not image_ids and not label_stdout.strip():
            return {
                "success": False,
                "error": (
                    "Failed to fully destroy environment. "
                    f"compose down error: {down_stderr or label_stderr}"
                ),
            }

        result = {
            "success": True,
            "project_name": safe_name,
            "message": f"Environment '{safe_name}' destroyed.",
        }

        if remove_files:
            if project_dir.exists():
                quoted_project_dir = shlex.quote(str(project_dir))
                await _run(
                    (
                        "docker run --rm "
                        f"-v {quoted_project_dir}:/cleanup "
                        "alpine sh -c 'find /cleanup -mindepth 1 -delete'"
                    ),
                    timeout=60,
                )
            shutil.rmtree(project_dir, ignore_errors=True)
            result["message"] += " Files removed."

        return result

    async def list_environments(self) -> dict:
        if not self.base_dir.exists():
            return {"success": True, "environments": []}

        environments = []
        for item in sorted(self.base_dir.iterdir()):
            if not item.is_dir() or not _compose_file(item).exists():
                continue

            meta = _load_project_meta(item)

            rc, stdout, _ = await _run("docker compose ps --format json", cwd=item)
            status = "unknown"
            if rc == 0 and stdout.strip():
                try:
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

            workspace_mode = _normalize_workspace_mode(meta.get("workspace_mode"))
            if not workspace_mode:
                workspace_mode = WORKSPACE_MODE_MAPPED

            environments.append(
                {
                    "project_name": item.name,
                    "host_app_dir": str(item)
                    if workspace_mode == WORKSPACE_MODE_MAPPED
                    else None,
                    "stack": meta.get("stack", "unknown"),
                    "port": meta.get("port", "unknown"),
                    "workspace_mode": workspace_mode,
                    "status": status,
                }
            )
        return {"success": True, "environments": environments}

    async def get_environment_info(self, project_name: str) -> dict:
        found, safe_name, project_dir, error = self._resolve_existing_project(project_name)
        if not found or project_dir is None:
            return {"success": False, "error": error}

        meta = _load_project_meta(project_dir)
        workspace_mode = _normalize_workspace_mode(meta.get("workspace_mode"))
        if not workspace_mode:
            workspace_mode = WORKSPACE_MODE_MAPPED

        rc, stdout, _ = await _run("docker compose ps --format json", cwd=project_dir)
        container_info = {}
        if rc == 0 and stdout.strip():
            try:
                lines = [
                    json.loads(line) for line in stdout.strip().split("\n") if line.strip()
                ]
                if lines:
                    container_info = lines[0]
            except json.JSONDecodeError:
                pass

        files = (
            [f.name for f in sorted(project_dir.iterdir()) if not f.name.startswith(".")]
            if project_dir.exists()
            else []
        )

        return {
            "success": True,
            "project_name": safe_name,
            "workspace_mode": workspace_mode,
            "host_app_dir": str(project_dir)
            if workspace_mode == WORKSPACE_MODE_MAPPED
            else None,
            "stack": meta.get("stack", "unknown"),
            "port": meta.get("port", "unknown"),
            "base_image": meta.get("base_image", "unknown"),
            "container_status": container_info.get("State", "unknown"),
            "container_name": container_info.get("Name", f"devenv-{safe_name}"),
            "files": files,
            "url": f"http://localhost:{meta.get('port', '?')}",
        }

    async def exec_command(self, project_name: str, command: str) -> dict:
        found, safe_name, project_dir, error = self._resolve_existing_project(project_name)
        if not found or project_dir is None:
            return {"success": False, "error": error}

        rc, stdout, stderr = await self._compose_exec(
            project_dir,
            safe_name,
            command,
            timeout=120,
        )
        return {
            "success": rc == 0,
            "project_name": safe_name,
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": rc,
        }

    async def write_file(self, project_name: str, file_path: str, content: str) -> dict:
        found, safe_name, project_dir, error = self._resolve_existing_project(project_name)
        if not found or project_dir is None:
            return {"success": False, "error": error}

        valid, relative_path = _validate_relative_file_path(file_path)
        if not valid:
            return {"success": False, "error": "Invalid file path."}

        workspace_mode = _workspace_mode_for_project(project_dir)

        if workspace_mode == WORKSPACE_MODE_MAPPED:
            project_root = project_dir.resolve()
            target = (project_root / relative_path).resolve()
            try:
                target.relative_to(project_root)
            except ValueError:
                return {"success": False, "error": "Path traversal not allowed."}

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
                return {
                    "success": True,
                    "project_name": safe_name,
                    "workspace_mode": workspace_mode,
                    "file_path": relative_path,
                    "host_path": str(target),
                    "message": "File written.",
                }
            except OSError as exc:
                return {"success": False, "error": str(exc)}

        container_path = (PurePosixPath("/app") / relative_path).as_posix()
        parent_path = PurePosixPath(container_path).parent.as_posix()

        mkdir_rc, _, mkdir_err = await self._compose_exec(
            project_dir,
            safe_name,
            f"mkdir -p {shlex.quote(parent_path)}",
            timeout=60,
        )
        if mkdir_rc != 0:
            return {
                "success": False,
                "error": f"Failed to prepare directory: {mkdir_err}",
            }

        encoded = base64.b64encode(content.encode()).decode()
        write_rc, _, write_err = await self._compose_exec(
            project_dir,
            safe_name,
            f"printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(container_path)}",
            timeout=60,
        )
        if write_rc != 0:
            return {
                "success": False,
                "error": f"Failed to write file in container: {write_err}",
            }

        return {
            "success": True,
            "project_name": safe_name,
            "workspace_mode": workspace_mode,
            "file_path": relative_path,
            "container_path": container_path,
            "message": "File written in container.",
        }

    async def read_file(self, project_name: str, file_path: str) -> dict:
        found, safe_name, project_dir, error = self._resolve_existing_project(project_name)
        if not found or project_dir is None:
            return {"success": False, "error": error}

        valid, relative_path = _validate_relative_file_path(file_path)
        if not valid:
            return {"success": False, "error": "Invalid file path."}

        workspace_mode = _workspace_mode_for_project(project_dir)

        if workspace_mode == WORKSPACE_MODE_MAPPED:
            project_root = project_dir.resolve()
            target = (project_root / relative_path).resolve()
            try:
                target.relative_to(project_root)
            except ValueError:
                return {"success": False, "error": "Path traversal not allowed."}

            if not target.exists():
                return {"success": False, "error": f"File not found: {relative_path}"}

            try:
                return {
                    "success": True,
                    "project_name": safe_name,
                    "workspace_mode": workspace_mode,
                    "file_path": relative_path,
                    "content": target.read_text(),
                }
            except OSError as exc:
                return {"success": False, "error": str(exc)}

        container_path = (PurePosixPath("/app") / relative_path).as_posix()
        rc, stdout, stderr = await self._compose_exec(
            project_dir,
            safe_name,
            f"cat {shlex.quote(container_path)}",
            timeout=60,
        )
        if rc != 0:
            return {
                "success": False,
                "error": f"File not found or unreadable in container: {stderr.strip()}",
            }

        return {
            "success": True,
            "project_name": safe_name,
            "workspace_mode": workspace_mode,
            "file_path": relative_path,
            "content": stdout,
        }

    async def export_environment(
        self,
        project_name: str,
        output_tar_path: str | None = None,
        image_tag: str | None = None,
    ) -> dict:
        """
        Export a development environment as a portable Docker image tar archive.
        """
        found, safe_name, project_dir, error = self._resolve_existing_project(project_name)
        if not found or project_dir is None:
            return {"success": False, "error": error}

        workspace_mode = _workspace_mode_for_project(project_dir)
        container_name = f"devenv-{safe_name}"
        final_image_tag = image_tag or f"devenv-export-{safe_name}:latest"
        commit_output = ""

        if workspace_mode == WORKSPACE_MODE_MAPPED:
            token = uuid.uuid4().hex[:12]
            temp_snapshot_image = f"devenv-export-tmp-{safe_name}:{token}"
            temp_container_name = f"devenv-export-{safe_name}-{token}"
            temp_container_created = False
            temp_snapshot_created = False

            try:
                # Snapshot runtime state first (packages/tools installed in the running container).
                base_commit_rc, base_commit_stdout, base_commit_stderr = await _run(
                    (
                        f"docker commit {shlex.quote(container_name)} "
                        f"{shlex.quote(temp_snapshot_image)}"
                    ),
                    timeout=120,
                )
                if base_commit_rc != 0:
                    return {
                        "success": False,
                        "error": (
                            "Failed to snapshot mapped environment container. "
                            "Ensure the environment exists and is running. "
                            f"stderr: {base_commit_stderr.strip()}"
                        ),
                    }
                temp_snapshot_created = True

                run_rc, _, run_stderr = await _run(
                    (
                        "docker run -d "
                        f"--name {shlex.quote(temp_container_name)} "
                        f"{shlex.quote(temp_snapshot_image)} "
                        "sh -lc "
                        f"{shlex.quote('while :; do sleep 3600; done')}"
                    ),
                    timeout=60,
                )
                if run_rc != 0:
                    return {
                        "success": False,
                        "error": (
                            "Failed to create temporary export container for mapped mode. "
                            f"stderr: {run_stderr.strip()}"
                        ),
                    }
                temp_container_created = True

                clear_rc, _, clear_stderr = await _run(
                    (
                        "docker exec -u 0 "
                        f"{shlex.quote(temp_container_name)} "
                        "sh -lc "
                        f"{shlex.quote('mkdir -p /app && rm -rf /app/* /app/.[!.]* /app/..?*')}"
                    ),
                    timeout=120,
                )
                if clear_rc != 0:
                    return {
                        "success": False,
                        "error": (
                            "Failed to prepare /app in temporary export container. "
                            f"stderr: {clear_stderr.strip()}"
                        ),
                    }

                copy_rc, _, copy_stderr = await _run(
                    (
                        "docker cp "
                        f"{shlex.quote(str(project_dir / '.'))} "
                        f"{shlex.quote(f'{temp_container_name}:/app')}"
                    ),
                    timeout=180,
                )
                if copy_rc != 0:
                    return {
                        "success": False,
                        "error": (
                            "Failed to copy mapped project files into export container. "
                            f"stderr: {copy_stderr.strip()}"
                        ),
                    }

                final_commit_rc, final_commit_stdout, final_commit_stderr = await _run(
                    (
                        f"docker commit {shlex.quote(temp_container_name)} "
                        f"{shlex.quote(final_image_tag)}"
                    ),
                    timeout=120,
                )
                if final_commit_rc != 0:
                    return {
                        "success": False,
                        "error": (
                            "Failed to finalize portable export image from mapped environment. "
                            f"stderr: {final_commit_stderr.strip()}"
                        ),
                    }

                commit_output = (
                    f"base_snapshot={base_commit_stdout.strip()} "
                    f"final_snapshot={final_commit_stdout.strip()}"
                ).strip()
            finally:
                if temp_container_created:
                    await _run(
                        f"docker rm -f {shlex.quote(temp_container_name)}",
                        timeout=60,
                    )
                if temp_snapshot_created:
                    await _run(
                        f"docker rmi {shlex.quote(temp_snapshot_image)}",
                        timeout=60,
                    )
        else:
            commit_rc, commit_stdout, commit_stderr = await _run(
                (
                    f"docker commit {shlex.quote(container_name)} "
                    f"{shlex.quote(final_image_tag)}"
                ),
                timeout=120,
            )
            if commit_rc != 0:
                return {
                    "success": False,
                    "error": (
                        "Failed to snapshot container. Ensure the environment exists "
                        f"and is running. stderr: {commit_stderr.strip()}"
                    ),
                }
            commit_output = commit_stdout.strip()

        if output_tar_path:
            output_path = Path(output_tar_path).expanduser()
            if not output_path.is_absolute():
                output_path = (project_dir / output_path).resolve()
        else:
            output_path = project_dir / f"{safe_name}.tar"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        save_rc, _, save_stderr = await _run(
            (
                "docker save "
                f"-o {shlex.quote(str(output_path))} "
                f"{shlex.quote(final_image_tag)}"
            ),
            timeout=180,
        )
        if save_rc != 0:
            return {
                "success": False,
                "error": f"Failed to export image tar: {save_stderr.strip()}",
            }

        container_port = _resolve_project_port(project_dir)
        deploy_scripts = _write_deploy_scripts(
            output_tar_path=output_path,
            project_name=safe_name,
            image_tag=final_image_tag,
            container_port=container_port,
        )

        return {
            "success": True,
            "project_name": safe_name,
            "container_name": container_name,
            "workspace_mode": workspace_mode,
            "image_tag": final_image_tag,
            "output_tar": str(output_path),
            "deploy_scripts": deploy_scripts,
            "message": (
                "Environment exported. Deploy scripts generated next to the tar: "
                f"{Path(deploy_scripts['linux_sh']).name}, {Path(deploy_scripts['windows_ps1']).name}."
            ),
            "commit_output": commit_output,
        }
