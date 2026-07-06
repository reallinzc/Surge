# Surge
## Modules

### po0 防火墙自动加白

多 token（英文逗号分割，一台机器一个 `pgnfw_` token），network-changed 事件 + 每 2 分钟 cron 自动把当前出口 IP 加入 po0 防火墙白名单，附手动刷新面板。

特性：

- **省坑位**：GET 先查，当前出口已在白名单则不 POST（白名单上限 5 个，API 无删除能力）。
- **蜂窝优化**：蜂窝（CGNAT）下自动加白 24h 内最多消耗 2 个坑位，超限只通知；面板手动刷新不受限，要用时点一下必定加白。
- **面板**：显示白名单 IP 与坑位占用（不显示 token），蜂窝加白的 IP 标 📶，当前出口标 ←。
- **安静**：KV 记录状态，仅在失败、限频或消耗新坑位时通知。

图文教程：<https://rfcjpco.rlyio.com/>

**一键安装（Surge iOS / Mac）：**

[surge:///install-module?url=…](surge:///install-module?url=https%3A%2F%2Fraw.githubusercontent.com%2Freallinzc%2FSurge%2Fmain%2Fpo0-firewall-whitelist.sgmodule)

链接点不动时手动复制：

```
surge:///install-module?url=https%3A%2F%2Fraw.githubusercontent.com%2Freallinzc%2FSurge%2Fmain%2Fpo0-firewall-whitelist.sgmodule
```

安装后在模块参数 `tokens` 填 `pgnfw_xxx,pgnfw_yyy`。
