# Surge

## AI 规则

自行维护的 AI 域名、Claude IP、ChatGPT 语音 IP 和 Apple Intelligence 规则。
来源、更新方法与 Surge 引用示例见 [AI 规则维护](docs/ai-rules.md)。

- [AI.list](AI.list)：Meta AI、OpenAI、Claude、Gemini、Copilot、Cursor 等
- [AI-IP.list](AI-IP.list)：OpenAI 官方 ChatGPT 实时语音 IP
- [Claude-IP.list](Claude-IP.list)：Claude API 入站 IP 与已核验的 Anthropic ASN
- [AppleIntelligence.list](AppleIntelligence.list)：Siri / Private Cloud Compute

## Google 规则

[Google.list](Google.list) 由 `scripts/google_rules.py` 从 [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community)
的 `data/google` 生成（展开 include，`full:` → `DOMAIN`，域名 → `DOMAIN-SUFFIX`；`regexp:` 无 Surge 对应写法，跳过并在文件头列出）。
另外人工补充：v2fly 缺失、但实测解析到 AS15169 的 Google 域名，AS15169 的 IP 段，以及 Google Drive 的 UA。

- 文件头记录上游提交；`python3 scripts/google_rules.py` 会在该提交上重新生成并逐字节比对，同时校验。
- 校验项：不带点的后缀只允许 Google 品牌 TLD（`.google`、`.youtube` 等，不含 `.app`/`.dev` 这类公开注册的 TLD），并且必须通过 `tests/google-routing.json` 中的必中/必不中用例。
- GitHub Actions 每天跑 `--update`，规则有变化才提交。

```ini
RULE-SET,https://raw.githubusercontent.com/reallinzc/Surge/main/Google.list,Google,extended-matching,no-resolve
```

## Apple TV 规则

[AppleTV.list](AppleTV.list)：补充 `ruleset.skk.moe` `non_ip/stream.conf` 未覆盖的 `tv.apple.com` 与 Apple TV App UA。
macOS 进程规则 `PROCESS-NAME,TV` 留在客户端配置。

```ini
RULE-SET,https://raw.githubusercontent.com/reallinzc/Surge/main/AppleTV.list,Media,extended-matching
```

## Telegram DC regional rules

Surge rule sets that split Telegram's official address space by the lowest
measured end-to-end path from the local Surge front end:

- `TelegramDC-Americas.list`: DC1/DC3 via the Japan T1 Smart group
- `TelegramDC-Europe.list`: DC2/DC4/DC203 via the Hong Kong T1 Smart group
- `TelegramDC-Singapore.list`: DC5 via the Singapore V.PS node

The lists partition every IPv4 and IPv6 network published in Telegram's
official CIDR feed. `scripts/update_telegram_dc_rules.py --check` also checks
the current MTProxy DC endpoints against those partitions. A scheduled GitHub
Actions workflow runs the check daily.

## Modules

### po0 防火墙自动加白

已迁移到独立仓库：<https://github.com/reallinzc/po0fw>（教程 <https://po0fw.rlyio.com/>）。
