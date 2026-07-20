# =============================================================================
# 多站点转账 - 排行榜/致谢渲染（严格对齐原项目 AWBotHub）
#
# 原项目对应实现：
#   - 致谢文案 + 组合通知：core/services/transfer_service.py::_send_combined_notification
#   - 排行榜图片：adapters/leaderboard/imgkit_adapter.py（wkhtmltoimage 渲染 HTML）
#   - 图片生成失败时的「精修版文字排行榜」：同上 _send_combined_notification 里的兜底分支
#
# 出图两档，自动择优、逐级回退，全程不抛错：
#   1) imgkit + wkhtmltoimage（系统装了才用，直接复刻原项目 HTML 模板，样式 1:1）
#   2) Pillow/PIL 纯 Python 绘制（平台 venv 自带 PIL，无系统二进制；尽量还原 HTML 版式）
#   文字兜底（render_text_fallback）永远可用。
#
# 不 import pyrogram / core / config。
# =============================================================================

import html
import os
import shutil
import uuid


# ─── 文本格式化小工具 ─────────────────────────────────────────────────────────
def _html_escape(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _short_name(value, limit: int = 12) -> str:
    """限制用户名展示长度；完整名称仍保留在记录中用于聚合。"""
    name = str(value or "").strip() or "未知用户"
    return name if len(name) <= limit else name[:limit] + "..."


def _fmt_amount(v) -> str:
    """本次金额：带千分位（对齐原项目 f"{abs(amount):,}"）。整数不带小数。"""
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}"
    return f"{v:,.1f}"


def _fmt_plain(v) -> str:
    """累计金额：不带千分位（对齐原项目 f"{sum_total}"）。整数不带小数。"""
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}"


def _mask_uid(uid) -> str:
    """脱敏 TG id：对齐原项目 _mask_tgid —— 长度>4 时取 s[:2]+****+s[-2:]。"""
    s = str(uid)
    if not s or s == "0":
        return ""
    if len(s) <= 4:
        return s
    return s[:2] + "****" + s[-2:]


def _user_link(user_id, user_name) -> str:
    """对齐原项目 others.build_user_html_link。user_id 无效时退纯文本名字。"""
    name = _html_escape(_short_name(user_name))
    if user_id and str(user_id) != "0":
        return f'<a href="tg://user?id={user_id}">{name}</a>'
    return name


# ─── 单笔转账致谢文案（对齐 transfer_service._send_combined_notification 的 text）──
def render_user_summary(stat: dict, bonus_name: str, direction: str,
                        user_name: str, amount: float, user_id=0) -> str:
    """单笔转账后的致谢 + 个人累计（HTML）。direction: 'in'=打赏 / 'out'=赏赐。"""
    title = "打赏" if direction == "in" else "赏赐"
    link = _user_link(user_id, user_name)
    amt = _fmt_amount(abs(amount))
    total = _fmt_plain(stat.get("total", 0))
    count = stat.get("count", 0)
    rank = stat.get("rank", -1)
    rank_str = f"第 {rank} 名" if isinstance(rank, int) and rank > 0 else "—"

    if direction == "in":
        head = (f"👤 {link} 大佬，感谢打赏！\n"
                f"💰 本次收到：<b>{amt} {bonus_name}</b>")
    else:
        head = (f"👤 {link}\n"
                f"🎁 这是赏赐你的 <b>{amt} {bonus_name}</b>，拿去花！")
    tail = (f"📊 累计{title}：{count} 次，共 {total} {bonus_name}\n"
            f"🏆 {title}总榜：{rank_str}")
    return f"{head}\n<blockquote>{tail}</blockquote>"


def render_extra(owner_name: str, direction: str, n: int) -> str:
    """图片版致谢的附注行（斜体），对齐原项目 extra。带前导换行，直接拼在正文后。"""
    title = "打赏" if direction == "in" else "赏赐"
    owner = _html_escape(owner_name)
    return f"\n<i>✨ 当前 {owner} 个人{title}总榜 TOP{n} 如图所示</i>"


