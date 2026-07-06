# Surge
## Modules

### po0 防火墙自动加白

多 token（英文逗号分割，一台机器一个 `pgnfw_` token），network-changed + 每 5 分钟 cron 自动把当前出口 IP 加入 po0 防火墙白名单，附手动刷新面板。

**一键安装（Surge iOS / Mac）：**

[surge:///install-module?url=…](surge:///install-module?url=https%3A%2F%2Fraw.githubusercontent.com%2Freallinzc%2FSurge%2Fmain%2Fpo0-firewall-whitelist.sgmodule)

链接点不动时手动复制：

```
surge:///install-module?url=https%3A%2F%2Fraw.githubusercontent.com%2Freallinzc%2FSurge%2Fmain%2Fpo0-firewall-whitelist.sgmodule
```

安装后在模块参数 `tokens` 填 `pgnfw_xxx,pgnfw_yyy`。
