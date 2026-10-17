# 安装与部署

本页适用于 AWBotNest V2。第一次安装，建议选“一键安装”；已经熟悉 Docker Compose，再选手动部署。

> V1 与 V2 不要共用 `data`、`sessions`、`plugins` 目录。V1 的插件和配置不能当成 V2 的配置直接导入。旧系统先保留，用新目录部署 V2。

## 1. 安装前准备

你需要准备：

- 一台能运行 Docker 的 Linux 服务器或 NAS。
- 服务器的 SSH 登录方式，以及 `root` 或 `sudo` 权限。
- 一个没有被占用的网页端口，默认 `18001`。
- 能从服务器访问 Docker 镜像仓库和 GitHub 的网络。

镜像支持以下架构：

| 设备架构 | 是否支持 | 常见设备 |
| --- | --- | --- |
| `x86_64` / `amd64` | 支持 | 常见 Intel、AMD 服务器与 NAS |
| `aarch64` / `arm64` | 支持 | 64 位 ARM 服务器、部分 NAS、运行 64 位系统的树莓派 |
| 32 位 ARM，如 `armv7l` | 不支持 | 部分旧设备或装了 32 位系统的树莓派 |

不确定架构时，在服务器终端执行：

```bash
uname -m
```

同一条安装命令和同一个镜像标签都能用于 AMD64、ARM64，不用自己寻找另一种镜像。系统支持某个架构，不代表每个插件的第三方依赖都支持它；遇到插件依赖安装失败，请同时提供设备架构和错误日志。

## 2. 一键安装：推荐新手使用

### 第一步：打开服务器终端

用 SSH 工具登录服务器。下面的命令在服务器上执行，不是在电脑浏览器地址栏里输入。

如果没有 `curl`，先按服务器发行版安装它。例如 Debian、Ubuntu：

```bash
sudo apt-get update
sudo apt-get install -y curl
```

### 第二步：执行安装命令

```bash
curl -fsSL https://raw.githubusercontent.com/AWdress/AWBotNest/v2/install.sh | sudo bash
```