# ─── 精修版文字排行榜（图片生成失败时兜底，对齐原项目文字分支）────────────────
def render_text_fallback(entries: list[dict], owner_name: str,
                         direction: str, bonus_name: str) -> str:
    """图片不可用时的文字排行榜（不含 <blockquote>，调用方负责包裹）。"""
    title = "打赏" if direction == "in" else "赏赐"
    owner = owner_name or ""
    header = f"🌟 {owner} 的{title}数据终端 🌟"
    subtitle = f">>> TOP{len(entries)} 排行榜 <<<"
    border = "━" * 25
    lines = [border, header.center(22), subtitle.center(22), border]

    medals = ["🥇", "🥈", "🥉"]
    for i, e in enumerate(entries):
        medal = medals[i] if i < 3 else f"{i + 1:2d}."
        amt_str = f"{float(e['total']):,.1f}".rjust(10)
        display_name = _short_name(e.get("user_name"), 10).ljust(10)
        lines.append(f"{medal} {_html_escape(display_name)} {amt_str} {bonus_name}")

    lines.append(border)
    lines.append(f"💡 {render_extra(owner, direction, len(entries)).strip()}")
    return "\n".join(lines)


# ─── 命令 .转账排行 用的纯文本榜（保留既有形态）──────────────────────────────
def render_text(entries: list[dict], site_name: str, bonus_name: str,
                direction: str, owner_name: str = "") -> str:
    title_word = "打赏" if direction == "in" else "赏赐"
    head = f"{site_name} {title_word}总榜 TOP{len(entries)}"
    if owner_name:
        head = f"{owner_name} · {site_name} {title_word}总榜 TOP{len(entries)}"
    if not entries:
        return f"{head}\n\n暂无数据。"
    medals = ["🥇", "🥈", "🥉"]
    lines = [head, ""]
    for e in entries:
        rank = e["rank"]
        medal = medals[rank - 1] if rank <= 3 else f"{rank:>2}."
        name = _short_name(e["user_name"], 10)
        amt = _fmt_amount(e["total"])
        lines.append(f"{medal} {name}  {amt} {bonus_name}（{e['count']}次）")
    return "\n".join(lines)


# ─── 出图能力探测 ─────────────────────────────────────────────────────────────
def _imgkit_available() -> bool:
    try:
        import imgkit  # noqa: F401
    except Exception:
        return False
    return shutil.which("wkhtmltoimage") is not None


def _pil_available() -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    except Exception:
        return False
    return True


def image_available() -> bool:
    return _imgkit_available() or _pil_available()


def render_image(entries: list[dict], site_name: str, bonus_name: str,
                 direction: str, owner_name: str, out_dir) -> str | None:
    """渲染 PNG 排行榜，返回文件路径；不可用/失败返回 None（调用方回退文本）。

    优先 imgkit（HTML 渲染，与原项目 1:1），不可用时退 PIL 纯 Python 绘制。
    """
    if not entries:
        return None
    if _imgkit_available():
        path = _render_image_imgkit(entries, site_name, bonus_name,
                                    direction, owner_name, out_dir)
        if path:
            return path
    if _pil_available():
        return _render_image_pil(entries, site_name, bonus_name,
                                 direction, owner_name, out_dir)
    return None


# ─── imgkit / wkhtmltoimage 路径：直接复刻原项目 HTML 模板 ─────────────────────
def _render_image_imgkit(entries: list[dict], site_name: str, bonus_name: str,
                         direction: str, owner_name: str, out_dir) -> str | None:
    try:
        import imgkit

        title = "打赏" if direction == "in" else "赏赐"
        rows = ""
        for e in entries:
            rank = e["rank"]
            rank_row_class = f"rank-{rank}" if rank <= 3 else "rank-normal"
            display_uid = _mask_uid(e["user_id"])
            display_name = str(e.get("user_name") or "")
            if not display_name or display_name.lower() in ("untitled", "none", "null"):
                display_name = f"用户{display_uid}" if display_uid else "未知用户"
            display_name = _short_name(display_name)
            rows += f"""
            <tr class="{rank_row_class}">
                <td class="rank-cell"><span class="rank-num">{rank}</span></td>
                <td class="username-cell">
                    <span class="username">{_html_escape(display_name)}</span>
                    <small class="userid">{display_uid}</small>
                </td>
                <td class="count-cell"><span class="count">{e['count']} 次</span></td>
                <td class="amount-cell"><span class="amount">{float(e['total']):,.1f}</span></td>
            </tr>
            """

        html_str = _html_template(site_name.upper(), title, bonus_name, rows,
                                  owner_name, len(entries))

        out_dir = str(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        uid = uuid.uuid4().hex
        html_path = os.path.join(out_dir, f"_lb_{uid}.html")
        img_path = os.path.join(out_dir, f"_lb_{uid}.png")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_str)
        options = {
            "format": "png", "encoding": "UTF-8", "quiet": "",
            "width": "500", "enable-local-file-access": "",
        }
        try:
            imgkit.from_file(html_path, img_path, options=options)
        finally:
            if os.path.exists(html_path):
                os.unlink(html_path)
        return img_path if os.path.exists(img_path) else None
    except Exception:
        return None


