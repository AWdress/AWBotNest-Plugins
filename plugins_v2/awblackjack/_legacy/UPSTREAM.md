# AWBlackJack 迁移说明

本插件由本地 `AWBlackJack` 项目迁移，原项目 README 标注为 MIT License。

- 保留原项目的 SpringSunday 21 点对局、抓牌、停牌、主动对战和平局协助状态机。
- 保留 MQTT 跨实例协议；每个 AWBotNest 插件实例只运行一个站点账号。
- 新增 AWBotNest 配置、数据目录、日志、通知、进程监督与生命周期适配。
- 移除原项目中仅用于告警的硬编码账号列表，队友状态以 MQTT 在线上报为准。
