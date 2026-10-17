# 插件开发入门

这一页面向会一点 Python、想写第一个 V2 插件的人。先完成一个不需要 Telegram、网络或额外依赖的小例子，再按需求接入其他能力。

完整规范与详细接口放在源码文档中，本文不重复所有参数：

- [插件开发指南](https://github.com/AWdress/AWBotNest/blob/v2/docs/PLUGIN_GUIDE.md)
- [插件硬性规范](https://github.com/AWdress/AWBotNest/blob/v2/docs/SPEC.md)
- [开放 API 说明](https://github.com/AWdress/AWBotNest/blob/v2/docs/API.md)
- [单文件模板](https://github.com/AWdress/AWBotNest/blob/v2/plugins/_TEMPLATE.py)

相关使用说明：[插件管理](Plugins) · [开放 API](Open-API) · [AI 服务](AI-Service) · [Cookie 与浏览器](Cookies-and-Browser)

## 1. 最小可用插件

在自己电脑上新建 `hello_demo.py`，使用 UTF-8 编码保存下面的完整内容：

```python
__plugin__ = {
    "id": "hello_demo",
    "name": "入门示例",
    "version": "1.0.0",
    "scope": "standalone",
    "plugin_api_version": 2,
    "description": "在配置页点击按钮，向插件日志写入一条消息。",
    "requirements": [],
    "config_schema": {
        "message": {
            "type": "string",
            "label": "消息内容",
            "default": "你好，AWBotNest！",
            "required": True,
        },
        "run_once": {
            "type": "action",
            "label": "运行一次",
            "action": "run",
        },
    },
}


async def setup(ctx):
    async def run(payload):
        message = str(ctx.config.get("message", "你好，AWBotNest！"))
        ctx.log.info("示例消息：%s", message)
        return {"ok": True, "message": "已写入插件日志"}

    ctx.action("run", run)
    ctx.log.info("入门示例已启动")


async def teardown(ctx):
    ctx.log.info("入门示例已停止")
```

这段代码不会连接网站、发送消息或申请付费服务。

### 怎么测试

1. 在「插件管理 → 我的插件」上传 `hello_demo.py`。
2. 打开配置，填写消息内容并保存。
3. 开启插件，等待启用成功。
4. 再打开配置，点击「运行一次」。动作需要插件已经启用。
5. 打开该插件日志，应看到“入门示例已启动”和“示例消息：……”记录。
6. 修改消息内容并保存，再运行一次，检查新内容是否生效。
7. 停用插件，确认出现停止记录，再启用一次，检查动作没有重复注册。

不要双击 Python 文件来运行它。插件由系统调用 `setup(ctx)` 并提供上下文；单独执行这个文件不会自动启动系统，也不会出现配置页。

## 2. 必须理解的几项规则

### 文件名与 ID

单文件插件使用 `plugins/hello_demo.py`，目录插件使用 `plugins/hello_demo/__init__.py`。两种情况下 ID 都应是 `hello_demo`。

`__plugin__` 必须是入口顶层的**字面量字典**。系统先用静态分析读取它，不要通过函数、环境变量或动态拼接生成整份元数据。

改了插件 ID 就是另一个插件，不会自动继承原来的配置、任务命名空间和数据。

### 生命周期

- `setup(ctx)`：注册消息、动作、任务和资源。
- `teardown(ctx)`：处理插件自己的退出逻辑；没有额外资源时可以很简单。
- 停用、重载、系统退出时，系统会移除它管理的处理器和任务。
- 后台协程用 `ctx.create_task()`，额外资源用 `ctx.add_cleanup()` 登记释放。
- 不要吞掉 `asyncio.CancelledError`，也不要启动系统无法追踪的永久线程或协程。

### V2 不是 V1 改个版本号

V2 使用 Telethon。V1 插件中的客户端、调度器或内部模块可能不适用，不能只改 `version` 就宣传兼容。新插件使用正式 `ctx` 接口，不导入其他插件的实例，也不读取系统真实配置文件来绕过权限。

## 3. 选对作用域

| `scope` | 用途 |
| --- | --- |
| `standalone` | 不监听 Telegram，适合定时任务、HTTP 工具或配置页操作。 |
| `bot` | 接收所绑定 Telegram Bot 的事件。 |
| `user` | 接收管理员所选 Telegram 用户账号的事件。 |
| `both` | 同时挂载 Bot 与用户账号，注意避免重复处理。 |
| `wecom` | 企业微信专用插件，使用系统统一回调，不需要 Telegram 凭据。 |

需要多用户账号分别运行时，阅读 `instance_mode: "account"` 规范。账号实例有独立上下文和数据命名空间，不能擅自合并成共享存储。

## 4. 配置页、动作和内部 API

### 优先使用 Schema

入门例子中的 `config_schema` 会自动生成表单；一般参数无需自己写 Vue。字符串、密码、数字、开关、下拉选项、列表、会话选择及动作按钮都有现成类型。

密码用 `type: "password"` 或显式 `secret: True` 声明，嵌套敏感字段也要声明。否则系统不知道某个普通字段里其实放的是密钥。

读配置使用 `ctx.config`。持久化业务数据使用异步 `ctx.storage`；不要把 Cookie、账号密码或 Token 写进日志和动作结果。

### 动作

通过 `ctx.action("run", callback)` 注册，回调可接收一个 `payload`。Schema 的动作按钮要用同样的动作名。

动作不是 Telegram 命令。企业微信也可调用已启用、关联到该渠道的插件动作；不要期待任意 Telegram 文本处理器自动变成企业微信指令。

### 自定义 Vue 页面

复杂列表、图表或专门的交互才需要 Vue。目录插件设置 `render_mode: "vue"`，发布已构建的 `frontend/dist` 模块联邦产物，暴露 `./Config`。

配置组件使用系统传入的 `host`：

- `host.getConfig()`、`host.saveConfig()`：读写配置。
- `host.revealSecret(field)`：管理员主动查看某个已声明的敏感字段；不要在页面初始化时批量读取真实值。
- `host.callApi()`：调用当前插件的管理员内部接口。
- `host.ui.CronInput`：使用系统统一 Cron 编辑器。

内部接口用 `ctx.on_api()` 注册，只对管理员配置操作开放；不要为配置页随意注册公开 Webhook。Vue 的前端依赖由作者构建，系统启用插件时不会帮你运行 `npm install` 或编译前端。

详细说明：[配置表单](https://github.com/AWdress/AWBotNest/blob/v2/docs/PLUGIN_GUIDE.md#配置表单) · [Vue 配置界面（开发指南中的同名章节）](https://github.com/AWdress/AWBotNest/blob/v2/docs/PLUGIN_GUIDE.md) · [配置页内部 API](https://github.com/AWdress/AWBotNest/blob/v2/docs/PLUGIN_GUIDE.md#配置页内部-api)

## 5. Cron 字段与定时任务是两件事

要让配置页显示规则编辑器，字段按下面声明：

```python
"schedule": {
    "type": "string",
    "format": "cron",
    "label": "执行周期",
    "default": "0 9 * * *",
}
```

这里只提供配置输入、描述和校验，**不会自动创建一个执行任务**。插件仍需读取配置并正确注册任务。不要依赖字段名里包含 `cron`、`schedule` 就能自动识别。

如果只是固定每天执行，可在 `setup(ctx)` 中注册：

```python
async def daily():
    ctx.log.info("每日任务已执行")

ctx.schedule_cron("daily", daily, hour=9, minute=0)
```

`schedule_cron` 接收 APScheduler 字段参数，不是把任意 Cron 字符串直接塞给 `hour`。自定义字符串转换、五段/六段兼容和时区处理，请阅读[调度与后台任务](https://github.com/AWdress/AWBotNest/blob/v2/docs/PLUGIN_GUIDE.md#调度与后台任务)，对照正式插件接口实现并测试；不要套用开放 REST API 的请求格式。

普通周期任务可用 `ctx.schedule_interval("refresh", refresh, seconds=300)`。任务名称应稳定且在插件实例内唯一，不要每次运行都重新注册一个新任务。

不要在异步回调里调用 `time.sleep()` 或同步网络请求。使用异步服务，必要的阻塞工作按正式接口移到工作线程，避免拖住整个事件循环。

## 6. 复用系统服务

| 需求 | 优先使用 | 需要注意 |
| --- | --- | --- |
| 发通知 | `await ctx.notify(...)`、`ctx.notify_table(...)` | 跟随管理员通知路由；内容避免泄露敏感值。 |
| HTTP 请求 | `ctx.http` | 继承系统代理；外部请求设置超时并处理失败。 |
| AI 文字、识图、生图 | `ctx.ai.chat/vision/generate_image` | 使用管理员分配的能力与模型，不在插件里重复保存 AI Key。 |
| 网站 Cookie | `ctx.cookies` | 元数据声明 `cookie_domains`，按域名读取，不能读取任意站点。 |
| 浏览器任务 | `ctx.browser` | 复用系统设置、下载缓存与执行队列，使用完正确关闭资源。 |
| 本地 OCR | `ctx.ocr` | 按指南声明实际依赖，使用托管 OCR，避免长期占住模型内存。 |
| 持久化数据 | `ctx.storage`、`ctx.data_dir` | 只写插件自己的命名空间和目录。 |
| 短期交互状态 | `ctx.sessions` | 适合会话锁与临时状态，不要高频写数据库。 |

具体签名及示例：[系统服务](https://github.com/AWdress/AWBotNest/blob/v2/docs/PLUGIN_GUIDE.md#系统服务) · [通知](Accounts-and-Notifications) · [AI 配置](AI-Service) · [Cookie 与浏览器](Cookies-and-Browser)

企业微信文字、图片、文件和按钮事件通过 `ctx.on_wecom_message()` 接入统一回调；消息类型、成员隔离、媒体大小限制、回复方法见[企业微信统一消息回调](https://github.com/AWdress/AWBotNest/blob/v2/docs/PLUGIN_GUIDE.md#企业微信统一消息回调)。不要为同一个应用另搭一套不必要的回调入口。

## 7. 第三方依赖怎么声明

在元数据中列出插件直接使用的发行包，例如：

```python
"requirements": ["httpx>=0.28,<1"]
```

系统启用时先检查、安装依赖，再导入插件。不要只附带一个 `requirements.txt` 就认为会自动安装，也不要在 `setup()` 中自行执行 pip。

标准库不用声明。发行包名和导入名可能不同；extras 也可能需要显式补齐附加包。系统依赖目录是共享的，不是插件独立虚拟环境，不能强制降级核心库或删除公共依赖来解决自己的问题。

包在 x86_64 可用，不代表 ARM64 和当前 Python 版本也有可用 wheel；有原生扩展的包要分别验证。详见[依赖声明与安装](https://github.com/AWdress/AWBotNest/blob/v2/docs/PLUGIN_GUIDE.md#python-依赖声明与安装)。

## 8. 发布到插件市场

当前仓库界面接受名为 `AWBotNest-Plugins` 的公开 GitHub 仓库，V2 清单放在仓库根目录的 `manifest_v2.json`。

上面入门插件对应的最小清单：

```json
{
  "plugins": {
    "hello_demo": {
      "name": "入门示例",
      "version": "1.0.0",
      "author": "你的作者名",
      "description": "在配置页点击按钮，向插件日志写入一条消息。",
      "scope": "standalone",
      "path": "hello_demo.py"
    }
  }
}
```

仓库中的文件路径、插件 ID、版本和作用域必须相互一致。发布更新时，清单和入口元数据一起改版本；只换文件、不改版本，管理员可能看不到更新提示。

目录插件和 Vue 资源的发布方式，请按[市场发布规范](https://github.com/AWdress/AWBotNest/blob/v2/docs/PLUGIN_GUIDE.md#发布到插件市场)组织。测试文件、真实 Key、Cookie、Session、日志和个人配置不要放入插件发布包。

## 9. 发布前最低检查清单

- 在干净环境首次安装、配置、启用成功，已有依赖时不会重复无意义安装。
- 停用再启用、重载后，没有重复消息处理器、任务或未关闭浏览器。
- 没有 Telegram 账号的 `standalone` 模式也能使用声明的独立功能。
- 无配置、错误配置、网络断开、接口限流、超时和用户取消都有合理结果。
- 手机配置页能滚动，输入框、下拉选项、确认按钮和关闭按钮不被遮挡。
- 敏感值按 schema 声明，不进入日志、通知、异常正文或公开响应。
- Windows/Linux 路径用 `pathlib`，涉及原生依赖时验证 amd64/arm64。
- 不导入其他插件内部对象，不擅自修改系统配置，不在公开 Webhook 中省略鉴权。
- 发布包不含开发账号、测试数据、密钥或会话文件。

遇到系统接口行为与文档不一致时，报告系统版本、最小复现代码和脱敏日志。不要让管理员为了让插件工作而把所有权限、全部密钥或整个配置目录发给你。

返回：[Wiki 首页](Home) · [插件管理](Plugins) · [常见问题](Troubleshooting)
