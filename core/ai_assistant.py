"""AI assistant. Default: deterministic local mock. Optional: Claude API with mock fallback."""
import ast
import json
import os
import re

API_MODEL = "claude-sonnet-5-5"

TIPS = {
    "Performance": "Prefer built-ins and comprehensions; avoid repeated work inside loops.",
    "Readability": "Small functions with clear names and docstrings are easier to review.",
    "Bug Fix": "Add guard clauses for empty or invalid input before computing.",
    "Style": "Follow PEP 8 and PEP 20: compare with None using `is`, return booleans directly.",
    "Safety": "Never use bare `except:`; catch specific exceptions and avoid eval/exec.",
}


class _Improver(ast.NodeTransformer):
    """Small set of safe, semantics-preserving rewrites."""

    def __init__(self):
        self.changes = []

    def visit_Compare(self, node):
        self.generic_visit(node)
        ops = []
        for op, comp in zip(node.ops, node.comparators):
            if isinstance(comp, ast.Constant) and comp.value is None and isinstance(op, (ast.Eq, ast.NotEq)):
                ops.append(ast.Is() if isinstance(op, ast.Eq) else ast.IsNot())
                self.changes.append("Compared with None using `is` / `is not` instead of `==` / `!=`.")
            else:
                ops.append(op)
        node.ops = ops
        return node

    def visit_ExceptHandler(self, node):
        self.generic_visit(node)
        if node.type is None:
            node.type = ast.Name(id="Exception", ctx=ast.Load())
            self.changes.append("Replaced bare `except:` with `except Exception:`.")
        return node

    def visit_If(self, node):
        self.generic_visit(node)
        b, o = node.body, node.orelse
        if (isinstance(node.test, ast.Compare) and len(b) == 1 and len(o) == 1
                and isinstance(b[0], ast.Return) and isinstance(o[0], ast.Return)
                and isinstance(b[0].value, ast.Constant) and isinstance(o[0].value, ast.Constant)
                and isinstance(b[0].value.value, bool) and isinstance(o[0].value.value, bool)
                and b[0].value.value != o[0].value.value):
            test = node.test if b[0].value.value else ast.UnaryOp(op=ast.Not(), operand=node.test)
            self.changes.append("Returned the boolean expression directly instead of if/else True/False.")
            return ast.copy_location(ast.Return(value=test), node)
        return node

    @staticmethod
    def _as_comp(name, loop):
        if not isinstance(loop.target, (ast.Name, ast.Tuple)):
            return None
        body, conds = loop.body, []
        if len(body) == 1 and isinstance(body[0], ast.If) and not body[0].orelse:
            conds, body = [body[0].test], body[0].body
        if len(body) != 1:
            return None
        st = body[0]
        if (isinstance(st, ast.Expr) and isinstance(st.value, ast.Call)
                and isinstance(st.value.func, ast.Attribute) and st.value.func.attr == "append"
                and isinstance(st.value.func.value, ast.Name) and st.value.func.value.id == name
                and len(st.value.args) == 1 and not st.value.keywords):
            return ast.ListComp(elt=st.value.args[0], generators=[
                ast.comprehension(target=loop.target, iter=loop.iter, ifs=conds, is_async=0)])
        return None

    def _rewrite(self, body):
        out, i = [], 0
        while i < len(body):
            s = body[i]
            nxt = body[i + 1] if i + 1 < len(body) else None
            if (isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)
                    and isinstance(s.value, ast.List) and not s.value.elts
                    and isinstance(nxt, ast.For) and not nxt.orelse):
                comp = self._as_comp(s.targets[0].id, nxt)
                if comp is not None:
                    out.append(ast.copy_location(ast.Assign(targets=s.targets, value=comp), s))
                    self.changes.append("Replaced an append-in-a-loop with a list comprehension.")
                    i += 2
                    continue
            out.append(s)
            i += 1
        return out

    def visit_Module(self, node):
        self.generic_visit(node)
        node.body = self._rewrite(node.body)
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.body = self._rewrite(node.body)
        if not ast.get_docstring(node):
            doc = node.name.replace("_", " ").strip().capitalize() + "."
            node.body.insert(0, ast.Expr(value=ast.Constant(value=doc)))
            self.changes.append(f"Added a docstring to `{node.name}()`.")
        return node


