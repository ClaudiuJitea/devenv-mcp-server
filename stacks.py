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
# PHP stacks
# ---------------------------------------------------------------------------

def laravel_stack() -> StackTemplate:
    """Laravel (PHP) development environment."""
    return StackTemplate(
        name="laravel",
        display_name="Laravel",
        description="Laravel PHP framework development environment",
        base_image="php:8.3-fpm-alpine",
        default_port=8000,
        dockerfile="""\
FROM php:8.3-fpm-alpine
WORKDIR /app
RUN apk add --no-cache curl git zip unzip bash
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer
RUN chmod -R 777 /app
COPY . .
EXPOSE 8000
CMD ["php", "artisan", "serve", "--host=0.0.0.0", "--port=8000"]
""",
        scaffold_files={},
        init_commands=[
            "composer create-project --prefer-dist laravel/laravel tmp_app",
            "cp -a tmp_app/. . && rm -rf tmp_app",
        ],
    )

def symfony_stack() -> StackTemplate:
    """Symfony (PHP) development environment."""
    return StackTemplate(
        name="symfony",
        display_name="Symfony",
        description="Symfony PHP framework development environment",
        base_image="php:8.3-fpm-alpine",
        default_port=8000,
        dockerfile="""\
FROM php:8.3-fpm-alpine
WORKDIR /app
RUN apk add --no-cache curl git zip unzip bash
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer
RUN curl -sS https://get.symfony.com/cli/installer | bash
RUN mv /root/.symfony*/bin/symfony /usr/local/bin/symfony
RUN chmod -R 777 /app
COPY . .
EXPOSE 8000
CMD ["symfony", "server:start", "--port=8000", "--no-tls", "--allow-all-ip"]
""",
        scaffold_files={},
        init_commands=[
            "composer create-project symfony/skeleton tmp_app",
            "cp -a tmp_app/. . && rm -rf tmp_app",
        ],
    )

# ---------------------------------------------------------------------------
# Additional Node.js & Bun stacks
# ---------------------------------------------------------------------------

def nestjs_stack() -> StackTemplate:
    """NestJS (Node.js) development environment."""
    return StackTemplate(
        name="nestjs",
        display_name="NestJS",
        description="NestJS Node.js framework with hot-reload",
        base_image="node:22-slim",
        default_port=3000,
        dockerfile="""\
FROM node:22-slim
WORKDIR /app
RUN npm install -g @nestjs/cli
RUN chmod -R 777 /usr/local /app
COPY . .
EXPOSE 3000
CMD ["npm", "run", "start:dev"]
""",
        scaffold_files={},
        init_commands=[
            "nest new project --package-manager npm --skip-git",
            "cp -a project/. . && rm -rf project",
            "npm install",
        ],
    )

def bun_hono_stack() -> StackTemplate:
    """Hono (Bun) development environment."""
    return StackTemplate(
        name="bun-hono",
        display_name="Hono (Bun)",
        description="Hono web framework using Bun runtime",
        base_image="oven/bun:1-alpine",
        default_port=3000,
        dockerfile="""\
FROM oven/bun:1-alpine
WORKDIR /app
RUN chmod -R 777 /app
COPY . .
EXPOSE 3000
CMD ["bun", "run", "--hot", "src/index.ts"]
""",
        scaffold_files={
            "src/index.ts": """\
import { Hono } from 'hono'

const app = new Hono()

app.get('/', (c) => {
  return c.text('Hello from Hono on Bun!')
})

export default {
  port: 3000,
  fetch: app.fetch,
}
""",
            "package.json": """\
{
  "name": "bun-hono-app",
  "scripts": {
    "dev": "bun run --hot src/index.ts"
  },
  "dependencies": {
    "hono": "^4.0.0"
  },
  "devDependencies": {
    "@types/bun": "latest"
  }
}
""",
            "tsconfig.json": """\
{
  "compilerOptions": {
    "strict": true,
    "lib": ["ESNext"],
    "module": "esmodule",
    "moduleResolution": "bundler",
    "target": "ESNext",
    "types": ["@types/bun"]
  }
}
"""
        },
        init_commands=[
            "bun install",
        ],
    )

