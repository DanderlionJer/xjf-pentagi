# -*- coding: utf-8 -*-
"""Patch static/index.html"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
P = ROOT / "src" / "xjf_pentagi" / "static" / "index.html"


def main() -> None:
    h = P.read_text(encoding="utf-8")

    h2, n = re.subn(
        r'<label>[^<]*</label>\s*'
        r'<textarea id="targets" class="targets-input" placeholder="[^"]*"></textarea>',
        "<label>"
        + "\u6d4b\u8bd5\u76ee\u6807\uff08\u4f8b\uff1awww.baidu.com \u6216\u5b8c\u6574 URL\uff09"
        + "</label>\n"
        + '          <input type="text" id="targetUrl" placeholder="www.baidu.com" autocomplete="off" '
        + 'style="width:100%;padding:0.55rem 0.65rem;border-radius:8px;border:1px solid var(--border);'
        + 'background:var(--bg);color:var(--text);font-family:var(--font);font-size:0.95rem" />',
        h,
        count=1,
        flags=re.DOTALL,
    )
    if n != 1:
        raise SystemExit("targets textarea replace failed")
    h = h2

    ins = (
        '        <div class="row" style="margin-top:0.5rem">\n'
        '          <button type="button" class="btn primary" id="btnQuickStart" '
        'style="font-size:1rem;padding:0.55rem 1.1rem">'
        + "\u5f00\u59cb\u6d4b\u8bd5"
        + "</button>\n"
        + '          <span style="color:var(--muted);font-size:0.85rem;margin-left:0.5rem">'
        + "\u4fa6\u5bdf + \u53ef\u9009 LLM"
        + "</span>\n"
        "        </div>\n"
    )
    mark = 'id="btnAutonomous"'
    i = h.find(mark)
    if i < 0:
        raise SystemExit("btnAutonomous not found")
    h = h[:i] + ins + h[i:]

    h, n = re.subn(
        r'(<label><input type="checkbox" id="useLlm" checked />)\s*[^<]*(</label>)',
        r"\1 " + "\u542f\u7528 LLM \u89c4\u5212\u9636\u6bb5" + r" \2",
        h,
        count=1,
    )
    if n != 1:
        raise SystemExit("useLlm label replace failed")

    llm = (
        "\n      <div class=\"panel\" style=\"margin-top:0.35rem;padding:0.65rem 0.75rem\">\n"
        '        <h3 style="margin:0 0 0.5rem;font-size:0.95rem">'
        + "\u5916\u90e8 LLM\uff08OpenAI \u517c\u5bb9 /v1/chat/completions\uff09"
        + "</h3>\n"
        + '        <div class="row">\n'
        + '          <div style="flex:1;min-width:120px">\n'
        + '            <label style="font-size:0.8rem;color:var(--muted)">API Key</label>\n'
        + '            <input type="password" id="llmApiKey" placeholder="'
        + "\u53ef\u586b sk-... \u6216\u7559\u7a7a\u7528\u73af\u5883\u53d8\u91cf"
        + '" autocomplete="off" style="width:100%" />\n'
        + "          </div>\n"
        + "        </div>\n"
        + '        <div class="row" style="margin-top:0.35rem">\n'
        + '          <div style="flex:1;min-width:120px">\n'
        + '            <label style="font-size:0.8rem;color:var(--muted)">Base URL</label>\n'
        + '            <input type="text" id="llmBaseUrl" placeholder="https://api.openai.com/v1" '
        + 'autocomplete="off" style="width:100%" />\n'
        + "          </div>\n"
        + '          <div style="flex:1;min-width:100px">\n'
        + '            <label style="font-size:0.8rem;color:var(--muted)">'
        + "\u6a21\u578b"
        + '</label>\n'
        + '            <input type="text" id="llmModel" placeholder="gpt-4o-mini" '
        + 'autocomplete="off" style="width:100%" />\n'
        + "          </div>\n"
        + "        </div>\n"
        + "      </div>\n"
    )
    anchor = '</div>\n      <div class="row">\n        <div style="flex:1">\n          <label>UI'
    if anchor not in h:
        raise SystemExit("LLM insert anchor not found")
    h = h.replace(anchor, llm + anchor, 1)

    m = re.search(r"function currentTargets\(\) \{.*?\n    \}", h, re.DOTALL)
    if not m:
        raise SystemExit("currentTargets not found")
    new_fn = (
        "function normalizeTarget(raw) {\n"
        '      let s = (raw || "").trim();\n'
        '      if (!s) throw new Error("'
        + "\u8bf7\u586b\u5199\u6d4b\u8bd5\u76ee\u6807"
        + '");\n'
        '      if (!s.includes("://")) {\n'
        "        if (/^[A-Za-z0-9._\\-]+$/.test(s)) {\n"
        '          s = "https://" + s.replace(/\\/$/, "") + "/";\n'
        "        }\n"
        "      }\n"
        "      return s;\n"
        "    }\n\n"
        "    function currentTargets() {\n"
        '      return [normalizeTarget($("targetUrl").value)];\n'
        "    }\n\n"
        "    function llmPayload() {\n"
        "      const o = {};\n"
        '      const k = $("llmApiKey").value.trim();\n'
        '      const u = $("llmBaseUrl").value.trim();\n'
        '      const m = $("llmModel").value.trim();\n'
        "      if (k) o.llm_api_key = k;\n"
        "      if (u) o.llm_base_url = u;\n"
        "      if (m) o.llm_model = m;\n"
        "      return o;\n"
        "    }"
    )
    h = h[: m.start()] + new_fn + h[m.end() :]

    h3, n = re.subn(
        r'\$\("btnAutonomous"\)\.onclick = async \(\) => \{.*?\n    \};',
        "async function runAutonomous() {\n"
        "      try {\n"
        '        log("'
        + "\u5f00\u59cb\u6d4b\u8bd5\u2026"
        + '");\n'
        "        const body = {\n"
        "          targets: currentTargets(),\n"
        '          use_llm: $("useLlm").checked,\n'
        '          dry_run: $("dryRun").checked,\n'
        "          ...llmPayload(),\n"
        "        };\n"
        '        const res = await apiPost("/api/autonomous", body);\n'
        "        log(res);\n"
        "      } catch (e) {\n"
        '        log("'
        + "\u9519\u8bef"
        + ': " + e.message);\n'
        "      }\n"
        "    }\n"
        '    $("btnAutonomous").onclick = () => runAutonomous();\n'
        '    $("btnQuickStart").onclick = () => runAutonomous();',
        h,
        count=1,
        flags=re.DOTALL,
    )
    if n != 1:
        raise SystemExit("btnAutonomous block replace failed")
    h = h3

    old_boot = (
        "    loadScope();\n"
        "    loadScopeYaml();\n"
        "    loadModules();\n"
        "    loadPipelines();"
    )
    new_boot = (
        '    document.querySelector(\'#tabs button[data-tab="auto"]\').click();\n'
        "    loadScope();\n"
        "    loadScopeYaml();\n"
        "    loadModules();\n"
        "    loadPipelines();"
    )
    if old_boot not in h:
        raise SystemExit("boot sequence not found")
    h = h.replace(old_boot, new_boot, 1)

    h, n = re.subn(r"    textarea\.targets-input \{[^}]+\}\n", "", h, count=1)
    if n != 1:
        raise SystemExit("CSS targets-input remove failed")

    P.write_text(h, encoding="utf-8", newline="\n")
    print("patched", P)


if __name__ == "__main__":
    main()