def explain_code(code: str) -> str:
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError) as e:
        return f"The code could not be parsed: {e}"
    nodes = list(ast.walk(tree))
    funcs = [n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    parts = []
    if funcs:
        sigs = ", ".join(f"`{f.name}({', '.join(a.arg for a in f.args.args)})`" for f in funcs)
        parts.append(f"Defines {len(funcs)} function(s): {sigs}.")
    classes = [n.name for n in nodes if isinstance(n, ast.ClassDef)]
    if classes:
        parts.append("Defines class(es): " + ", ".join(f"`{c}`" for c in classes) + ".")
    loops = [n for n in nodes if isinstance(n, (ast.For, ast.While))]
    if loops:
        nested = any(isinstance(c, (ast.For, ast.While)) for n in loops for c in ast.walk(n) if c is not n)
        parts.append(f"Uses {len(loops)} loop(s)" + (", including nested iteration (roughly quadratic work)." if nested else "."))
    conds = sum(isinstance(n, (ast.If, ast.IfExp)) for n in nodes)
    if conds:
        parts.append(f"Branches in {conds} place(s).")
    if any(isinstance(n, ast.Try) for n in nodes):
        parts.append("Handles errors with try/except.")
    if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print" for n in nodes):
        parts.append("Prints results to the console.")
    if any(isinstance(n, ast.Return) for n in nodes):
        parts.append("Returns a computed value to its caller.")
    return " ".join(parts) or "A short script with no functions or control flow."


def mock_suggest(code: str, category: str) -> dict:
    explanation = explain_code(code)
    try:
        imp = _Improver()
        tree = imp.visit(ast.parse(code))
        ast.fix_missing_locations(tree)
        improved = ast.unparse(tree)
        changes = list(dict.fromkeys(imp.changes))
    except Exception:  # never let the mock crash the UI
        improved, changes = code, []
    if changes:
        rationale = "\n".join(f"- {c}" for c in changes)
        rationale += "\n- Note: the rewrite goes through the AST, so comments are not preserved."
    else:
        improved = code
        rationale = "- No safe automatic improvement found; the code already follows the common patterns."
    rationale += f"\n\nTip ({category}): {TIPS.get(category, '')}"
    return {"explanation": explanation, "improved_code": improved, "rationale": rationale, "source": "mock"}


def _api_suggest(code: str, category: str, api_key: str) -> dict:
    import anthropic  # ImportError -> caller falls back to the mock

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("no API key")
    client = anthropic.Anthropic(api_key=key, timeout=20.0)
    msg = client.messages.create(
        model=API_MODEL, max_tokens=1500,
        system="You review small Python programs. Reply with ONLY a JSON object with string keys "
               "'explanation', 'improved_code', 'rationale'. No markdown fences.",
        messages=[{"role": "user", "content": f"Category: {category}\n\n{code}"}])
    text = re.sub(r"^```(?:json)?|```$", "", msg.content[0].text.strip(), flags=re.M).strip()
    data = json.loads(text)
    for k in ("explanation", "improved_code", "rationale"):
        if not isinstance(data.get(k), str):
            raise ValueError(f"missing {k}")
    ast.parse(data["improved_code"])
    data["source"] = "claude-api"
    return data


def suggest(code: str, category: str, use_api: bool = False, api_key: str = "") -> dict:
    """Mock by default; with use_api, tries Claude and falls back to the mock on any failure."""
    if use_api:
        try:
            return _api_suggest(code, category, api_key)
        except Exception as exc:  # network, import, key, parse...
            res = mock_suggest(code, category)
            res["source"] = f"mock (API unavailable: {type(exc).__name__})"
            return res
    return mock_suggest(code, category)