这条命令会下载并以管理员权限运行安装脚本。希望先检查脚本内容，可以先在 [GitHub 查看 install.sh](https://github.com/AWdress/AWBotNest/blob/v2/install.sh)，确认后再运行。

脚本会询问以下内容。直接回车代表接受括号中的默认值。

| 提问 | 默认值 | 该怎么选 |
| --- | --- | --- |
| 安装位置 | `/opt/AWBotNest` | 新手用默认值即可；记住这个目录，后续更新和备份要用 |
| 网络模式 | `bridge` | 没有特殊需求用 `bridge` |
| 访问端口 | `18001` | 仅 bridge 模式询问；这是浏览器访问的端口 |
| 系统监听端口 | `18001` | bridge 模式一般保持默认；host 模式填写要在宿主机使用的端口 |

脚本会检查 Docker，未安装时尝试安装；随后识别 Docker 服务器架构、检查 Compose、创建数据目录、拉取镜像并启动容器。下载速度取决于服务器网络，首次安装需要等待。

### 第三步：确认安装结果

看到类似下面的信息，说明启动命令已完成：

```text
AWBotNest 已启动。
镜像架构：linux/amd64
网络模式：bridge
访问地址：http://服务器IP:18001
安装目录：/opt/AWBotNest
```

架构也可能显示 `linux/arm64`，这是正常的。

用浏览器打开 `http://你的服务器IP:18001`。如果设置过其他访问端口，请替换 `18001`。首次打开后按 [首次使用](First-Run) 设置管理员。

> 脚本显示的 IP 可能是内网 IP。云服务器应使用你实际可以访问的公网 IP；家里或局域网部署则使用对应内网 IP。安装成功不代表防火墙已自动放行端口。

### 网页打不开时先查这三处

1. 在服务器执行 `docker ps -a --filter name=AWBotNest_V2`，看容器是否在运行。
2. 执行 `docker logs --tail 100 AWBotNest_V2`，看是否有启动错误。
3. 检查服务器防火墙、云厂商安全组、NAS 防火墙，是否允许你当前网络访问所选端口。

不要为了排错直接关闭全部防火墙。公网部署建议使用 HTTPS 反向代理，并限制管理入口的访问范围。

## 3. bridge 和 host 到底有什么区别

### bridge：端口映射，默认推荐

例如配置为：

```yaml
ports:
  - "19001:18001"
```

- 左边 `19001`：宿主机访问端口。浏览器打开 `http://服务器IP:19001`。
- 右边 `18001`：容器内系统监听端口。
- 两边可以不同，但右边必须与系统实际监听端口一致。

如果只是因为宿主机 `18001` 已被其他服务占用，通常只需要换左边，不必修改系统内的监听端口。

### host：直接使用宿主机网络

host 模式没有“左边映射到右边”。系统监听 `19001`，浏览器就访问 `http://服务器IP:19001`。

- 不要同时设置 `network_mode: host` 和 `ports`。
- 监听端口必须没有被宿主机上的其他程序占用。
- 容器里的 `127.0.0.1` 指向宿主机网络；bridge 模式则不是。配置本机代理时尤其要区分这一点。
- 本文 host 示例针对 Linux Docker；桌面版 Docker 的 host 支持情况请以 Docker 自身说明为准。

### 不想交互输入：进阶示例

host 模式，监听 `19001`：

```bash
curl -fsSL https://raw.githubusercontent.com/AWdress/AWBotNest/v2/install.sh | \
  sudo env AWBOTNEST_MODE=host AWBOTNEST_PLATFORM_PORT=19001 bash
```

bridge 模式，浏览器访问 `19001`，容器内仍监听 `18001`：

```bash
curl -fsSL https://raw.githubusercontent.com/AWdress/AWBotNest/v2/install.sh | \
  sudo env AWBOTNEST_MODE=bridge AWBOTNEST_PORT=19001 AWBOTNEST_PLATFORM_PORT=18001 bash
```

这些变量是安装脚本参数，不是在网页里填写的项目。`AWBOTNEST_DIR` 可指定安装目录，`AWBOTNEST_IMAGE` 可指定镜像标签。已有安装再次运行时，要使用原目录和原网络、端口设置，不要随手一路回车改掉原来的部署方式。

## 4. 手动 Docker Compose 部署

以下步骤要求已经安装 Docker 和 Docker Compose。可先检查：

```bash
docker version
docker compose version
```

### 第一步：创建独立目录

示例使用 `/opt/AWBotNest`。已有 V1 或其他部署时，请换一个新目录。

```bash
sudo mkdir -p /opt/AWBotNest/data /opt/AWBotNest/sessions /opt/AWBotNest/plugins
cd /opt/AWBotNest
```

用宝塔、NAS 文件管理器或自己熟悉的编辑器，在此目录新建 `docker-compose.yml`，粘贴下面内容。YAML 的缩进用空格，不用 Tab。

### bridge 模式配置

```yaml
services:
  awbotnest:
    image: awdress/awbotnest_v2:latest
    container_name: AWBotNest_V2
    restart: always
    environment:
      TZ: Asia/Shanghai
    ports:
      - "18001:18001"
    volumes:
      - ./plugins:/app/plugins
      - ./sessions:/app/sessions
      - ./data:/app/data
```

若宿主机 `18001` 已占用，可改为 `"19001:18001"`，随后从浏览器访问 `19001`。

### host 模式配置

```yaml
services:
  awbotnest:
    image: awdress/awbotnest_v2:latest
    container_name: AWBotNest_V2
    restart: always
    network_mode: host
    environment:
      TZ: Asia/Shanghai
      AWBOTNEST_WEB_PORT: "19001"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:19001/readyz', timeout=3)"]
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3
    volumes:
      - ./plugins:/app/plugins
      - ./sessions:/app/sessions
      - ./data:/app/data
```

这里指定系统监听 `19001`，健康检查也使用 `19001`。如果改端口，要把这两处一起改。环境变量指定的监听端口会在启动时覆盖配置文件中的值；不要只在网页里改一个数字，期待 Compose 的映射和健康检查也自动改变。

### 第二步：校验并启动

仍在 `docker-compose.yml` 所在目录执行：

```bash
docker compose config -q
docker compose pull awbotnest
docker compose up -d awbotnest
docker compose ps
```

`config -q` 没有输出且正常结束，代表配置格式通过校验；`ps` 应看到 `awbotnest` 正在运行。然后打开对应 IP 和端口，进入 [首次使用](First-Run)。

### 持久化目录不能省略

| 宿主机目录 | 容器内目录 | 作用 |
| --- | --- | --- |
| `./data` | `/app/data` | 系统设置、插件数据、Cookie、日志、依赖及浏览器缓存等 |
| `./sessions` | `/app/sessions` | Telegram 用户账号登录会话 |
| `./plugins` | `/app/plugins` | 已安装插件文件与插件界面资源 |

`./` 表示相对于 Compose 配置所在目录。重建容器可以保留这些目录里的内容，但换目录、改挂载路径或删宿主机目录都会影响数据。备份方法见 [更新与维护](Maintenance)。

## 5. 反向代理和 HTTPS

公网访问建议用 Nginx 或 Caddy，将域名的 HTTPS 请求反向代理到系统实际访问端口。反向代理需要支持 WebSocket，运行日志等实时功能才能正常工作。

- 系统与反向代理在同一宿主机时，上游示例为 `http://127.0.0.1:18001`。
- 反向代理也在独立容器里时，不能照抄这个地址：该容器的 `127.0.0.1` 是它自己。应按网络结构使用可达的宿主机地址或同一 Docker 网络中的服务名。
- 域名、证书和端口转发是在反向代理服务中设置的，不需要把域名填进容器内部监听端口。
- 企业微信回调需要公网可访问的 HTTPS 地址，详见 [账号与通知](Accounts-and-Notifications)。

## 6. 源码运行：仅建议有基础的用户使用

源码方式需要自己维护 Python、Node.js、浏览器系统依赖和进程守护。只想使用系统，建议选择 Docker。

项目声明 Python `3.11` 及以上；当前 Docker 镜像使用 Python `3.13`、前端使用 Node.js `22`。下面是 Linux 示例，要求系统已有 Git、Python 和 Node.js/npm。

```bash
git clone --branch v2 --single-branch https://github.com/AWdress/AWBotNest.git AWBotNest-v2
cd AWBotNest-v2
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
cd frontend
npm install
npm run build
cd ..
python -m awbotnest.main
```

说明：

- 某些 Linux 发行版需要先安装 Python 的 `venv` 支持包。
- Playwright 安装浏览器系统依赖时可能需要管理员权限。遇到提示请按其说明处理，不要把所有 Python 依赖随意安装到系统全局环境。
- `npm run build` 会把界面文件输出到项目的 `static` 目录；只启动 Python 而没有构建界面，不能得到完整网页。
- 命令会前台运行，关闭终端会影响进程。长期运行请配置 systemd 等进程管理器，工作目录为项目目录，解释器使用 `.venv/bin/python`。
- 有头浏览器需要可用显示服务。无桌面的 Linux 主机可安装 Xvfb 并通过 `xvfb-run -a python -m awbotnest.main` 启动；Docker 已处理这部分依赖。
- 运行数据保存在此项目的 `data`、`sessions`、`plugins`，同样不要与 V1 共用。

## 下一步

[首次使用](First-Run) · [更新与维护](Maintenance) · [常见问题](Troubleshooting) · [返回首页](Home)
