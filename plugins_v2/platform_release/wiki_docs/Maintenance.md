# 更新、备份与日常维护

本文的 Docker 命令默认：安装目录 `/opt/AWBotNest`、服务名 `awbotnest`、容器名 `AWBotNest_V2`。如果你安装时改过，请换成自己的值。

## 1. 先记住三个目录

| 目录 | 主要内容 | 丢失的影响 |
| --- | --- | --- |
| `data` | 系统设置、插件设置和数据、Cookie、依赖、缓存、日志等 | 设置和运行数据可能丢失 |
| `sessions` | Telegram 用户账号登录会话 | 通常需要重新登录账号 |
| `plugins` | 插件程序和界面资源 | 需要重新安装相应插件 |

更新镜像与删除数据不是一回事。只要持久化挂载正确，按本文更新或重建容器不会主动删除这三个宿主机目录。

> 不要执行带 `-v` 的删除卷命令来“清缓存”，也不要直接清空整个安装目录。重建容器前先确认挂载，再做备份。

## 2. 配置包与完整备份不是一回事

![维护、日志清理与配置导入导出](https://raw.githubusercontent.com/wiki/AWdress/AWBotNest/images/maintenance.jpg)

| 方式 | 保存什么 | 不保存什么 | 适合用途 |
| --- | --- | --- | --- |
| 网页“下载配置包” | 系统设置、插件设置 | Telegram 会话、Cookie 数据、日志、插件程序和其他运行文件 | 修改设置前留档，导入相同类型的 V2 设置 |
| 备份三个目录及 Compose | `data`、`sessions`、`plugins` 和部署配置 | 系统镜像本身、服务器其他服务 | 迁移服务器、完整恢复、重要更新前保护数据 |

配置包不是脱敏包，也不是加密保险箱。里面可能包含 API Key、Bot Token、通知凭据、账号配置及管理员认证资料。完整备份的权限更大，尤其要保护 Telegram 会话和 Cookie。

### 网页导出配置

1. 进入“系统设置 → 维护”。
2. 点击“下载配置包”。
3. 等待浏览器下载 `AWBotNest-config-时间.zip`。
4. 将文件保存到只有你能访问的位置；不要上传公共网盘或 Git 仓库。

浏览器没有出现下载时，检查下载列表与弹窗拦截，并查看系统日志中的“配置包下载”记录。

### 网页导入配置

1. 先导出一次当前配置，留作恢复用。
2. 在“系统设置 → 维护”点击“选择配置包”。
3. 选择本系统支持的 V2 ZIP 配置包。
4. 阅读预览：哪些系统项、插件项会新增、修改或删除。
5. 确认内容无误后，点击“暂存并导入”。
6. 系统会保存导入前配置快照；如浏览器开始下载快照，请妥善保管。
7. 按页面提示重启，重启后才应用导入的设置。

请注意：

- 导入是配置替换，不是只补上缺失项。预览中的“删除”也需要检查。
- 导入不会把插件程序装回来，不会恢复账号会话、Cookie 数据或日志。
- 配置包会受到格式和体积校验，上传上限为 16 MB。不要把手工打包的全部数据目录当成配置包上传。
- 预览后又修改了当前设置，或换了另一个配置包，需要重新预览。
- 配置含管理员认证资料，导入其他实例的配置后，登录凭据可能随配置改变。重启后若需要重新登录，请使用导入来源对应的管理员凭据。
- 不要导入 V1 配置或不可信来源的配置包。

## 3. 完整备份：建议更新前做

备份运行中的数据库或会话文件可能出现不一致，最稳妥的方式是短暂停止系统后打包。下面不会删除原数据。

### 第一步：核对部署目录和挂载

```bash
cd /opt/AWBotNest
pwd
docker inspect AWBotNest_V2 --format '{{json .Mounts}}'
```

确认宿主机的 `data`、`sessions`、`plugins` 分别挂载到 `/app/data`、`/app/sessions`、`/app/plugins`。如果实际数据不在此处，先找准目录，不要备份一个空目录就认为完成了。

### 第二步：停止并打包

```bash
docker compose stop awbotnest
sudo tar -czf /opt/AWBotNest-full-backup-20261017.tar.gz \
  data sessions plugins docker-compose.yml
sudo chmod 600 /opt/AWBotNest-full-backup-20261017.tar.gz
docker compose start awbotnest
```

把示例日期换成实际日期，并使用一个不存在的新文件名，避免覆盖旧备份。若 `tar` 报错，先查原因；不要把不完整的压缩包当成有效备份。打包完成后把备份复制到另一台设备保存。

如果有 `docker-compose.awbotnest-runtime.yml`、自行使用的 Compose override、`.env` 或额外挂载目录，也应一并备份。`chmod 600` 只限制本机读取权限，不会给压缩包加密。

### 恢复到新目录或新服务器

1. 在新服务器准备 Docker，暂时不要启动系统。
2. 创建一个空的恢复目录，例如 `/opt/AWBotNest-restored`。
3. 先用 `tar -tzf 备份文件路径` 查看压缩包内容，确认是自己备份的相对路径。
4. 将可信备份解压到新目录，而不是直接覆盖一个仍在运行的实例。
5. 核对 Compose 的挂载、端口、网络模式与镜像标签。
6. **先停止旧实例**，再从新目录启动；不要让两套实例同时使用同一 Telegram 会话文件。
7. 检查管理员登录、账号、插件和通知是否正常。

一个解压示例：

```bash
sudo mkdir -p /opt/AWBotNest-restored
sudo tar -xzf /opt/AWBotNest-full-backup-20261017.tar.gz -C /opt/AWBotNest-restored
cd /opt/AWBotNest-restored
docker compose config -q
docker compose up -d awbotnest
```

示例适用于新服务器，或已经确认没有同名容器、端口冲突的环境。**仅停止旧容器不会释放 `AWBotNest_V2` 这个容器名称。** 同机恢复时，应先停用旧实例，再为恢复目录中的 Compose 设置不同的 `container_name`，并核对端口；如果要沿用旧名称，则先在完整备份后妥善处理旧容器。不要只复制目录就直接启动，更不要让新旧实例同时运行同一套账号会话。

跨 AMD64、ARM64 迁移时，Python 原生依赖和浏览器缓存不一定能直接复用。先保留原备份，再检查日志并按实际架构重新准备相应依赖，不能只复制一个浏览器可执行文件就认为兼容。

## 4. 更新 Docker 镜像

### 更新前

1. 在 [版本发布页](https://github.com/AWdress/AWBotNest/releases) 阅读更新内容。
2. 备份数据，尤其是重要插件的配置和会话。
3. 确认原安装目录、网络模式、端口与镜像标签。

### 用一键安装脚本更新

可以再次运行 [安装页中的一键命令](Installation)，选择**原来的安装目录、网络模式和端口**。脚本会拉取镜像并重新启动服务。

安装脚本生成的 Compose 会按这次选择重新生成，并保留原配置副本；如果曾手工增加配置，更新前应先备份并核对。自定义 Compose 可能另外生成运行模式覆盖文件，详见下文。

### 用 Compose 手动更新

在原安装目录执行：

```bash
cd /opt/AWBotNest
docker compose pull awbotnest
docker compose up -d awbotnest
docker compose ps
docker compose logs --tail 100 awbotnest
```

网页“立即重启”只会重新加载系统，不能代替 `pull` 下载新镜像。

### 注意一键脚本的覆盖文件

如果安装时提示生成了 `docker-compose.awbotnest-runtime.yml`，后续要把它和基础配置一起使用，例如更新时：

```bash
docker compose -f docker-compose.yml -f docker-compose.awbotnest-runtime.yml pull awbotnest
docker compose -f docker-compose.yml -f docker-compose.awbotnest-runtime.yml up -d awbotnest
```

同理，`ps`、`stop`、`start` 等命令也应带相同的 `-f` 文件列表。Docker 不会因为这个文件放在目录里，就自动识别它作为默认 override。

### 固定某个版本

Compose 中 `image: awdress/awbotnest_v2:latest` 表示拉取 `latest` 标签。需要固定发布版本，可换成确实存在的标签，例如：

```yaml
image: awdress/awbotnest_v2:v2.0.1.6
```

改完后再执行 `pull` 和 `up -d`。不要凭空填写不存在的版本号。回退镜像前，也要确认该旧版能够读取现有配置和数据；镜像回退不能代替数据备份。

## 5. 新版本检查与通知

- 系统启动时检查更新，之后后台每小时检查一次。
- 网页也会获取更新状态，不必只在“关于”页才发现新版本。
- “系统设置 → 通知渠道”的“系统更新通知”默认开启；配置好默认 Bot 通知后，检测到新版本会发送更新内容。
- 检查更新只是发现新版本，不会在后台自动替你更新 Docker 镜像。

新版本入口出现后，先阅读更新内容，再按本页备份和更新。网络访问不到 GitHub 时，更新检查可能失败；没有提示不能作为“绝对没有新版本”的证明。

## 6. 停止、启动、重启和日志

以下命令不会主动删除持久化数据：

```bash
cd /opt/AWBotNest
docker compose stop awbotnest
docker compose start awbotnest
docker compose restart awbotnest
```

三条命令分别用于停止、启动、重启，不是让你每次都连续执行。

查看最近 100 条容器输出：

```bash
docker logs --tail 100 AWBotNest_V2
```

持续查看新日志：

```bash
docker logs --tail 100 -f AWBotNest_V2
```

按 `Ctrl+C` 只是结束本次日志查看，不会停止容器。

日常优先在网页“运行日志”筛选级别、关键词或来源。某个插件出问题，可以从该插件菜单查看日志；提交问题前请遮住手机号、Token、Cookie、验证码和其他隐私内容，系统的自动脱敏不代表所有第三方插件输出都绝对安全。

## 7. 日志清理到底清理什么

“系统设置 → 维护”中的日志清理，处理的是**系统与插件共用的网页日志历史**，按总条数保留，不是每个插件各留指定条数。

### 自动清理

1. 打开“日志清理”开关。
2. 设置“每天执行时间”，按 `Asia/Shanghai`（中国标准时间，UTC+8）执行；系统调度器使用此时区，不随浏览器或宿主机的显示时区自动变化。
3. 设置“历史保留条数”，允许 1～1000。
4. 点击“保存设置”，有重启提示时按提示重启。

默认开启，每天 `03:00` 执行，保留 1000 条。系统启动后可在日志中看到定时任务启动记录。

### 手动清理

点击“立即清理日志”并确认。手动清理使用的是**已保存**的设置；刚在页面改了保留条数，要先保存再清理。

执行后会记录实际条数，例如：

```text
日志手动清理完成：清理 120 条，保留 100 条
```

定时执行对应“日志自动清理完成”。即使没有需要删除的记录，也会显示清理 0 条的结果。保留条数不包含随后新写入的这条清理结果，因此界面多出一条或后续继续增长是正常的。

### 不会清理的内容

- 不删除 `data/logs/app.log` 及其轮转文件。
- 不清空 Docker 自己保存的容器输出日志。
- 不删除插件数据库、账号会话、Cookie 或浏览器缓存。

`app.log` 使用大小轮转，单份约 5 MiB，保留最多 5 份历史文件，另有当前日志。Docker 日志的保留策略由 Docker 配置控制，与网页清理不是同一个功能。

## 8. 内存占用高时怎么查

先区分是 Python 主进程、浏览器进程还是文件缓存，不要看到 Docker 总数就直接判断“某插件泄漏”。

```bash
docker stats AWBotNest_V2 --no-stream
docker top AWBotNest_V2 -eo pid,ppid,rss,comm
docker inspect AWBotNest_V2 --format 'Memory={{.HostConfig.Memory}} MemorySwap={{.HostConfig.MemorySwap}}'
```

- `docker stats` 显示容器总占用，和进程 RSS 不会完全相同。
- `RSS` 单位通常是 KiB，不是 MiB。
- Chromium/CloakBrowser 执行网页验证时会产生额外内存峰值。
- 安装了插件依赖不等于它们全部一直运行；要结合进程与当时任务判断。

Linux cgroup v2 环境还可只读查看：

```bash
docker exec AWBotNest_V2 sh -c 'grep -E "^(anon|file|inactive_file|active_file|shmem|kernel|slab) " /sys/fs/cgroup/memory.stat'
```

若提示文件不存在，可能是旧版 cgroup，不要为此修改或删除系统文件。

### 出现“突然重新初始化”

先看容器是否重启：

```bash
docker inspect AWBotNest_V2 --format 'StartedAt={{.State.StartedAt}} RestartCount={{.RestartCount}} OOMKilled={{.State.OOMKilled}}'
```

如果宿主机有 systemd，可用 `journalctl -k` 查看对应时段的内核日志，寻找 `oom`、`Killed process`、`Memory cgroup out of memory`。容器重启后的 `OOMKilled=false`，不能单独排除上一轮运行发生过 OOM。

内存额度不是越低越好。把容器限制压得过小，系统、多个插件和浏览器同时工作时，内核可能直接结束进程。先收集日志和峰值，再决定增大额度、减少同时运行的重型任务或调整插件。

系统的浏览器公共服务会对执行名额排队，等待名额不消耗系统自有的插件执行时限；轮到任务后仍受实际执行时限约束。插件自己启动的独立浏览器、自己设置的超时和外部网站行为，不会自动被改写。不要因此认为所有第三方插件都能无限期等待，或已经杜绝 OOM。

内存较高时，系统会低频记录内存诊断。它只用于定位，不会自动终止插件或浏览器。向开发者反馈时，请附“占用高的时刻、正在运行的插件、上述命令输出及对应日志”，并先脱敏。

[安装与部署](Installation) · [插件管理](Plugins) · [Cookie 与浏览器](Cookies-and-Browser) · [常见问题](Troubleshooting) · [返回首页](Home)
