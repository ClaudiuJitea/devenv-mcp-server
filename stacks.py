"""
Stack template definitions for the MCP Dev Environment Server.

Each stack defines a complete Docker-based development environment:
- Dockerfile content
- docker-compose service configuration
- Initial project scaffold files
- Post-creation initialization commands
"""

from dataclasses import dataclass, field


@dataclass
class StackTemplate:
    """Defines a complete development environment stack."""

    name: str
    display_name: str
    description: str
    base_image: str
    default_port: int
    dockerfile: str
    compose_service: dict = field(default_factory=dict)
    scaffold_files: dict = field(default_factory=dict)
    init_commands: list = field(default_factory=list)
    workdir: str = "/app"


# ---------------------------------------------------------------------------
# Python stacks
# ---------------------------------------------------------------------------

def flask_stack() -> StackTemplate:
    """Flask (Python) development environment."""
    return StackTemplate(
        name="flask",
        display_name="Flask",
        description="Python Flask web framework with hot-reload",
        base_image="python:3.12-slim",
        default_port=5000,
        dockerfile="""\
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask watchdog
RUN chmod -R 777 /usr/local
COPY . .
ENV FLASK_APP=app.py
ENV FLASK_ENV=development
EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0", "--reload"]
""",
        scaffold_files={
            "app.py": """\
from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello():
    return "<h1>Hello from Flask!</h1><p>Your dev environment is ready.</p>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
""",
            "requirements.txt": """\
flask
watchdog
""",
        },
        init_commands=[
            "pip install --no-cache-dir -r requirements.txt",
        ],
    )


def django_stack() -> StackTemplate:
    """Django (Python) development environment."""
    return StackTemplate(
        name="django",
        display_name="Django",
        description="Python Django web framework with auto-reload",
        base_image="python:3.12-slim",
        default_port=8000,
        dockerfile="""\
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir django
RUN chmod -R 777 /usr/local
COPY . .
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
""",
        scaffold_files={
            "requirements.txt": "django\n",
        },
        init_commands=[
            "pip install --no-cache-dir django",
            "django-admin startproject project .",
        ],
    )


def fastapi_stack() -> StackTemplate:
    """FastAPI (Python) development environment."""
    return StackTemplate(
        name="fastapi",
        display_name="FastAPI",
        description="Python FastAPI with Uvicorn hot-reload",
        base_image="python:3.12-slim",
        default_port=8000,
        dockerfile="""\
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn[standard]
RUN chmod -R 777 /usr/local
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--reload"]
""",
        scaffold_files={
            "main.py": """\
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello from FastAPI! Your dev environment is ready."}
""",
            "requirements.txt": """\
fastapi
uvicorn[standard]
""",
        },
        init_commands=[
            "pip install --no-cache-dir -r requirements.txt",
        ],
    )


# ---------------------------------------------------------------------------
# Node.js stacks
# ---------------------------------------------------------------------------

def nextjs_stack() -> StackTemplate:
    """Next.js (React) development environment."""
    return StackTemplate(
        name="nextjs",
        display_name="Next.js",
        description="Next.js React framework with hot-reload",
        base_image="node:20-slim",
        default_port=3000,
        dockerfile="""\
FROM node:20-slim
WORKDIR /app
RUN chmod -R 777 /usr/local
ENV NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000
CMD ["npm", "run", "dev"]
""",
        scaffold_files={},
        init_commands=[
            "npx -y create-next-app@latest ./ --ts --tailwind "
            "--eslint --app --src-dir --import-alias '@/*' --yes",
        ],
    )


def vite_react_stack() -> StackTemplate:
    """Vite + React development environment."""
    return StackTemplate(
        name="vite-react",
        display_name="Vite + React",
        description="Vite-powered React app with HMR",
        base_image="node:20-slim",
        default_port=5173,
        dockerfile="""\
FROM node:20-slim
WORKDIR /app
RUN chmod -R 777 /usr/local
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
""",
        scaffold_files={},
        init_commands=[
            "npm create vite@latest ./ -- --template react",
            "npm install",
        ],
    )


