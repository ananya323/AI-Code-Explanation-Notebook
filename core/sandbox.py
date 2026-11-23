"""Run untrusted snippets in a subprocess with timeout, output cap and static safety checks."""
import ast
import os
import subprocess
import sys
import tempfile
import time

BLOCKED_IMPORTS = {"os", "subprocess", "socket", "shutil", "ctypes", "multiprocessing",
                   "requests", "urllib", "http", "ftplib", "smtplib", "pathlib"}
BLOCKED_CALLS = {"eval", "exec", "compile", "__import__", "open"}
OUTPUT_CAP = 4000


def check_safety(code: str) -> list:
    findings = []
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError) as e:
        return [f"Cannot parse: {e}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in BLOCKED_IMPORTS:
                    findings.append(f"Blocked import: {a.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in BLOCKED_IMPORTS:
                findings.append(f"Blocked import: {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_CALLS:
                findings.append(f"Blocked call: {node.func.id}()")
    return findings


def run_code(code: str, timeout: float = 5.0) -> dict:
    """Returns {status: passed|failed|timeout|blocked, stdout, stderr, runtime_ms}."""
    findings = check_safety(code)
    if findings:
        return {"status": "blocked", "stdout": "", "stderr": "; ".join(findings), "runtime_ms": 0.0}
    env = {k: v for k, v in os.environ.items() if k in ("SYSTEMROOT", "PATH")}
    env["PYTHONIOENCODING"] = "utf-8"
    with tempfile.TemporaryDirectory() as cwd:
        start = time.perf_counter()
        try:
            p = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True,
                               timeout=timeout, cwd=cwd, stdin=subprocess.DEVNULL, env=env)
            status = "passed" if p.returncode == 0 else "failed"
            out, err = p.stdout, p.stderr
        except subprocess.TimeoutExpired:
            status, out, err = "timeout", "", f"Timed out after {timeout:g}s"
        except OSError as e:
            status, out, err = "failed", "", f"Could not start interpreter: {e}"
    return {"status": status, "stdout": out[:OUTPUT_CAP], "stderr": err[-OUTPUT_CAP:],
            "runtime_ms": round((time.perf_counter() - start) * 1000, 1)}
