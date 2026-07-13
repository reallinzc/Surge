# Surge

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
