# AI 规则维护

本仓库维护经过核对的 AI 分流范围。`AI.list` 是直接编辑的唯一域名规则源，
客户端只引用本仓库，不在运行时拼接第三方 AI 列表。新增、删除或扩大匹配范围
均通过 Git 提交审阅；不会自动把第三方仓库的新域名或整个云服务 ASN 带入配置。

## 引用

```ini
# 保留既有 Siri / Apple Intelligence 的较前位置
RULE-SET,https://raw.githubusercontent.com/reallinzc/Surge/main/AppleIntelligence.list,AI,extended-matching

# 放在 Google、Microsoft、通用 CDN / 海外规则前
RULE-SET,https://raw.githubusercontent.com/reallinzc/Surge/main/AI.list,AI,extended-matching

# 放在 IP 分流段，保留 no-resolve
RULE-SET,https://raw.githubusercontent.com/reallinzc/Surge/main/Claude-IP.list,AI,no-resolve
RULE-SET,https://raw.githubusercontent.com/reallinzc/Surge/main/AI-IP.list,AI,no-resolve
```

策略组 `AI` 由使用者在自己的配置里定义；规则文件不包含节点、账号、密钥或策略名。
域名规则、Apple 例外、Claude IP 与语音 IP 分开维护，保持各自的先后关系。
`AI.list` 只保存域名/URL 条件，不嵌入进程或 IP 条件。

Claude Code 的 Mac 进程兜底留在客户端主配置，放在明确的本机、内网及直连例外之后，
Google、通用 CDN 和海外兜底之前；按实际二进制名匹配，避免覆盖通用 Node/Bun 进程：

```ini
PROCESS-NAME,/Applications/Claude.app/,AI
PROCESS-NAME,claude,AI
PROCESS-NAME,claude.exe,AI
```

2026-10-14 补入官方开发者站 `claude.dev`，将 Claude Priority 的重复域名合并。
保留已有的 Sentry、Datadog、Sift、Intercom 等共享服务例外；这些是历史上的全局 AI 分流选择，
不代表它们只由 Claude 使用。`statsig.com` 未全局加入；CLI 自身的请求可由进程规则兜底。

`Claude-IP.list` 使用 [Anthropic 官方 API 入站范围](https://platform.claude.com/docs/en/api/ip-addresses)
`160.79.104.0/23` 和 `2607:6bc0::/48`，并保留注册局确认归 Anthropic 所有的
[AS399358](https://rdap.arin.net/registry/autnum/399358)。ASN 条件覆盖范围随该网络变化，
包含其当前公告的另一 IPv6 前缀 `2607:6bc0:11::/48`；它不宣称该前缀是官方 API 入站范围。
移除非 Anthropic 的 AS55960、AS14201。官方 `/21` 是 Anthropic 工具调用出站范围，
不作为客户端 API 入站 CIDR；不用整个云厂商 ASN 兜底。

## 来源与范围（2026-09-16）

- [Sukka AI](https://github.com/SukkaW/Surge/blob/master/Source/non_ip/ai.conf)：
  通用 AI 基线；本次快照来自 2026-09-07 更新的发布文件。移除无业务用途的标识域名，
  合并被补充后缀规则完全覆盖的精确域名。保留原有 `openai` 关键字和 Gemini 重定向 URL 规则。
- [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community/tree/master/data)：
  `openai`、`anthropic`、`google-deepmind`、`github-copilot`、`cursor`、`windsurf`、
  `perplexity`、`poe`、`xai` 和 `category-ai-!cn` 的服务域名补充。
- [blackmatrix7 Copilot](https://github.com/blackmatrix7/ios_rule_script/blob/master/rule/Surge/Copilot/Copilot.list)：
  Microsoft Copilot 专属接口交叉核对，未采用共享 SaaS 后缀或云服务 ASN。
- [Meta AI 官方](https://ai.meta.com/meta-ai/assistant/)：`meta.ai` 已覆盖主站及子域；
  实际未登录网页的登录按钮进入 `auth.meta.com`。补充 `ai.meta.com`、`aidemos.meta.com`；
  `imagine.meta.com` 同时参考
  [QuixoticHeart AI](https://github.com/QuixoticHeart/rule-set/blob/ruleset/surge/ai.list)。
- [OpenAI 官方语音 IP](https://openai.com/chatgpt-voice.json)：保存为
  `sources/chatgpt-voice.json`，生成 `AI-IP.list`。初始版本为 23 个 IPv4 /32。
- Apple Intelligence 保留既有 Siri / Private Cloud Compute 的六条范围；
  [Apple 企业网络要求](https://support.apple.com/101555) 是服务用途参考。
  不引入同时影响地图等服务的 `gspe1-ssl.ls.apple.com`。

Meta AI 独立站的登录入口与主站应使用同一出口。Facebook、Instagram、WhatsApp、
Messenger 与共享 CDN 仍由各自规则处理；本列表不声称覆盖它们内部所有 AI 请求。
Gemini 的 `URL-REGEX` 在 HTTPS 下需要已有的对应 MITM 条件，规则集本身不会启用 MITM。

上游条目保留各自来源及许可，不重新许可上游内容。随仓库保留上游许可证全文：
[Sukka AGPL 3.0](../LICENSES/Sukka-AGPL-3.0.txt)、
[v2fly MIT / V2Ray copyright](../LICENSES/v2fly-MIT.txt)、
[blackmatrix7 GPL 2.0](../LICENSES/blackmatrix7-GPL-2.0.txt)。
上述整理和范围调整由本仓库完成，原始可编辑规则随文件公开。

## 更新与验证

```sh
# 离线校验语法、重复项、生成一致性及覆盖/排除范围
python3 scripts/ai_rules.py

# 获取官方语音 IP，生成供审阅的变更；不会自动提交或推送
python3 scripts/ai_rules.py --refresh-voice
git diff -- AI-IP.list sources/chatgpt-voice.json
```

普通域名修改直接编辑 `AI.list`，并按需要更新 `tests/ai-routing.json`。
语音更新若删除旧测试地址，校验会提示范围变化；核对官方变更后再调整对应测试。
GitHub Actions 在相关提交与 PR 上运行离线检查，不会自动改写规则。
上线后还需使用 Surge `external-resource list`、`profile check`、`rule match` 和
实际请求记录验证客户端已获取文件及命中预期策略。

NetOps 工作区的 `rules/AI.list`、`rules/Claude-IP.list` 与本仓库发布文件同步。
编辑前先将发布仓库快进到远端 main；同步两处后再校验、提交和推送，避免旧检出通过校验却覆盖新发布内容。
