# AWBotNest V2 原生迁移审计

审计日期：2026-09-09。范围仅为 `plugins_v2/`。复杂度和优先级用于安排原生 V2 迁移，不代表插件质量。

| Plugin | Category | Complexity | _compat | _legacy | Interactive | Storage | External Service | Frontend | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ai | External | 高 | 是 | 是 | 是 | 是 | AI | Vue | P4 |
| auto_avatar | Automation | 低 | 否 | 否 | 否 | 是 | Telegram | Schema | 已完成 |
| auto_changename | Automation | 低 | 否 | 否 | 否 | 否 | Telegram | Schema | 已完成 |
| auto_lottery | Interactive | 中 | 是 | 是 | 是 | 是 | Telegram | Vue | P2 |
| auto_subscribe | External | 高 | 是 | 是 | 是 | 是 | HTTP/AI/Browser | Vue | P4 |
| awblackjack | External/Interactive | 极高 | 是 | 是 | 是 | 是 | MQTT/HTTP | 否 | P5 |
| awembypush | Automation | 中 | 是 | 是 | 否 | 是 | Telegram | Vue | P3 |
| awpulse | External | 高 | 是 | 是 | 是 | 否 | HTTP/AI/Browser | Vue | P4 |
| awrelay | Automation | 高 | 是 | 是 | 是 | 是 | Telegram Forum | Vue | P3 |
| bomb_game | Interactive | 高 | 否 | 否 | 是 | 是 | Telegram | Vue | 已完成 |
| common_lottery | Interactive | 中 | 否 | 否 | 否 | 是 | Telegram | 否 | 已完成 |
| config_migration | Migration/Utility | 中 | 否 | 否 | 否 | 否 | HTTP | Vue | 已原生 |
| custom_auto_reply | Automation | 低 | 否 | 否 | 是 | 否 | Telegram | Schema | 已完成 |
| custom_plugin | Utility | 中 | 否 | 否 | 否 | 是 | Telegram | Vue | 已完成 |
| digital_pet | Interactive | 中 | 是 | 是 | 是 | 是 | Telegram | 否 | P2 |
| dyp_redpacket | Interactive | 中 | 否 | 否 | 否 | 是 | Telegram | 否 | 已完成 |
| emby_toolbox | External | 高 | 是 | 是 | 是 | 是 | Emby | Vue | P4 |
| getmsg | Utility | 低 | 否 | 否 | 是 | 否 | Telegram | 否 | 已完成 |
| gptgod_checkin | External | 中 | 否 | 否 | 否 | 是 | Browser | 否 | 已完成 |
| hdhive_lottery | Interactive | 中 | 否 | 否 | 是 | 否 | Telegram | Schema | 已完成 |
| hdhive_quiz | Interactive | 高 | 是 | 是 | 是 | 是 | AI/HTTP | Vue | P2 |
| hdsky_redpacket | Interactive | 中 | 否 | 否 | 否 | 是 | Telegram | 否 | 已完成 |
| hhan_lottery | Interactive/External | 极高 | 是 | 是 | 是 | 是 | HTTP | Vue | P4 |
| human_lottery | Interactive | 高 | 是 | 是 | 是 | 是 | Telegram | Vue | P2 |
| id | Utility | 低 | 否 | 否 | 否 | 否 | Telegram | Schema | 已完成 |
| jupai | Interactive | 低 | 否 | 否 | 是 | 否 | HTTP/Telegram | 否 | 已完成 |
| keyword_auto_reply | Automation | 中 | 是 | 是 | 是 | 是 | Telegram | Vue | P3 |
| movie_monitor_115 | External | 高 | 否 | 否 | 否 | 是 | HTTP | Vue | 已完成 |
| msg_forward | Automation | 低 | 否 | 否 | 否 | 否 | Telegram | Schema | 已完成 |
| probe | Utility | 低 | 否 | 否 | 否 | 是 | Telegram | 否 | 已完成 |
| pt_multi_checkin | External | 极高 | 是 | 是 | 是 | 是 | HTTP/AI/Browser | Vue | P5 |
| pterclub_bonus | External | 高 | 否 | 否 | 否 | 是 | HTTP | 否 | 已完成 |
| quiz_game | Interactive | 高 | 是 | 是 | 是 | 是 | HTTP/AI | Vue | P2 |
| red_packet_grab | Interactive | 高 | 是 | 是 | 是 | 否 | Telegram/OCR | Vue | P2 |
| red_packet_send | Interactive | 高 | 是 | 是 | 是 | 是 | Telegram | Vue | P2 |
| self_delete | Utility | 低 | 否 | 否 | 否 | 否 | Telegram | Schema | 已完成 |
| trans115search | Automation | 中 | 否 | 否 | 是 | 否 | Telegram | Schema | 已完成 |
| transfer | Automation | 高 | 是 | 是 | 是 | 是 | Telegram | Vue | P3 |
| u2_dmhy | External | 高 | 否 | 否 | 否 | 是 | HTTP | 否 | 已完成 |
| webhook_bridge | External/Utility | 中 | 否 | 否 | 否 | 是 | Webhook | 否 | 已完成 |
| xjj | External | 中 | 否 | 否 | 是 | 否 | HTTP/Telegram | Schema | 已完成 |
| yingchao_redpacket | Interactive | 中 | 否 | 否 | 否 | 是 | Telegram/OCR | 否 | 已完成 |
| zf | Utility | 低 | 否 | 否 | 否 | 否 | Telegram | Schema | 已完成 |
| zhuque_lottery | Interactive/External | 极高 | 是 | 是 | 是 | 是 | HTTP | Vue | P4 |
| zpr | External | 中 | 否 | 否 | 是 | 否 | HTTP/Telegram | Schema | 已完成 |

## 扫描结论

- 共 45 个 V2 插件。
- 本轮开始时 44 个插件仍包含 `_compat.py` 和 `_legacy` 运行路径；`config_migration` 已是原生入口。
- 已完成 `auto_changename`、`bomb_game`、`id`、`self_delete`、`zf`、`getmsg`、`jupai`、`msg_forward` 与 `auto_avatar` 的原生迁移并移除兼容运行层。
- 未发现 V2 业务入口直接导入 `pyrogram`；主要技术债集中在兼容层模拟 Pyrogram 消息、客户端、过滤器、同步 KV 和调度器。
- 下一批应优先迁移体量较小的 Interactive 插件，建立 callback 与文本互动的原生模板，再处理普通 Automation 和外部 Worker。
