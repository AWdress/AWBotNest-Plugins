# AWBlackJack

SpringSunday 21 点单账号自动挂机插件。

## 部署方式

- 一个 AWBotNest 实例只配置一个 SpringSunday 账号。
- 需要协同的所有插件实例连接同一个 MQTT Broker；Broker 可以部署在 VPS、NAS 或其他可被各实例访问的主机上。
- 每个账号必须填写不同的站点用户 ID，MQTT 地址、用户名和密码则保持一致。
- 插件不会在本机启动第二个站点账号。

## 协同流程

1. 各账号把等待局、对局编号、金额和当前点数发布到共享 Broker。
2. 其他实例依据自己的站点状态和配置判断是否加入。
3. 出现平局求助时，符合金额、点数和并发限制的其他账号响应并进入对局。
4. 异常和个人战绩通过告警主题回传当前插件实例，用于平台日志、通知和运行状态。

MQTT 主题与原项目兼容：`blackjack/games`、`blackjack/states`、`blackjack/help`、`blackjack/alerts`。