def _html_template(site: str, title: str, bonus_name: str, rows: str,
                   owner_name: str, count: int) -> str:
    display_name = _html_escape(owner_name or "")
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                background: #f0f2f5; margin: 0; padding: 10px;
                font-family: "Helvetica Neue", Helvetica, Arial, "Microsoft YaHei", sans-serif;
                width: 480px;
            }}
            .card {{
                background: white; border-radius: 12px; border: 1px solid #e1e4e8;
                overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }}
            .header {{
                background: #1a2a6c;
                background: linear-gradient(to right, #1a2a6c, #b21f1f, #fdbb2d);
                padding: 18px 10px; text-align: center; color: white;
            }}
            .title {{ font-size: 20px; font-weight: bold; margin-bottom: 4px; text-shadow: 1px 1px 2px rgba(0,0,0,0.3); }}
            .subtitle {{ font-size: 13px; opacity: 0.9; letter-spacing: 1px; }}
            table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
            th {{
                background: #f8f9fa; color: #586069; font-size: 12px;
                padding: 12px 10px; text-align: left; border-bottom: 2px solid #e1e4e8;
            }}
            tbody tr:nth-child(even) {{ background-color: #f9fbfd; }}
            td {{
                padding: 12px 10px; border-bottom: 1px solid #f1f1f1; color: #24292e;
                vertical-align: middle; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
            }}
            .rank-cell {{ width: 50px; text-align: center; }}
            .username-cell {{ width: 180px; }}
            .count-cell {{ width: 80px; text-align: center; }}
            .amount-cell {{ width: 120px; text-align: right; }}
            .rank-num {{
                display: inline-block; width: 28px; height: 28px; line-height: 28px;
                text-align: center; background: #f1f3f5; color: #495057;
                border-radius: 50%; font-weight: bold; font-size: 14px;
            }}
            .rank-1 .rank-num {{ background: #FFD700; color: #856404; box-shadow: 0 0 5px rgba(255,215,0,0.4); }}
            .rank-2 .rank-num {{ background: #C0C0C0; color: #383d41; }}
            .rank-3 .rank-num {{ background: #CD7F32; color: #ffffff; }}
            .username {{
                font-weight: bold; font-size: 15px; color: #0366d6; display: block;
                width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
            }}
            .userid {{ font-weight: normal; color: #6a737d; font-size: 11px; }}
            .count {{ font-size: 13px; color: #28a745; font-weight: bold; }}
            .amount {{ color: #d73a49; font-weight: bold; font-size: 16px; font-family: "Courier New", Courier, monospace; }}
            .footer {{
                padding: 12px; background: #f8f9fa; text-align: center;
                font-size: 11px; color: #6a737d; border-top: 1px solid #e1e4e8;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <div class="title">{display_name} 的数据终端</div>
                <div class="subtitle">>>> {site} {title}排行榜 TOP {count} <<<</div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th class="rank-cell">排名</th>
                        <th>用户信息</th>
                        <th style="text-align:center;">次数</th>
                        <th style="text-align:right;">{bonus_name}累计</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
            <div class="footer">
                数据实时同步更新 · 祝您好运连连 ☘️
            </div>
        </div>
    </body>
    </html>
    """


# ─── PIL 纯 Python 出图：尽量还原原项目 HTML 版式（无系统二进制/emoji 依赖）────
_FONT_REG = [
    r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_FONT_BOLD = [
    r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# 配色（取自原项目 HTML）
_C_PAGE = (240, 242, 245)      # #f0f2f5
_C_CARD = (255, 255, 255)
_C_GRAD = [(26, 42, 108), (178, 31, 31), (253, 187, 45)]  # #1a2a6c → #b21f1f → #fdbb2d
_C_TH_BG = (248, 249, 250)     # #f8f9fa
_C_TH_TX = (88, 96, 105)       # #586069
_C_ZEBRA = (249, 251, 253)     # #f9fbfd
_C_TD = (36, 41, 46)           # #24292e
_C_LINE = (241, 241, 241)      # #f1f1f1
_C_BORDER = (225, 228, 232)    # #e1e4e8
_C_NAME = (3, 102, 214)        # #0366d6
_C_UID = (106, 115, 125)       # #6a737d
_C_COUNT = (40, 167, 69)       # #28a745
_C_AMOUNT = (215, 58, 73)      # #d73a49
_C_RANKN_BG = (241, 243, 245)  # #f1f3f5
_C_RANKN_TX = (73, 80, 87)     # #495057
_C_MEDAL = [((255, 215, 0), (133, 100, 4)),     # 金 #FFD700 / #856404
            ((192, 192, 192), (56, 61, 65)),    # 银 #C0C0C0 / #383d41
            ((205, 127, 50), (255, 255, 255))]  # 铜 #CD7F32 / #fff


def _font(paths, size):
    from PIL import ImageFont
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _tw(draw, text, font) -> float:
    try:
        return draw.textlength(text, font=font)
    except Exception:
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        return r - l


def _grad_color(t: float):
    """t∈[0,1] 在三段色标上插值，复刻 header 的 linear-gradient。"""
    if t <= 0.5:
        a, b, k = _C_GRAD[0], _C_GRAD[1], t / 0.5
    else:
        a, b, k = _C_GRAD[1], _C_GRAD[2], (t - 0.5) / 0.5
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def _render_image_pil(entries: list[dict], site_name: str, bonus_name: str,
                      direction: str, owner_name: str, out_dir) -> str | None:
    try:
        from PIL import Image, ImageDraw

        title = "打赏" if direction == "in" else "赏赐"
        owner = owner_name or ""
        n = len(entries)

        # 版式（对齐 HTML：卡片宽 ~480，四列 排名/用户信息/次数/累计）
        PAD = 14
        CARD_W = 468
        COL = [58, 210, 78, 122]         # 排名 / 用户信息 / 次数 / 累计 = 468
        HEADER_H = 76
        THEAD_H = 40
        ROW_H = 52
        FOOTER_H = 40
        card_h = HEADER_H + THEAD_H + n * ROW_H + FOOTER_H
        W = CARD_W + PAD * 2
        H = card_h + PAD * 2

        f_title = _font(_FONT_BOLD, 22)
        f_sub = _font(_FONT_REG, 13)
        f_th = _font(_FONT_REG, 13)
        f_name = _font(_FONT_BOLD, 16)
        f_uid = _font(_FONT_REG, 11)
        f_count = _font(_FONT_BOLD, 14)
        f_amt = _font(_FONT_BOLD, 17)
        f_rank = _font(_FONT_BOLD, 14)
        f_foot = _font(_FONT_REG, 11)

        R = 12
        img = Image.new("RGB", (W, H), _C_PAGE)
        d = ImageDraw.Draw(img)

        x0, y0 = PAD, PAD
        x1, y1 = PAD + CARD_W, PAD + card_h
        # 白卡 + 圆角
        d.rounded_rectangle([x0, y0, x1, y1], radius=R, fill=_C_CARD,
                            outline=_C_BORDER, width=1)

        # —— 渐变 header（独立图层 + 仅上圆角遮罩后贴入，保证圆角干净）——
        band = Image.new("RGB", (CARD_W, HEADER_H))
        bd = ImageDraw.Draw(band)
        for i in range(CARD_W):
            bd.line([(i, 0), (i, HEADER_H)], fill=_grad_color(i / max(CARD_W - 1, 1)))
        hmask = Image.new("L", (CARD_W, HEADER_H), 0)
        hmd = ImageDraw.Draw(hmask)
        hmd.rounded_rectangle([0, 0, CARD_W - 1, HEADER_H - 1], radius=R, fill=255)
        hmd.rectangle([0, HEADER_H - R, CARD_W - 1, HEADER_H - 1], fill=255)  # 下沿改方角
        img.paste(band, (x0, y0), hmask)

        cx = (x0 + x1) / 2
        t_title = f"{owner} 的数据终端".strip()
        tw = _tw(d, t_title, f_title)
        d.text((cx - tw / 2, y0 + 18), t_title, font=f_title, fill=(255, 255, 255))
        t_sub = f">>> {site_name.upper()} {title}排行榜 TOP {n} <<<"
        sw = _tw(d, t_sub, f_sub)
        d.text((cx - sw / 2, y0 + 48), t_sub, font=f_sub, fill=(255, 255, 255))

        # —— 表头 ——
        ty = y0 + HEADER_H
        d.rectangle([x0, ty, x1, ty + THEAD_H], fill=_C_TH_BG)
        d.line([x0, ty + THEAD_H, x1, ty + THEAD_H], fill=_C_BORDER, width=2)
        heads = ["排名", "用户信息", "次数", f"{bonus_name}累计"]
        aligns = ["c", "l", "c", "r"]
        _row_cells(d, x0, ty, THEAD_H, COL, heads, aligns, f_th, _C_TH_TX)

        # —— 数据行 ——
        ry = ty + THEAD_H
        for idx, e in enumerate(entries):
            rank = e["rank"]
            if idx % 2 == 1:  # 斑马纹（偶数行，0-based 奇数）
                d.rectangle([x0, ry, x1, ry + ROW_H], fill=_C_ZEBRA)

            # 列1：名次圆
            _draw_rank(d, x0, ry, COL[0], ROW_H, rank, f_rank)

            # 列2：用户名 + 脱敏 id（两行）
            ux = x0 + COL[0] + 12
            name = str(e.get("user_name") or "")
            if not name or name.lower() in ("untitled", "none", "null"):
                name = f"用户{_mask_uid(e['user_id'])}" or "未知用户"
            name = _short_name(name)
            uid = _mask_uid(e["user_id"])
            if uid:
                d.text((ux, ry + 9), name, font=f_name, fill=_C_NAME)
                d.text((ux, ry + 30), uid, font=f_uid, fill=_C_UID)
            else:
                d.text((ux, ry + (ROW_H - 16) / 2), name, font=f_name, fill=_C_NAME)

            # 列3：次数（居中）
            c3x = x0 + COL[0] + COL[1]
            ct = f"{e['count']} 次"
            cw = _tw(d, ct, f_count)
            d.text((c3x + (COL[2] - cw) / 2, ry + (ROW_H - 16) / 2),
                   ct, font=f_count, fill=_C_COUNT)

            # 列4：金额（右对齐）
            c4x = x0 + COL[0] + COL[1] + COL[2]
            at = f"{float(e['total']):,.1f}"
            aw = _tw(d, at, f_amt)
            d.text((c4x + COL[3] - aw - 12, ry + (ROW_H - 17) / 2),
                   at, font=f_amt, fill=_C_AMOUNT)

            d.line([x0, ry + ROW_H, x1, ry + ROW_H], fill=_C_LINE, width=1)
            ry += ROW_H

        # —— footer（独立图层 + 仅下圆角遮罩后贴入）——
        fy = ry
        foot_band = Image.new("RGB", (CARD_W, FOOTER_H), _C_TH_BG)
        fmask = Image.new("L", (CARD_W, FOOTER_H), 0)
        fmd = ImageDraw.Draw(fmask)
        fmd.rounded_rectangle([0, 0, CARD_W - 1, FOOTER_H - 1], radius=R, fill=255)
        fmd.rectangle([0, 0, CARD_W - 1, R], fill=255)  # 上沿改方角
        img.paste(foot_band, (x0, fy), fmask)
        foot = "数据实时同步更新 · 祝您好运连连"
        fw = _tw(d, foot, f_foot)
        d.text((cx - fw / 2, fy + (FOOTER_H - 14) / 2), foot, font=f_foot, fill=_C_UID)

        out_dir = str(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        img_path = os.path.join(out_dir, f"_lb_{uuid.uuid4().hex}.png")
        img.save(img_path, "PNG")
        return img_path if os.path.exists(img_path) else None
    except Exception:
        return None


def _row_cells(d, x0, y, h, col, values, aligns, font, fill):
    x = x0
    for i, val in enumerate(values):
        w = _tw(d, val, font)
        cy = y + (h - 16) / 2
        if aligns[i] == "c":
            d.text((x + (col[i] - w) / 2, cy), val, font=font, fill=fill)
        elif aligns[i] == "r":
            d.text((x + col[i] - w - 12, cy), val, font=font, fill=fill)
        else:
            d.text((x + 12, cy), val, font=font, fill=fill)
        x += col[i]


def _draw_rank(d, x, y, cw, row_h, rank: int, font):
    """名次：前三名金/银/铜圆，其余灰圆，圆内白/深字。"""
    rr = 14
    cxm = x + cw / 2
    cym = y + row_h / 2
    if rank <= 3:
        bg, tx = _C_MEDAL[rank - 1]
    else:
        bg, tx = _C_RANKN_BG, _C_RANKN_TX
    d.ellipse([cxm - rr, cym - rr, cxm + rr, cym + rr], fill=bg)
    s = str(rank)
    w = _tw(d, s, font)
    d.text((cxm - w / 2, cym - 9), s, font=font, fill=tx)
