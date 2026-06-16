#!/usr/bin/env python3
"""
mcpSway MCP Server — 通过 stdio 协议将 mcpSway 技能库暴露为 MCP 工具。

协议：MCP JSON-RPC over stdio（符合 MCP 2025-03-26 规范）
生命周期：
  1. client → initialize → server → InitializeResult
  2. client → initialized (notification, 无需回复)
  3. client → tools/list → server → tools[]
  4. client → tools/call → server → content[]

部署后注册到 LiteLLM config.yaml 的 mcp_servers 段。
"""

import json
import sys
from pathlib import Path

# SWAY_DIR = mcpSway 子模块所在路径（脚本在 mcps/ 根目录，mcpSway 在同级子目录）
HERE = Path(__file__).resolve().parent
SWAY_DIR = HERE / "mcpSway"

MCP_PROTOCOL_VERSION = "2025-03-26"

SERVER_INFO = {
    "name": "mcpSway",
    "version": "1.0.0",
}

# 服务器能力声明：仅支持 tools（不提供 resources / prompts）
CAPABILITIES = {
    "tools": {},
}

def load_skills(base: Path) -> list[dict]:
    """扫描 skills/ 子目录，返回技能元信息列表"""
    skills_dir = base / "skills"
    if not skills_dir.is_dir():
        return []
    entries = []
    for sub in sorted(skills_dir.iterdir()):
        skill_md = sub / "SKILL.md"
        if not skill_md.is_file():
            continue
        # 读取 frontmatter 粗略提取描述
        text = skill_md.read_text(encoding="utf-8")
        desc = ""
        tags = []
        for line in text.splitlines():
            if line.startswith("description:"):
                desc = line.split(":", 1)[1].strip().strip('"').strip("'")
            if line.startswith("tags:"):
                raw_tags = line.split(":", 1)[1].strip()
                if raw_tags.startswith("["):
                    raw_tags = raw_tags.strip("[]")
                tags = [t.strip().strip('"').strip("'") for t in raw_tags.split(",") if t.strip()]
            if line.startswith("---") and desc:
                break
        entries.append({
            "name": sub.name,
            "description": desc or f"Sway 技能: {sub.name}",
            "path": str(skill_md),
            "tags": tags,
        })
    return entries


def handle_list_tools() -> dict:
    skills = load_skills(SWAY_DIR)
    tools = []
    for s in skills:
        tools.append({
            "name": s["name"],
            "description": s["description"],
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        })
    return {"tools": tools}


def handle_call_tool(name: str, arguments: dict) -> dict:
    skills = load_skills(SWAY_DIR)
    matched = None
    for s in skills:
        if s["name"] == name:
            matched = s
            break
    if not matched:
        return {"content": [{"type": "text", "text": f"Skill '{name}' not found"}], "isError": True}

    path = Path(matched["path"])
    text = path.read_text(encoding="utf-8")

    # 如果传了 ref 参数，返回参考/模板文件
    ref = (arguments or {}).get("ref", "")
    if ref:
        ref_base = path.parent / "references" / ref
        tmpl_base = path.parent / "templates" / ref
        if ref_base.is_file():
            text = ref_base.read_text(encoding="utf-8")
        elif tmpl_base.is_file():
            text = tmpl_base.read_text(encoding="utf-8")
        else:
            return {"content": [{"type": "text", "text": f"Reference '{ref}' not found"}], "isError": True}

        text = f"# {name}/{ref}\n\n{text}"

    # 列出可用的参考/模板文件
    if (arguments or {}).get("list_refs"):
        refs_dir = path.parent / "references"
        tmpls_dir = path.parent / "templates"
        refs = sorted(f.name for f in refs_dir.iterdir()) if refs_dir.is_dir() else []
        tmpls = sorted(f.name for f in tmpls_dir.iterdir()) if tmpls_dir.is_dir() else []
        text = f"# {name}\n\n{text}\n\n## References\n\n"
        text += "\n".join(f"- {r}" for r in refs) if refs else "(none)"
        text += "\n\n## Templates\n\n"
        text += "\n".join(f"- {t}" for t in tmpls) if tmpls else "(none)"
        text += "\n\nPass `\"ref\": \"filename.md\"` to read a specific reference or template."

    return {"content": [{"type": "text", "text": text}]}


def main():
    """MCP stdio 协议主循环：读 stdin JSON-RPC，写 stdout JSON-RPC"""
    initialized = False
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method", "")
        req_id = req.get("id")

        # MCP 初始化握手
        if method == "initialize":
            params = req.get("params", {})
            client_version = params.get("protocolVersion", MCP_PROTOCOL_VERSION)
            resp = {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "protocolVersion": client_version,
                    "capabilities": CAPABILITIES,
                    "serverInfo": SERVER_INFO,
                },
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
            continue

        # initialized notification — 无需回复
        if method == "notifications/initialized":
            initialized = True
            continue

        params = req.get("params", {})

        if method == "tools/list":
            result = handle_list_tools()
        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = handle_call_tool(name, arguments)
        else:
            resp = {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
            continue

        resp = {"jsonrpc": "2.0", "id": req_id, "result": result}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
