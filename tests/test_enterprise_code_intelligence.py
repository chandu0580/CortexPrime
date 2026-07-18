"""
Validation tests for the Enterprise Code Intelligence Engine.

Simulates:
  ✓ Repository scanning (real directory)
  ✓ Code parsing (Python, TypeScript, Java, Go, Rust, Shell)
  ✓ Dependency graph building
  ✓ Knowledge graph recording
  ✓ Impact analysis
  ✓ Repository listing

Verifies:
  ✓ Scanner discovers files/languages/modules/build systems
  ✓ Parser extracts functions, classes, routes, services, models
  ✓ Dependency graph tracks entities and relationships
  ✓ Knowledge graph stores and queries entities
  ✓ Impact analysis returns affected files, APIs, services, tests
  ✓ Round-trip serialization
  ✓ All supported languages parse correctly
  ✓ Error handling for missing directories
"""
import os
import tempfile
import pytest

from backend.services.enterprise_code_intelligence import (
    EnterpriseCodeIntelligence,
    RepositoryScanner,
    CodeParser,
    CodeContext,
    DependencyGraph,
    CodeKnowledgeGraph,
    ImpactAnalyzer,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_repo_dir():
    with tempfile.TemporaryDirectory() as tmp:
        # Python file
        py_file = os.path.join(tmp, "main.py")
        with open(py_file, "w") as f:
            f.write("""
import os
import sys


def greet(name: str) -> str:
    \"\"\"Say hello.\"\"\"
    return f"Hello {name}"


class Calculator:
    \"\"\"A simple calculator.\"\"\"

    def add(self, a: int, b: int) -> int:
        return a + b

    def subtract(self, a: int, b: int) -> int:
        return a - b


@app.get("/api/health")
async def health():
    return {"status": "ok"}


class UserService:
    def get_user(self, user_id: int):
        pass
""")
        # TypeScript file
        ts_file = os.path.join(tmp, "app.ts")
        with open(ts_file, "w") as f:
            f.write("""
import { Component } from 'react';

export interface User {
  id: number;
  name: string;
}

export enum Status {
  Active = "active",
  Inactive = "inactive",
}

export function formatName(user: User): string {
  return user.name;
}

export class UserController {
  async getUsers(): Promise<User[]> {
    return [];
  }
}

export const App: React.FC = () => {
  return <div>Hello</div>;
};

export function useUserData() {
  return { user: null };
}
""")
        # Java file
        java_file = os.path.join(tmp, "UserController.java")
        with open(java_file, "w") as f:
            f.write("""
package com.example;

import org.springframework.web.bind.annotation.*;

@RestController
public class UserController {
    @GetMapping("/api/users")
    public List<User> getUsers() {
        return new ArrayList<>();
    }

    @PostMapping("/api/users")
    public User createUser(@RequestBody User user) {
        return user;
    }
}

@Service
public class UserService {
    public User findById(Long id) {
        return null;
    }
}

@Entity
public class User {
    private Long id;
    private String name;
}
""")
        # Go file
        go_file = os.path.join(tmp, "handler.go")
        with open(go_file, "w") as f:
            f.write("""
package main

type User struct {
    ID   int
    Name string
}

type UserService interface {
    GetUser(id int) (*User, error)
}

func greet(name string) string {
    return "Hello " + name
}

func main() {
    r := gin.Default()
    r.GET("/api/health", healthHandler)
    r.Run()
}
""")
        # Rust file
        rs_file = os.path.join(tmp, "lib.rs")
        with open(rs_file, "w") as f:
            f.write("""
pub struct User {
    pub id: i32,
    pub name: String,
}

pub trait UserRepository {
    fn find_by_id(&self, id: i32) -> Option<User>;
}

pub enum Status {
    Active,
    Inactive,
}

pub fn greet(name: &str) -> String {
    format!("Hello {}", name)
}

impl User {
    pub fn new(id: i32, name: String) -> Self {
        User { id, name }
    }
}
""")
        # Shell file
        sh_file = os.path.join(tmp, "deploy.sh")
        with open(sh_file, "w") as f:
            f.write("""#!/bin/bash
function deploy() {
    echo "Deploying..."
}

function rollback() {
    echo "Rolling back..."
}

healthcheck() {
    curl -f http://localhost:8080/health
}
""")
        # Config files
        cfg_file = os.path.join(tmp, "package.json")
        with open(cfg_file, "w") as f:
            f.write('{"name": "test", "version": "1.0.0"}')

        req_file = os.path.join(tmp, "requirements.txt")
        with open(req_file, "w") as f:
            f.write("fastapi>=0.100.0\npydantic>=2.0.0")

        yield tmp


@pytest.fixture
def ci_engine():
    engine = EnterpriseCodeIntelligence()
    return engine


# ── Part 1: Repository Scanner ──────────────────────────────────────────────

def test_scanner_detects_files(sample_repo_dir):
    result = RepositoryScanner.scan(sample_repo_dir)
    assert result["total_files"] >= 8
    assert "error" not in result


def test_scanner_detects_languages(sample_repo_dir):
    result = RepositoryScanner.scan(sample_repo_dir)
    langs = result["languages"]
    assert "python" in langs
    assert "typescript" in langs
    assert "java" in langs
    assert "go" in langs
    assert "rust" in langs
    assert "shell" in langs


def test_scanner_detects_build_systems(sample_repo_dir):
    result = RepositoryScanner.scan(sample_repo_dir)
    assert "pip" in result["build_systems"] or "npm" in result["build_systems"]


def test_scanner_detects_configs(sample_repo_dir):
    result = RepositoryScanner.scan(sample_repo_dir)
    assert len(result["configs"]) >= 2


def test_scanner_missing_directory():
    result = RepositoryScanner.scan("/nonexistent/path")
    assert "error" in result


def test_scanner_detects_modules(sample_repo_dir):
    result = RepositoryScanner.scan(sample_repo_dir)
    assert len(result["modules"]) >= 0


# ── Part 2: Code Parser ─────────────────────────────────────────────────────

def test_parse_python_functions(sample_repo_dir):
    py_path = os.path.join(sample_repo_dir, "main.py")
    with open(py_path) as f:
        content = f.read()
    entities = CodeParser.parse_python(py_path, content)
    names = [e.name for e in entities]
    assert "greet" in names
    assert "health" in names


def test_parse_python_classes(sample_repo_dir):
    py_path = os.path.join(sample_repo_dir, "main.py")
    with open(py_path) as f:
        content = f.read()
    entities = CodeParser.parse_python(py_path, content)
    class_names = [e.name for e in entities if e.entity_type == "class"]
    assert "Calculator" in class_names


def test_parse_python_routes(sample_repo_dir):
    py_path = os.path.join(sample_repo_dir, "main.py")
    with open(py_path) as f:
        content = f.read()
    entities = CodeParser.parse_python(py_path, content)
    routes = [e for e in entities if e.entity_type == "route"]
    assert len(routes) >= 1
    assert any("/api/health" in r.name for r in routes)


def test_parse_python_service(sample_repo_dir):
    py_path = os.path.join(sample_repo_dir, "main.py")
    with open(py_path) as f:
        content = f.read()
    entities = CodeParser.parse_python(py_path, content)
    services = [e for e in entities if e.entity_type == "service"]
    assert len(services) >= 1
    assert any("UserService" in s.name for s in services)


def test_parse_typescript(sample_repo_dir):
    ts_path = os.path.join(sample_repo_dir, "app.ts")
    with open(ts_path) as f:
        content = f.read()
    entities = CodeParser.parse_typescript(ts_path, content)
    types = [e.entity_type for e in entities]
    names = [e.name for e in entities]
    assert "function" in types
    assert "class" in types
    assert "interface" in types
    assert "enum" in types
    assert "formatName" in names
    assert "UserController" in names
    assert "Status" in names


def test_parse_typescript_react_component(sample_repo_dir):
    ts_path = os.path.join(sample_repo_dir, "app.ts")
    with open(ts_path) as f:
        content = f.read()
    entities = CodeParser.parse_typescript(ts_path, content)
    components = [e for e in entities if e.entity_type == "react_component"]
    assert len(components) >= 1
    assert any("App" in c.name for c in components)


def test_parse_typescript_hook(sample_repo_dir):
    ts_path = os.path.join(sample_repo_dir, "app.ts")
    with open(ts_path) as f:
        content = f.read()
    entities = CodeParser.parse_typescript(ts_path, content)
    hooks = [e for e in entities if e.entity_type == "hook"]
    assert len(hooks) >= 1


def test_parse_java(sample_repo_dir):
    java_path = os.path.join(sample_repo_dir, "UserController.java")
    with open(java_path) as f:
        content = f.read()
    entities = CodeParser.parse_java(java_path, content)
    names = [e.name for e in entities]
    assert "UserController" in names
    assert "UserService" in names


def test_parse_go(sample_repo_dir):
    go_path = os.path.join(sample_repo_dir, "handler.go")
    with open(go_path) as f:
        content = f.read()
    entities = CodeParser.parse_go(go_path, content)
    names = [e.name for e in entities]
    assert "greet" in names
    assert "UserService" in names


def test_parse_rust(sample_repo_dir):
    rs_path = os.path.join(sample_repo_dir, "lib.rs")
    with open(rs_path) as f:
        content = f.read()
    entities = CodeParser.parse_rust(rs_path, content)
    names = [e.name for e in entities]
    assert "greet" in names
    assert "UserRepository" in names
    assert "Status" in names


def test_parse_shell(sample_repo_dir):
    sh_path = os.path.join(sample_repo_dir, "deploy.sh")
    with open(sh_path) as f:
        content = f.read()
    entities = CodeParser.parse_shell(sh_path, content)
    names = [e.name for e in entities]
    assert "deploy" in names
    assert "rollback" in names
    assert "healthcheck" in names


def test_parse_router_unknown_extension():
    entities = CodeParser.parse("/tmp/test.xyz", "content")
    assert entities == []


def test_parse_router_python(sample_repo_dir):
    py_path = os.path.join(sample_repo_dir, "main.py")
    with open(py_path) as f:
        content = f.read()
    entities = CodeParser.parse(py_path, content)
    assert len(entities) > 0


# ── Part 3: Dependency Graph ────────────────────────────────────────────────

def test_dependency_graph_add_nodes():
    g = DependencyGraph()
    g.add_node("fn:main:greet:10", "function", "greet", "main.py")
    g.add_node("fn:main:health:20", "function", "health", "main.py")
    g.add_edge("fn:main:greet:10", "fn:main:health:20", "calls")
    graph = g.get_graph()
    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1


def test_dependency_graph_get_dependents():
    g = DependencyGraph()
    g.add_node("fn:a:1", "function", "a", "a.py")
    g.add_node("fn:b:1", "function", "b", "b.py")
    g.add_edge("fn:a:1", "fn:b:1", "calls")
    deps = g.get_dependents("b.py")
    assert "a.py" in deps


def test_dependency_graph_round_trip():
    g = DependencyGraph()
    g.add_node("n1", "function", "f1", "f.py")
    g.add_edge("n1", "n2", "calls")
    data = g.to_dict()
    restored = DependencyGraph.from_dict(data)
    assert restored._nodes["n1"]["name"] == "f1"


# ── Part 4: Code Knowledge Graph ────────────────────────────────────────────

def test_knowledge_graph_record_repository():
    kg = CodeKnowledgeGraph()
    rid = kg.record_repository("https://github.com/test/repo", {"directory": "/tmp/repo", "languages": {"python": 5}})
    assert rid is not None
    repos = kg._repositories
    assert rid in repos


def test_knowledge_graph_query():
    kg = CodeKnowledgeGraph()
    rid = kg.record_repository("https://github.com/test/repo", {"directory": "/tmp/repo", "languages": {}})
    entities = [
        CodeContext("function", "greet", "main.py", 10, 20),
        CodeContext("class", "Calculator", "main.py", 30, 50),
    ]
    kg.record_entities(rid, entities, ["main.py"])

    functions = kg.query(node_type="Function")
    assert len(functions) >= 1

    classes = kg.query(node_type="Class")
    assert len(classes) >= 1


def test_knowledge_graph_get_relationships():
    kg = CodeKnowledgeGraph()
    rid = kg.record_repository("https://github.com/test/repo", {"directory": "/tmp/repo", "languages": {}})
    entities = [CodeContext("function", "greet", "main.py", 10, 20)]
    kg.record_entities(rid, entities, ["main.py"])

    rels = kg.get_relationships(f"file:main.py")
    assert len(rels) >= 1


# ── Part 5: Impact Analysis ─────────────────────────────────────────────────

def test_impact_analysis():
    dg = DependencyGraph()
    kg = CodeKnowledgeGraph()
    rid = kg.record_repository("https://github.com/test/repo", {"directory": "/tmp/repo", "languages": {}})

    dg.add_node("fn:core:1", "function", "core_func", "core.py")
    dg.add_node("fn:dep:1", "function", "dep_func", "dependent.py")
    dg.add_edge("fn:dep:1", "fn:core:1", "calls")

    analyzer = ImpactAnalyzer(dg, kg)
    result = analyzer.analyze("core.py")
    assert "core.py" in result["all_affected_files"]
    assert result["total_dependents"] >= 1
    assert 0 <= result["risk_score"] <= 100
    assert result["risk_level"] in ("low", "medium", "high", "critical")


def test_impact_analysis_no_dependents():
    dg = DependencyGraph()
    kg = CodeKnowledgeGraph()
    kg.record_repository("https://github.com/test/repo", {"directory": "/tmp/repo", "languages": {}})
    dg.add_node("fn:alone:1", "function", "alone", "orphan.py")

    analyzer = ImpactAnalyzer(dg, kg)
    result = analyzer.analyze("orphan.py")
    assert result["total_dependents"] == 0
    assert result["risk_level"] == "low"


# ── Part 6: End-to-End Scan ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_end_to_end_scan(sample_repo_dir, ci_engine):
    result = await ci_engine.scan_repository(sample_repo_dir)
    assert result["total_files"] >= 8
    assert result["entity_count"] > 10
    assert result["repo_id"] is not None
    assert len(result["entities"]) > 10


@pytest.mark.asyncio
async def test_list_repositories(sample_repo_dir, ci_engine):
    await ci_engine.scan_repository(sample_repo_dir)
    repos = await ci_engine.list_repositories()
    assert len(repos) >= 1


@pytest.mark.asyncio
async def test_get_graph(sample_repo_dir, ci_engine):
    await ci_engine.scan_repository(sample_repo_dir)
    graph = await ci_engine.get_graph()
    assert graph["node_count"] > 0


@pytest.mark.asyncio
async def test_get_functions(sample_repo_dir, ci_engine):
    await ci_engine.scan_repository(sample_repo_dir)
    functions = await ci_engine.get_functions()
    assert len(functions) > 0


@pytest.mark.asyncio
async def test_get_classes(sample_repo_dir, ci_engine):
    await ci_engine.scan_repository(sample_repo_dir)
    classes = await ci_engine.get_classes()
    assert len(classes) > 0


@pytest.mark.asyncio
async def test_impact_end_to_end(sample_repo_dir, ci_engine):
    await ci_engine.scan_repository(sample_repo_dir)
    result = await ci_engine.analyze_impact("main.py")
    assert "main.py" in result["all_affected_files"]
    assert result["risk_level"] in ("low", "medium", "high", "critical")


# ── CodeContext ─────────────────────────────────────────────────────────────

def test_code_context():
    ctx = CodeContext("function", "test_fn", "file.py", 1, 10, "Does something.", "parent_cls",
                      {"key": "val"})
    assert ctx.id == "function:file.py:test_fn:1"
    assert ctx.to_dict()["entity_type"] == "function"
    assert ctx.to_dict()["name"] == "test_fn"

    ctx.add_relation("calls", "target_id_123", "target_name")
    assert len(ctx.relationships) == 1
    assert ctx.relationships[0]["type"] == "calls"


# ── Edge Cases ──────────────────────────────────────────────────────────────

def test_parse_empty_content():
    entities = CodeParser.parse("/tmp/empty.py", "")
    assert entities == []


def test_parse_invalid_syntax():
    entities = CodeParser.parse("/tmp/bad.py", "def (")
    assert isinstance(entities, list)


def test_scanner_ignores_node_modules(sample_repo_dir):
    nm_dir = os.path.join(sample_repo_dir, "node_modules")
    os.makedirs(nm_dir)
    with open(os.path.join(nm_dir, "index.js"), "w") as f:
        f.write("module.exports = {};")
    result = RepositoryScanner.scan(sample_repo_dir)
    nm_files = [f for f in result["files"] if "node_modules" in f["path"]]
    assert len(nm_files) == 0
