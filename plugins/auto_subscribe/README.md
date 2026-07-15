# 自动订阅助手 (auto_subscribe)

聚合多个榜单源（豆瓣 / Mikan 新番 / 奈飞 / 猫眼），按过滤条件筛选后，通过 **NextFind OpenAPI** 自动订阅。定时运行 + 结果推送，并自带 Vue 配置/管理界面。

> 迁移自 MoviePilot 插件 [`automaticsubscriptionassistant`](https://github.com/Aqr-K/Moviepilot-Plugins)（作者 Aqr-K），订阅落地后端由 MoviePilot 订阅引擎改为 NextFind。

## 工作流程

```
provider 抓榜单 → RankMediaItem(标题/年份/类型/…)
  → pre 过滤(热度) → NextFind /search 取最佳匹配(类型一致+年份就近)
  → 库/订阅判定 + 评分/类型/年份过滤 → POST /subscriptions/add → 记历史(ctx.kv)
```

关键：一次 `GET /search` 就返回 `id(=tmdb)`、`raw_type`、`year`、`_vote_average`、`is_subscribed`、`is_in_library`，所以识别、去重、库查重、评分过滤合并为一步，无需多次请求。

## 榜单源

| 源 | 数据 | 说明 |
|----|------|------|
| 豆瓣 | RSSHub 豆瓣榜单 RSS | 7 个内置榜单 + 自定义 RSS；rsshub.app 被墙可换自建实例 |
| Mikan 新番 | 蜜柑计划季度番剧 | 可抓详情补真实放送年（更准更慢） |
| 奈飞 | Tudum Top10 公开 TSV | 全球榜 + 94 国国家榜；富元数据模式补年份提升识别 |
| 猫眼 | 猫眼专业版票房/网播 | **无 Cookie 降级**（平台无 Playwright），个别榜可能受风控为空 |

> 未迁：MoviePilot 的「热门媒体(popular)」源依赖其自建统计服务器，NextFind 无对应。

## 过滤

- **全局过滤**：年份≥ / 评分≥ / 热度≥ / 媒体类型（默认应用到所有源）。
- **每源独立过滤**：每个源可开「独立过滤」开关，用该源自己的 年份≥ / 评分≥ / 媒体类型 覆盖全局（热度恒走全局）。

## 配置界面（Vue 模式）

`render_mode: "vue"`，配置弹窗由自带的 `frontend/src/Config.vue` 渲染，三个页签：

- **设置**：NextFind 地址/密钥（测试连接）、定时 cron、结果推送、全局过滤、各源开关与选项及独立过滤、立即运行。
- **历史**：本插件处理过的条目（新增订阅/已订阅/库中已有/未识别/已过滤），可按状态筛选、删除、清空。
- **订阅**：NextFind 当前活跃订阅列表，可取消订阅。

配置值经 `host.getConfig/saveConfig` 存平台统一存储，插件里 `ctx.config` 读取。业务数据经 `ctx.on_api` 接口 + `host.callApi` 交互。

### 后端接口（ctx.on_api）

| 路径 | 方法 | 用途 |
|------|------|------|
| `/test` | GET | 测试 NextFind 连接（查额度） |
| `/run` | POST | 立即运行一轮，返回汇总 |
| `/history` | GET | 处理历史列表 |
| `/history/delete` | POST | 删除单条 / 清空历史 |
| `/subscriptions` | GET | NextFind 活跃订阅列表 |
| `/subscriptions/remove` | POST | 取消某条订阅 |

## 定时与推送

- `schedule`：标准 5 段 cron，默认 `0 8 * * *`（每天 08:00）。留空=不定时（只能手动运行）。
- `notify`：开启后每轮跑完 `ctx.notify` 推送汇总（新增/已订阅/库中已有/未识别/过滤/失败计数）。

## 出站代理

- NextFind 是自建服务：客户端 `trust_env=False` **直连**，绕过平台境外代理。
- 榜单抓取（豆瓣/奈飞/猫眼）：默认走平台代理（应对 rsshub.app / Netflix 被墙）。

## 开发（前端）

```bash
cd frontend
npm install
npm run dev     # 本地预览（mock host）
npm run build   # 构建产物到 dist/，发布时一并提交
```

平台加载的是 `frontend/dist/assets/remoteEntry.js` 构建产物，改前端后必须重新 build 并提交 `dist/`。

## 已知限制

- 识别靠 `/search` 标题+年份+类型搜索（无豆瓣id/番组id精确定位），同名不同作品可能误配；奈飞 TSV 无年份时开富元数据模式可缓解。
- 猫眼无 Cookie 降级，网播接口可能返回受限。
- 国家榜整表约 30MB，靠周更缓存摊薄；同一刷新周内不重复抓取。