def vite_vue_stack() -> StackTemplate:
    """Vite + Vue development environment."""
    return StackTemplate(
        name="vite-vue",
        display_name="Vite + Vue",
        description="Vite-powered Vue.js app with HMR",
        base_image="node:20-slim",
        default_port=5173,
        dockerfile="""\
FROM node:20-slim
WORKDIR /app
RUN chmod -R 777 /usr/local
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
""",
        scaffold_files={},
        init_commands=[
            "npm create vite@latest ./ -- --template vue",
            "npm install",
        ],
    )


def express_stack() -> StackTemplate:
    """Express.js development environment."""
    return StackTemplate(
        name="express",
        display_name="Express.js",
        description="Express.js Node server with nodemon hot-reload",
        base_image="node:20-slim",
        default_port=3000,
        dockerfile="""\
FROM node:20-slim
WORKDIR /app
RUN npm install -g nodemon
RUN chmod -R 777 /usr/local
COPY . .
EXPOSE 3000
CMD ["nodemon", "index.js"]
""",
        scaffold_files={
            "index.js": """\
const express = require('express');
const app = express();
const port = 3000;

app.get('/', (req, res) => {
  res.send('<h1>Hello from Express!</h1><p>Your dev environment is ready.</p>');
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Server running at http://localhost:${port}`);
});
""",
            "package.json": """\
{
  "name": "express-app",
  "version": "1.0.0",
  "description": "Express.js development environment",
  "main": "index.js",
  "scripts": {
    "start": "node index.js",
    "dev": "nodemon index.js"
  },
  "dependencies": {
    "express": "^4.21.0"
  },
  "devDependencies": {
    "nodemon": "^3.1.0"
  }
}
""",
        },
        init_commands=[
            "npm install",
        ],
    )


def static_html_stack() -> StackTemplate:
    """Static HTML/CSS/JS development environment."""
    return StackTemplate(
        name="static-html",
        display_name="Static HTML",
        description="Simple static HTML/CSS/JS with live-server",
        base_image="node:20-slim",
        default_port=8080,
        dockerfile="""\
FROM node:20-slim
WORKDIR /app
RUN npm install -g live-server
RUN chmod -R 777 /usr/local
COPY . .
EXPOSE 8080
CMD ["live-server", "--port=8080", "--host=0.0.0.0"]
""",
        scaffold_files={
            "index.html": """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Project</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>Hello World!</h1>
    <p>Your dev environment is ready.</p>
    <script src="script.js"></script>
</body>
</html>
""",
            "style.css": """\
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: #1a1a2e;
    color: #eee;
}

h1 {
    font-size: 3rem;
    margin-bottom: 1rem;
}
""",
            "script.js": """\
console.log("Dev environment ready!");
""",
        },
        init_commands=[],
    )


# ---------------------------------------------------------------------------
# Stack registry
# ---------------------------------------------------------------------------

STACK_REGISTRY: dict[str, callable] = {
    "flask": flask_stack,
    "django": django_stack,
    "fastapi": fastapi_stack,
    "nextjs": nextjs_stack,
    "vite-react": vite_react_stack,
    "vite-vue": vite_vue_stack,
    "express": express_stack,
    "static-html": static_html_stack,
}


def get_stack(name: str) -> StackTemplate | None:
    """Get a stack template by name."""
    factory = STACK_REGISTRY.get(name)
    return factory() if factory else None


def list_stacks() -> list[dict]:
    """List all available stacks with metadata."""
    result = []
    for factory in STACK_REGISTRY.values():
        tmpl = factory()
        result.append({
            "name": tmpl.name,
            "display_name": tmpl.display_name,
            "description": tmpl.description,
            "base_image": tmpl.base_image,
            "default_port": tmpl.default_port,
        })
    return result
