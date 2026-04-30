"""方法论阶段提示（PTES 风格），供界面与本地规划参考。"""

PHASES: list[dict[str, str | list[str]]] = [
    {
        "id": "pre_engagement",
        "title": "前期沟通与范围界定",
        "hints": [
            "确认已具备书面授权与交战规则（RoE）。",
            "在 config/scope.yaml 中锁定目标（主机、CIDR、URL 前缀等）。",
        ],
    },
    {
        "id": "recon_passive",
        "title": "被动 / 轻量侦察",
        "hints": [
            "whois、DNS（dig/host）、如有条件可看证书透明度等公开信息。",
            "在范围文件明确允许主动探测前，尽量控制流量与动作强度。",
        ],
    },
    {
        "id": "recon_active",
        "title": "主动测绘",
        "hints": [
            "nmap 常用端口与服务识别；在允许的 URL 上用 curl/HTTP 做探测。",
        ],
    },
    {
        "id": "modeling",
        "title": "攻击面建模",
        "hints": [
            "梳理入口：认证、上传、API、管理路径等。",
            "在深入测试前标出信任边界与数据流。",
        ],
    },
    {
        "id": "discovery",
        "title": "漏洞发现",
        "hints": [
            "按应用画像做结构化测试；仅当范围允许时，再在 scope 中启用 internal 等内网相关 profile。",
        ],
    },
    {
        "id": "validation",
        "title": "受控验证",
        "hints": [
            "用破坏性最小的 PoC 证明影响；证据与日志保存到 output/ 目录。",
        ],
    },
    {
        "id": "reporting",
        "title": "报告与复测",
        "hints": [
            "输出带复现步骤的 findings；复测可用 xjf exec 对比前后差异。",
        ],
    },
]
