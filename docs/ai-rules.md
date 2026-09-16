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
RULE-SET,https://raw.githubusercontent.com/reallinzc/Surge/main/AI-IP.list,AI,no-resolve
```

策略组 `AI` 由使用者在自己的配置里定义；规则文件不包含节点、账号、密钥或策略名。
三份文件分开是为了保持域名规则、Apple 例外与 IP 兜底的先后关系。

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