# ---------------------------------------------------------------------------
# Go, Rust & Nginx stacks
# ---------------------------------------------------------------------------

def rust_axum_stack() -> StackTemplate:
    """Axum (Rust) development environment."""
    return StackTemplate(
        name="rust-axum",
        display_name="Axum (Rust)",
        description="Rust web framework Axum with cargo-watch",
        base_image="rust:1-slim",
        default_port=8080,
        dockerfile="""\
FROM rust:1-slim
WORKDIR /app
RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*
RUN cargo install cargo-watch
RUN chmod -R 777 /usr/local/cargo /app
ENV CARGO_HOME=/usr/local/cargo
COPY . .
EXPOSE 8080
CMD ["cargo", "watch", "-x", "run"]
""",
        scaffold_files={
            "Cargo.toml": """\
[package]
name = "rust-axum-app"
version = "0.1.0"
edition = "2021"

[dependencies]
axum = "0.7"
tokio = { version = "1.0", features = ["full"] }
""",
            "src/main.rs": """\
use axum::{routing::get, Router};

#[tokio::main]
async fn main() {
    let app = Router::new().route("/", get(|| async { "Hello from Axum!" }));
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await.unwrap();
    println!("Listening on {}", listener.local_addr().unwrap());
    axum::serve(listener, app).await.unwrap();
}
"""
        },
        init_commands=[
            "cargo build",
        ],
    )

def go_gin_stack() -> StackTemplate:
    """Gin (Go) development environment."""
    return StackTemplate(
        name="go-gin",
        display_name="Gin (Go)",
        description="Go web framework Gin with Air hot-reload",
        base_image="golang:1.24-alpine",
        default_port=8080,
        dockerfile="""\
FROM golang:1.24-alpine
WORKDIR /app
RUN go install github.com/air-verse/air@latest
RUN chmod -R 777 /go /app
ENV GOPATH=/go
COPY . .
EXPOSE 8080
CMD ["air", "-c", ".air.toml"]
""",
        scaffold_files={
            "main.go": """\
package main

import (
	"net/http"
	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()
	r.GET("/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"message": "Hello from Gin!",
		})
	})
	r.Run("0.0.0.0:8080")
}
""",
            ".air.toml": """\
root = "."
tmp_dir = "tmp"

[build]
cmd = "go build -o ./tmp/main ."
bin = "./tmp/main"
include_ext = ["go", "tpl", "tmpl", "html"]
exclude_dir = ["assets", "tmp", "vendor", "testdata"]
delay = 1000

[log]
time = false

[color]
build = "yellow"
main = "magenta"
runner = "green"
watcher = "cyan"
"""
        },
        init_commands=[
            "go mod init go-gin-app",
            "go get -u github.com/gin-gonic/gin",
            "go mod tidy",
        ],
    )

def nginx_static_stack() -> StackTemplate:
    """Nginx (Static) development environment."""
    return StackTemplate(
        name="nginx-static",
        display_name="Nginx Static",
        description="Nginx server for static HTML/CSS/JS",
        base_image="nginx:alpine",
        default_port=80,
        dockerfile="""\
FROM nginx:alpine
WORKDIR /app
RUN chmod -R 777 /usr/share/nginx/html
COPY ./html /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
""",
        scaffold_files={
            "html/index.html": """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nginx Static App</title>
</head>
<body>
    <h1>Hello from Nginx!</h1>
    <p>Your static files are ready.</p>
</body>
</html>
"""
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
    "laravel": laravel_stack,
    "symfony": symfony_stack,
    "nestjs": nestjs_stack,
    "bun-hono": bun_hono_stack,
    "rust-axum": rust_axum_stack,
    "go-gin": go_gin_stack,
    "nginx-static": nginx_static_stack,
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
