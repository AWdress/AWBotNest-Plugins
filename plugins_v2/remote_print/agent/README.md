# Windows 本地打印接收端

平台运行在服务器或 Docker，打印机连接在 Windows 电脑时，在这台电脑运行本接收端。它只向平台发起 HTTPS 请求领取任务和下载文件，不监听端口；电脑不需要公网 IP，也不需要设置端口映射。Windows 电脑、打印机和接收端均需保持在线。

支持 PDF、PNG、JPEG、WebP、BMP。PDF 使用 PDFium 逐页渲染，图片使用 Pillow 解码，最后通过 Windows GDI 提交到打印队列。不依赖浏览器、Office、Adobe Reader 或文件关联的“打印”命令。仅支持 Windows 10/11 的 Python 3.10+，建议 Python 3.11/3.12。

## 安装与配置

平台插件选择“Windows 电脑打印端”后才需要此程序；选择默认的“VPS / FRP 直连 IPP”时不需要安装或启动它。

将整个 `agent` 目录复制到打印机所在的 Windows 电脑。在该目录打开 PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe agent.py --list-printers
Copy-Item config.example.json config.json
```

`--list-printers` 只列出当前 Windows 账号可见的打印机以及系统默认打印机，不连接服务器，也不打印。把输出中的打印机名称完整填入 `allowed_printers` 和 `default_printer`，包括空格及大小写。

编辑 `config.json`：

| 字段 | 含义 |
| --- | --- |
| `server_url` | 平台的 HTTPS 访问地址，例如 `https://bot.example.com`；不能包含账号、密码、查询参数或片段。平台位于反向代理子路径时可包含该子路径。 |
| `device_id` | 与插件配置对应的设备 ID，例如 `home-printer`；只能含字母、数字、下划线和连字符。 |
| `token` | 为这台设备配置的独立认证令牌，至少 32 个无空格的 ASCII 字符。使用与平台插件相同的令牌。示例中为空，必须填写。 |
| `allowed_printers` | 接收端允许使用的本地打印机名称列表。任务指定的打印机必须与名单完全一致。 |
| `default_printer` | 未指定打印机时使用的名称，必须包含在名单内。省略时优先使用名单中的 Windows 默认打印机，否则使用第一个可用名称。 |
| `poll_seconds` | 领取任务的间隔，默认 5 秒，范围 1–300。 |
| `render_dpi` | PDF 渲染分辨率，默认 150，范围 72–200。 |
| `state_dir` | 可选，持久状态目录。默认 `%LOCALAPPDATA%\AWRemotePrint\设备ID`；相对路径以配置文件所在目录为基准。 |
| `allow_virtual_printers` | 默认 `false`。阻止 Microsoft Print to PDF、XPS、OneNote、Fax 等虚拟设备。只有明确启用且名称在名单内时才允许；需要“另存为”交互的驱动不适合无人值守运行。 |
| `allow_insecure_localhost` | 默认 `false`。仅本机调试时允许 `http://localhost`、`http://127.0.0.1` 或 `http://[::1]`。公网必须使用 HTTPS。 |

`config.json` 包含令牌，请只放在运行接收端的 Windows 账号可读取的位置，不提交到 Git。`state_dir` 也只应由这个账号管理，包含任务领取凭据和用于避免重复打印的日志。每台打印机电脑使用自己的设备 ID、令牌和状态目录；同一设备不能在多个电脑或多个状态目录同时运行。

## 检查与启动

```powershell
.\.venv\Scripts\python.exe agent.py --config .\config.json --check
.\.venv\Scripts\python.exe agent.py --config .\config.json
```

`--check` 验证配置、依赖、打印机名单及服务器认证，只发送设备握手，不领取、下载或打印任务。日常运行会先握手再循环领取任务；断网会自动重试，Ctrl+C 会停止接收端。HTTPS 证书必须能通过本机信任验证；接收端不会使用环境代理，也不会跟随重定向。反向代理应直接转发以下路径，不能跳转到登录页或另一个地址：

- `POST /api/plugin/remote_print/agent`
- `GET /api/plugin/remote_print/agent_file`

只处理一次领取请求后退出：

```powershell
.\.venv\Scripts\python.exe agent.py --config .\config.json --once
```

`--once` **可能实际打印一个任务**，用于人工控制的单次运行；诊断连接请使用 `--check`。

需要自动启动时，可在 Windows 任务计划程序创建“用户登录时”任务，程序使用该虚拟环境的 `python.exe`，参数使用 `agent.py` 和 `--config` 的绝对路径，选择安装打印机的同一 Windows 账号。先以普通用户手动验证，不需要更改系统默认打印机或以管理员身份运行。

## 打印结果与恢复

接收端下载后验证文件大小和 SHA-256，在授权打印前完成全部页面的解码和渲染。图片及 PDF 页面按比例缩放到打印机可打印区域，保留打印机已有的纸张设置，不裁切图片。

1.0.0 支持自动双面方向，按左右翻阅：竖向长边、横向短边；服务器识别后将具体方向和翻页参数交给电脑端，私有 DEVMODE 明确设置横向／竖向并验证驱动是否接受。平台插件和电脑端请同时更新为1.0.0，旧电脑端不会领取自动方向任务。仍保留手动单面、长边、短边覆盖；未指定时沿用 Windows 打印机默认设置。双面打印必须由打印机和当前驱动支持自动双面，接收端会在提交前检查驱动能力并验证参数。驱动不支持、无法确认能力或拒绝设置时，会报告明确原因并停止此任务，**不会偷偷改为单面**。仅使用任务专属的打印参数，不保存或修改系统打印机默认设置。指定单双面前请同时更新平台插件和这台电脑的接收端；旧版接收端不会领取指定单双面的任务。

为保证份数准确，任务专用的打印参数将驱动份数设为 1，再按任务份数分别提交完整文档，避免 Windows 默认份数再次相乘。每份使用独立的打印队列文档，奇数页的双面文档不会把下一份的第一页打印在上一份背面。0.0.18 起，“全部双面打印”将同一批多张图片在服务器合成一个 PDF，第一张正面、第二张背面。合并 PDF 已展开所选份数并在每份奇数页末尾补白，电脑端接收份数为1，只提交一次；其他文件仍独立打印。

本地固定上限为文件 25 MiB、50 页、10 份、每页 2500 万像素、整个文档渲染后 6000 万像素。服务器允许值更低时以服务器任务为准。较长文档即使未超过页数也可能触发像素上限，可以降低 `render_dpi` 或拆分文件；多帧/动画图片不接受。

`submitted` 代表已成功提交 Windows 打印队列，不能证明纸张已出纸。打印机缺纸、断线或卡纸应在 Windows 打印队列处理。

日志会先持久记录 `started`，再向服务器申请执行，得到明确授权后才调用 Windows 打印 API。授权响应丢失、提交过程异常、进程崩溃等无法确认的情况会报告 `unknown`，**不会自动重新打印**。重启只补报结果；报告暂时失败时会持续重试，不再次提交打印。已确认的任务 ID 仍保留用于去重。

遇到 `unknown`，先检查 Windows 打印队列和实际出纸，再决定是否在平台创建新任务。请保留 `journal.json`，不要删除、修改或恢复到旧备份，否则会丢失避免重复打印的依据。日志损坏或无法持久保存时接收端会停止，需人工检查后再恢复。若进程在准备文件时被强制终止，状态目录内可能遗留 `work-*` 临时目录；停止接收端后可只删除这些临时目录，保留 `journal.json` 和锁文件。
