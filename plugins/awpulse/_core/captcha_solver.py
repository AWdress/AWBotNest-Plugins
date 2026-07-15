# -*- coding: utf-8 -*-
"""
验证码识别模块 —— 本地多算法融合方案
滑块/拼图: ddddocr.slide_match + OpenCV Canny 边缘模板匹配
点选文字: ddddocr 目标检测 + OCR 分类
旋转验证码: 径向能量 + 环带方差对齐
滑动轨迹: 贝塞尔三阶段 + 高斯抖动 + 微回拉
"""

import math
import random
import re
import time
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

try:
    import ddddocr
except Exception:
    ddddocr = None


def cleanup_debug_files(debug_dir, patterns, keep=3):
    if not debug_dir:
        return
    try:
        for pattern in patterns:
            files = sorted(
                Path(debug_dir).glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for f in files[keep:]:
                try:
                    f.unlink()
                except OSError:
                    pass
    except Exception:
        pass


def _bezier_curve(p0, p1, p2, p3, steps):
    points = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def generate_slide_track(distance):
    """贝塞尔三阶段轨迹: 加速 匀速 减速 + 高斯抖动 + 微回拉"""
    distance = int(round(distance))
    if distance <= 0:
        return [{'x': 0, 'y': 0, 't': 20}]

    mid1 = distance * random.uniform(0.55, 0.7)
    mid2 = distance * random.uniform(0.85, 0.95)
    overshoot = distance + random.uniform(2, 5)

    p0 = (0, 0)
    p1 = (mid1 * 0.4, random.uniform(-3, 3))
    p2 = (mid2, random.uniform(-2, 2))
    p3 = (overshoot, random.uniform(-1, 1))

    num_steps = max(20, int(distance / 6))
    raw_points = _bezier_curve(p0, p1, p2, p3, num_steps)

    track = []
    for i, (bx, by) in enumerate(raw_points[1:], 1):
        progress = i / num_steps
        jitter_y = random.gauss(0, 1.2)
        if progress < 0.3:
            dt = random.randint(12, 20)
        elif progress < 0.7:
            dt = random.randint(8, 14)
        else:
            dt = random.randint(18, 32)
        track.append({'x': bx, 'y': by + jitter_y, 't': dt})

    pullback = distance - random.uniform(1, 4)
    track.append({'x': pullback, 'y': random.gauss(0, 0.5), 't': random.randint(30, 50)})
    track.append({'x': float(distance), 'y': random.gauss(0, 0.3), 't': random.randint(20, 35)})
    return track


# ---------------------------------------------------------------------------
# CaptchaSolver
# ---------------------------------------------------------------------------

class CaptchaSolver:
    """本地验证码识别器: ddddocr + OpenCV 多算法融合"""

    def __init__(self, config=None):
        self.config = config or {}
        self._ocr = None

    def _init_ddddocr(self):
        if self._ocr is not None:
            return
        if ddddocr is None:
            raise RuntimeError('ddddocr not installed')
        self._ocr = ddddocr.DdddOcr(det=True, ocr=True, show_ad=False)

    def is_available(self):
        try:
            self._init_ddddocr()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 验证码类型检测
    # ------------------------------------------------------------------

    def detect_captcha_type(self, page):
        try:
            if not self._is_captcha_visible(page):
                return 'none'
            time.sleep(0.5)

            has_tile = page.locator('div.gc-tile').count() > 0
            has_rotate_pic = page.locator('div.gc-rotate-picture').count() > 0
            has_rotate_thumb = page.locator('div.gc-rotate-thumb').count() > 0
            has_dots = page.locator('div.gc-dots').count() > 0
            has_word = page.locator('div.gc-word').count() > 0
            has_slidebar = page.locator('div.gc-drag-slide-bar').count() > 0
            has_button = page.locator('div.gc-button-block button').count() > 0

            # tile 优先: 有拼图块就是拼图类型, 不管有没有 gc-thumb
            if has_tile:
                if has_slidebar:
                    return 'slider'
                return 'drag_tile'
            # 旋转: 只有 div.gc-rotate-picture/thumb 才算
            if has_rotate_pic or has_rotate_thumb:
                return 'rotate'
            if has_word:
                return 'click'
            if has_dots or has_button:
                return 'icon_click'
            return 'none'
        except Exception:
            return 'none'

    def _is_captcha_visible(self, page):
        try:
            wrapper = page.locator('div.gc-wrapper')
            return wrapper.count() > 0 and wrapper.first.is_visible()
        except Exception:
            return False

    def _get_visible_text(self, page, selectors):
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    text = loc.first.inner_text().strip()
                    if text:
                        return text
            except Exception:
                continue
        return ''

    # ------------------------------------------------------------------
    # 滑块 / 拼图块验证码
    # ------------------------------------------------------------------

    def solve_slider_captcha(self, page):
        if not self.is_available():
            return False
        try:
            if page.locator('div.gc-tile').count() > 0:
                return self._solve_drag_tile(page)
            return self._solve_slider_handle(page)
        except Exception:
            return False

    def _solve_drag_tile(self, page):
        cap = self._capture_slider_images(page)
        if not cap or not cap[0] or not cap[1]:
            return False
        bg_bytes, tgt_bytes, tile_rect = cap
        gap_pos = self._detect_gap_2d(tgt_bytes, bg_bytes, tile_rect)
        if gap_pos is None:
            return False
        gap_x, gap_y = gap_pos
        has_slidebar = page.locator('div.gc-drag-slide-bar').count() > 0
        if has_slidebar:
            if not self._drag_by_displacement(page, gap_x):
                return False
        else:
            if not self._drag_tile_directly(page, gap_x, gap_y):
                return False
        return self._wait_captcha_closed(page)

    def _solve_slider_handle(self, page):
        cap = self._capture_slider_images(page)
        if not cap or not cap[0] or not cap[1]:
            return False
        bg_bytes, tgt_bytes, tile_rect = cap
        gap_pos = self._detect_gap_2d(tgt_bytes, bg_bytes, tile_rect)
        if gap_pos is None:
            return False
        gap_x, _ = gap_pos
        if not self._drag_by_displacement(page, gap_x):
            return False
        return self._wait_captcha_closed(page)

    def _wait_captcha_closed(self, page, timeout=6.0):
        """验证码真正通过的标志: wrapper 持续消失, 而不是失败后被重置成新一题
        失败时 go-captcha 会关闭旧 wrapper 短暂不可见, 然后重新显示新题
        所以需要等更久, 并要求连续多次检测都不可见才判定成功
        """
        deadline = time.time() + timeout
        consecutive_gone = 0
        required = 5  # 连续 5 次 (>= 1.5s) 都不可见才算真消失

        while time.time() < deadline:
            try:
                wrapper = page.locator('div.gc-wrapper')
                if wrapper.count() == 0:
                    consecutive_gone += 1
                else:
                    visible = False
                    try:
                        visible = wrapper.first.is_visible(timeout=200)
                    except Exception:
                        visible = False
                    if visible:
                        # wrapper 又出现了, 说明只是被重置成新一题, 不是真通过
                        return False
                    consecutive_gone += 1
                if consecutive_gone >= required:
                    return True
            except Exception:
                consecutive_gone += 1
                if consecutive_gone >= required:
                    return True
            time.sleep(0.3)
        return False

    def _capture_slider_images(self, page):
        """返回 (bg_bytes_with_tile_masked, tgt_bytes, tile_rect_in_bg_image_coords)
        bg_bytes: 原始 gc-picture 截图, mask 掉 tile 区域避免 ddddocr 把拼图块本身识别成缺口
        tgt_bytes: 拼图块独立截图
        tile_rect: tile 在 bg 图像像素坐标系下的 (x, y, w, h), 用于 mask 和位移计算
        """
        try:
            bg_loc = None
            tgt_loc = None
            for _ in range(10):
                if page.locator('img.gc-picture').count() > 0:
                    bg_loc = page.locator('img.gc-picture').first
                elif page.locator('div.gc-body img').count() > 0:
                    bg_loc = page.locator('div.gc-body img').first

                for sel in ('div.gc-tile img', '.gc-tile img', 'div.gc-tile'):
                    if page.locator(sel).count() > 0:
                        tgt_loc = page.locator(sel).first
                        break

                if bg_loc and tgt_loc:
                    break
                time.sleep(0.3)

            if not bg_loc:
                return None
            bg_bytes = bg_loc.screenshot()
            tgt_bytes = tgt_loc.screenshot() if tgt_loc else None

            tile_rect = None
            if tgt_loc:
                try:
                    bg_box = bg_loc.bounding_box()
                    tile_box = tgt_loc.bounding_box()
                    if bg_box and tile_box:
                        bg_img = Image.open(BytesIO(bg_bytes))
                        scale_x = bg_img.width / bg_box['width']
                        scale_y = bg_img.height / bg_box['height']
                        tx = (tile_box['x'] - bg_box['x']) * scale_x
                        ty = (tile_box['y'] - bg_box['y']) * scale_y
                        tw = tile_box['width'] * scale_x
                        th = tile_box['height'] * scale_y
                        tile_rect = (int(tx), int(ty), int(tw), int(th))
                except Exception:
                    tile_rect = None

            return bg_bytes, tgt_bytes, tile_rect
        except Exception:
            return None

    def _mask_tile_in_bg(self, bg_bytes, tile_rect):
        """把 bg 图像中 tile 占据的矩形用周边平均色填充, 避免被识别为缺口"""
        if not tile_rect:
            return bg_bytes
        try:
            arr = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
            if arr is None:
                return bg_bytes
            x, y, w, h = tile_rect
            x = max(0, x); y = max(0, y)
            w = min(arr.shape[1] - x, w); h = min(arr.shape[0] - y, h)
            if w <= 0 or h <= 0:
                return bg_bytes
            pad = 8
            top = max(0, y - pad); bot = min(arr.shape[0], y + h + pad)
            left = max(0, x - pad); right = min(arr.shape[1], x + w + pad)
            ring = arr[top:bot, left:right].copy()
            inner_y0 = y - top; inner_x0 = x - left
            ring[inner_y0:inner_y0 + h, inner_x0:inner_x0 + w] = 0
            mean_color = ring[ring.sum(axis=2) > 0].mean(axis=0) if (ring.sum(axis=2) > 0).any() else np.array([128, 128, 128])
            arr[y:y + h, x:x + w] = mean_color.astype(np.uint8)
            ok, buf = cv2.imencode('.png', arr)
            return buf.tobytes() if ok else bg_bytes
        except Exception:
            return bg_bytes

    def _detect_gap(self, target_bytes, background_bytes, tile_rect=None):
        """返回 gap_x (缺口左上角 x 坐标, 图像像素)"""
        pos = self._detect_gap_2d(target_bytes, background_bytes, tile_rect)
        return pos[0] if pos else None

    def _detect_gap_2d(self, target_bytes, background_bytes, tile_rect=None):
        """返回 (gap_x, gap_y) 缺口中心坐标 (图像像素)"""
        if not target_bytes:
            return None
        bg_for_match = self._mask_tile_in_bg(background_bytes, tile_rect) if tile_rect else background_bytes

        # 方法1: OpenCV Canny 边缘 + 模板匹配 (返回 x,y)
        try:
            pos = self._cv2_edge_match_2d(target_bytes, bg_for_match, tile_rect)
            if pos is not None:
                return pos
        except Exception:
            pass

        # 方法2: ddddocr slide_match (只返回 x, y 取 tile 高度中心)
        try:
            self._init_ddddocr()
            res = self._ocr.slide_match(target_bytes, bg_for_match, simple_target=True)
            if isinstance(res, dict):
                x = res.get('target_x') or (res.get('target', [None])[0])
                y = res.get('target_y') or (res.get('target', [None, None])[1] if len(res.get('target', [])) > 1 else None)
                if x is not None and x > 0:
                    cand_x = int(x)
                    if tile_rect and abs(cand_x - (tile_rect[0] + tile_rect[2] // 2)) < tile_rect[2] // 2:
                        pass
                    else:
                        tgt_arr = cv2.imdecode(np.frombuffer(target_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
                        cand_y = int(y) if y else (tile_rect[1] + tile_rect[3] // 2 if tile_rect else (tgt_arr.shape[0] // 2 if tgt_arr is not None else 0))
                        return (cand_x, cand_y)
        except Exception:
            pass

        return None

    def _cv2_edge_match_2d(self, target_bytes, background_bytes, tile_rect=None):
        """OpenCV Canny 边缘检测 + matchTemplate, 返回 (center_x, center_y)"""
        bg_arr = cv2.imdecode(np.frombuffer(background_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        tgt_arr = cv2.imdecode(np.frombuffer(target_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        if bg_arr is None or tgt_arr is None:
            return None
        tgt_h, tgt_w = tgt_arr.shape
        bg_h, bg_w = bg_arr.shape
        if tgt_h > bg_h or tgt_w > bg_w:
            return None

        bg_edge = cv2.Canny(cv2.GaussianBlur(bg_arr, (5, 5), 0), 50, 150)
        tgt_edge = cv2.Canny(cv2.GaussianBlur(tgt_arr, (5, 5), 0), 50, 150)

        if tile_rect:
            tx, ty, tw, th = tile_rect
            pad = 4
            x1 = max(0, tx - pad); y1 = max(0, ty - pad)
            x2 = min(bg_w, tx + tw + pad); y2 = min(bg_h, ty + th + pad)
            bg_edge[y1:y2, x1:x2] = 0

        result = cv2.matchTemplate(bg_edge, tgt_edge, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < 0.2:
            return None
        # 返回匹配区域的左上角 + 半个 tile 宽高 = 中心
        # go-captcha tile 的 left/top 是左上角对齐, 所以返回左上角
        return (int(max_loc[0]), int(max_loc[1]))

    def _drag_by_displacement(self, page, gap_x):
        try:
            tile_loc = page.locator('div.gc-tile').first
            if tile_loc.count() == 0:
                return False
            tile_box = tile_loc.bounding_box()
            bg_loc = page.locator('img.gc-picture').first
            bg_box = bg_loc.bounding_box()
            if not tile_box or not bg_box:
                return False
            bg_img = Image.open(BytesIO(bg_loc.screenshot()))
            scale_x = bg_box['width'] / bg_img.width
            # gap_x 是缺口左上角 x (图像像素), 转为屏幕坐标
            gap_screen_x = bg_box['x'] + gap_x * scale_x
            # tile 当前左上角屏幕坐标
            tile_screen_x = tile_box['x']
            displacement = gap_screen_x - tile_screen_x

            handle = page.locator('div.gc-drag-block').first
            handle_box = handle.bounding_box()
            if not handle_box:
                return False
            start_x = handle_box['x'] + handle_box['width'] / 2
            start_y = handle_box['y'] + handle_box['height'] / 2
            return self._drag_by_track(page, start_x, start_y, start_x + displacement, start_y)
        except Exception:
            return False

    def _drag_tile_directly(self, page, gap_x, gap_y):
        """直接拖拽 gc-tile 到缺口位置 (无底部滑块的拼图类型)"""
        try:
            tile_loc = page.locator('div.gc-tile').first
            if tile_loc.count() == 0:
                return False
            tile_box = tile_loc.bounding_box()
            bg_loc = page.locator('img.gc-picture').first
            bg_box = bg_loc.bounding_box()
            if not tile_box or not bg_box:
                return False
            bg_img = Image.open(BytesIO(bg_loc.screenshot()))
            scale_x = bg_box['width'] / bg_img.width
            scale_y = bg_box['height'] / bg_img.height

            # gap_x/gap_y 是缺口左上角 (图像像素), 转为屏幕坐标
            target_x = bg_box['x'] + gap_x * scale_x + tile_box['width'] / 2
            target_y = bg_box['y'] + gap_y * scale_y + tile_box['height'] / 2

            # tile 当前中心
            start_x = tile_box['x'] + tile_box['width'] / 2
            start_y = tile_box['y'] + tile_box['height'] / 2

            return self._drag_by_track_2d(page, start_x, start_y, target_x, target_y)
        except Exception:
            return False

    def _drag_by_track_2d(self, page, start_x, start_y, end_x, end_y):
        """2D 拖拽: 同时有 x 和 y 方向位移"""
        page.mouse.move(start_x, start_y)
        time.sleep(random.uniform(0.08, 0.16))
        page.mouse.down()

        dx = end_x - start_x
        dy = end_y - start_y
        num_steps = max(15, int(abs(dx) / 8))
        for i in range(1, num_steps + 1):
            progress = i / num_steps
            # ease-in-out
            t = progress * progress * (3 - 2 * progress)
            cx = start_x + dx * t + random.gauss(0, 0.8)
            cy = start_y + dy * t + random.gauss(0, 0.8)
            page.mouse.move(cx, cy, steps=2)
            time.sleep(random.uniform(0.01, 0.025))

        page.mouse.move(end_x, end_y, steps=3)
        time.sleep(random.uniform(0.05, 0.1))
        page.mouse.up()
        time.sleep(random.uniform(0.3, 0.6))
        return True

    # ------------------------------------------------------------------
    # 图标点选验证码 (gc-dots, 按 header 提示顺序点击大图中的图标)
    # ------------------------------------------------------------------

    def solve_icon_click_captcha(self, page):
        if not self.is_available():
            return False
        try:
            bg_loc = page.locator('img.gc-picture').first
            if bg_loc.count() == 0:
                return False
            bg_box = bg_loc.bounding_box()
            bg_bytes = bg_loc.screenshot()
            if not bg_box or not bg_bytes:
                return False

            header_img_loc = page.locator('div.gc-header img').first
            if header_img_loc.count() == 0:
                return False
            header_bytes = header_img_loc.screenshot()
            if not header_bytes:
                return False

            boxes = self._ocr.detection(bg_bytes)
            if not boxes or len(boxes) < 2:
                return False

            templates = self._split_header_icons(header_bytes)
            if not templates:
                return False

            bg_img = Image.open(BytesIO(bg_bytes))
            candidates = []
            for box in boxes:
                x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
                if x2 - x1 < 8 or y2 - y1 < 8:
                    continue
                crop = bg_img.crop((x1, y1, x2, y2)).convert('L')
                crop_arr = cv2.resize(np.asarray(crop), (40, 40))
                candidates.append({
                    'cx': (x1 + x2) // 2,
                    'cy': (y1 + y2) // 2,
                    'feat': crop_arr,
                })
            if len(candidates) < len(templates):
                return False

            scale_x = bg_box['width'] / bg_img.width
            scale_y = bg_box['height'] / bg_img.height
            used = set()
            click_positions = []
            for tpl in templates:
                best_idx, best_score = -1, -1.0
                for i, cand in enumerate(candidates):
                    if i in used:
                        continue
                    score = self._template_similarity(tpl, cand['feat'])
                    if score > best_score:
                        best_score = score
                        best_idx = i
                if best_idx < 0:
                    return False
                used.add(best_idx)
                cand = candidates[best_idx]
                px = bg_box['x'] + cand['cx'] * scale_x
                py = bg_box['y'] + cand['cy'] * scale_y
                click_positions.append((px, py))

            for px, py in click_positions:
                page.mouse.click(px, py)
                time.sleep(random.uniform(0.25, 0.45))

            confirm = page.locator('div.gc-button-block button').first
            if confirm.count() > 0:
                time.sleep(random.uniform(0.2, 0.4))
                confirm.click()
            return self._wait_captcha_closed(page)
        except Exception:
            return False

    def _split_header_icons(self, header_bytes):
        """提示图横向均分: 检测非空白列, 按等距切成 N 个图标"""
        arr = cv2.imdecode(np.frombuffer(header_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        if arr is None:
            return []
        h = arr.shape[0]
        # 列方差: 找有内容的列范围
        col_std = arr.std(axis=0)
        active_cols = np.where(col_std > 5)[0]
        if len(active_cols) < 4:
            return []
        left, right = int(active_cols[0]), int(active_cols[-1]) + 1

        # 估算图标个数: 约高度的整数倍
        approx_count = max(2, min(6, round((right - left) / max(1, h))))
        seg_w = (right - left) // approx_count
        templates = []
        for i in range(approx_count):
            x1 = left + i * seg_w
            x2 = left + (i + 1) * seg_w if i < approx_count - 1 else right
            crop = arr[:, x1:x2]
            # 去除上下空白
            row_std = crop.std(axis=1)
            active_rows = np.where(row_std > 5)[0]
            if len(active_rows) > 2:
                top, bot = int(active_rows[0]), int(active_rows[-1]) + 1
                crop = crop[top:bot, :]
            if crop.size == 0:
                continue
            templates.append(cv2.resize(crop, (40, 40)))
        return templates

    def _template_similarity(self, tpl, feat):
        """归一化互相关相似度"""
        a = tpl.astype(np.float32) - tpl.mean()
        b = feat.astype(np.float32) - feat.mean()
        denom = (a.std() * b.std() * a.size) + 1e-6
        return float((a * b).sum() / denom)

    # ------------------------------------------------------------------
    # 点选文字验证码
    # ------------------------------------------------------------------

    def solve_click_captcha(self, page):
        if not self.is_available():
            return False
        try:
            # 只对 gc-picture 区域做检测, 避免 header/footer 干扰
            bg_loc = page.locator('img.gc-picture').first
            if bg_loc.count() == 0:
                bg_loc = page.locator('div.gc-body img').first
            if bg_loc.count() == 0:
                return False
            bg_bytes = bg_loc.screenshot()
            bg_box = bg_loc.bounding_box()
            if not bg_bytes or not bg_box:
                return False

            boxes = self._ocr.detection(bg_bytes)
            if not boxes:
                return False

            hint = self._extract_click_hint(page)
            words = self._normalize_words(hint)

            bg_img = Image.open(BytesIO(bg_bytes))
            candidates = []
            for box in boxes:
                x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
                if x2 - x1 < 8 or y2 - y1 < 8:
                    continue
                crop = bg_img.crop((x1, y1, x2, y2))
                buf = BytesIO()
                crop.save(buf, format='PNG')
                text = self._ocr.classification(buf.getvalue()).strip()
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                candidates.append((cx, cy, text))

            # 按提示词匹配顺序点击
            selected = []
            if words:
                for w in words:
                    for cx, cy, t in candidates:
                        if w in t and (cx, cy) not in selected:
                            selected.append((cx, cy))
                            break
            if not selected:
                selected = [(cx, cy) for cx, cy, t in candidates if t and len(t) <= 4]
            if not selected:
                return False

            # 转换为屏幕坐标并点击
            scale_x = bg_box['width'] / bg_img.width
            scale_y = bg_box['height'] / bg_img.height
            for cx, cy in selected:
                page.mouse.click(bg_box['x'] + cx * scale_x, bg_box['y'] + cy * scale_y)
                time.sleep(random.uniform(0.25, 0.45))

            # 点确认按钮
            confirm = page.locator('div.gc-button-block button').first
            if confirm.count() > 0:
                time.sleep(random.uniform(0.2, 0.4))
                confirm.click()

            return self._wait_captcha_closed(page)
        except Exception:
            return False

    def _extract_click_hint(self, page):
        hint = self._get_visible_text(page, [
            'div.gc-tips', 'div.gc-head', 'div.gc-body',
            'div.gc-header', 'div.gc-word', 'div.gc-info',
        ])
        return re.sub(r'\s+', ' ', hint).strip() if hint else ''

    def _normalize_words(self, hint):
        if not hint:
            return []
        text = hint.replace('请选择', ' ').replace('点击', ' ').replace('Tap', ' ').replace('Please', ' ')
        text = re.sub(r'[：:，,。\s]+', ' ', text)
        return [w for w in text.split() if len(w) >= 1]

    # ------------------------------------------------------------------
    # 旋转验证码 —— 内/外圈环带相关性最大化
    # ------------------------------------------------------------------

    def solve_rotate_captcha(self, page):
        if not self.is_available():
            return False
        try:
            outer_bytes = self._capture_element_bytes(page, 'div.gc-rotate-picture img, div.gc-rotate-picture, img.gc-picture')
            inner_bytes = self._capture_element_bytes(page, 'div.gc-rotate-thumb img, div.gc-rotate-thumb, img.gc-thumb')
            angle = None
            if outer_bytes and inner_bytes:
                angle = self._estimate_align_angle(outer_bytes, inner_bytes)
            if angle is None:
                text_angle = self._extract_rotation_angle_from_text(page)
                if text_angle is not None:
                    angle = text_angle
            if angle is None:
                return False
            if not self._drag_rotation_slider(page, angle):
                return False
            return self._wait_captcha_closed(page)
        except Exception:
            return False

    def _extract_rotation_angle_from_text(self, page):
        raw = self._get_visible_text(page, [
            'div.gc-body', 'div.gc-header', 'div.gc-tips', 'div.gc-wrapper',
        ])
        if not raw:
            return None
        m = re.search(r'(\d{1,3})\s*[°度]', raw)
        return int(m.group(1)) if m else None

    def _estimate_align_angle(self, outer_bytes, inner_bytes):
        """旋转 inner 找与 outer 边缘环带最匹配的角度
        go-captcha rotate: 滑块从左到右 = CSS rotate 0~360° (顺时针)
        OpenCV warpAffine 正角度 = 逆时针, 所以匹配时用负角度模拟顺时针
        """
        outer = cv2.imdecode(np.frombuffer(outer_bytes, np.uint8), cv2.IMREAD_COLOR)
        inner = cv2.imdecode(np.frombuffer(inner_bytes, np.uint8), cv2.IMREAD_COLOR)
        if outer is None or inner is None:
            return None

        # inner 是小圆 (嵌在 outer 中间), 不做 resize 到同尺寸
        # 而是把 inner resize 到 outer 中心区域的大小
        oh, ow = outer.shape[:2]
        ih = inner.shape[0]
        if oh < 30 or ih < 30:
            return None

        # outer 的中心区域 = inner 应该对齐的位置
        # inner 占 outer 的比例大约是 inner_size / outer_size
        # 直接用 inner 原始尺寸, 从 outer 中心裁出同尺寸区域做比较
        cx_o, cy_o = ow // 2, oh // 2
        # outer 的边缘环带 (inner 边界附近)
        outer_gray = cv2.cvtColor(outer, cv2.COLOR_BGR2GRAY)
        inner_gray = cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY)

        # resize inner 到跟 outer 中心区域匹配
        inner_resized = cv2.resize(inner_gray, (ih, ih))
        size = ih
        cx = cy = size // 2
        radius = size // 2 - 2

        # 从 outer 中心裁出同尺寸区域
        ox1 = cx_o - size // 2
        oy1 = cy_o - size // 2
        if ox1 < 0 or oy1 < 0 or ox1 + size > ow or oy1 + size > oh:
            # 如果 inner 比 outer 大, 直接 resize
            outer_crop = cv2.resize(outer_gray, (size, size))
        else:
            outer_crop = outer_gray[oy1:oy1+size, ox1:ox1+size]

        # 多环带采样 (0.7~0.95 半径范围, 更宽更稳定)
        best_angle, best_score = 0, -float('inf')
        for deg in range(0, 360, 3):
            # 用负角度模拟顺时针旋转
            M = cv2.getRotationMatrix2D((cx, cy), -deg, 1.0)
            rot = cv2.warpAffine(inner_resized, M, (size, size), borderMode=cv2.BORDER_REFLECT)
            score = self._multi_ring_score(outer_crop, rot, cx, cy, radius)
            if score > best_score:
                best_score = score
                best_angle = deg

        # 精细搜索 ±3 度
        coarse = best_angle
        for deg_10 in range(max(0, coarse - 3) * 10, min(360, coarse + 4) * 10):
            deg = deg_10 / 10.0
            M = cv2.getRotationMatrix2D((cx, cy), -deg, 1.0)
            rot = cv2.warpAffine(inner_resized, M, (size, size), borderMode=cv2.BORDER_REFLECT)
            score = self._multi_ring_score(outer_crop, rot, cx, cy, radius)
            if score > best_score:
                best_score = score
                best_angle = deg

        return float(best_angle)

    def _multi_ring_score(self, outer, inner, cx, cy, radius):
        """多环带归一化互相关评分"""
        score = 0.0
        for r_ratio in (0.7, 0.8, 0.9, 0.95):
            r = int(radius * r_ratio)
            n = max(36, int(r * 2))
            outer_vals = []
            inner_vals = []
            for i in range(n):
                a = 2 * math.pi * i / n
                x = int(cx + r * math.cos(a))
                y = int(cy + r * math.sin(a))
                if 0 <= x < outer.shape[1] and 0 <= y < outer.shape[0]:
                    outer_vals.append(float(outer[y, x]))
                    inner_vals.append(float(inner[y, x]))
            if len(outer_vals) < 10:
                continue
            a = np.array(outer_vals) - np.mean(outer_vals)
            b = np.array(inner_vals) - np.mean(inner_vals)
            denom = (np.std(a) * np.std(b) * len(a)) + 1e-6
            score += float(np.dot(a, b) / denom)
        return score

    def _sample_ring(self, img, cx, cy, r_inner, r_outer, n_angles=180):
        vals = []
        for r in range(r_inner, r_outer + 1):
            for i in range(n_angles):
                a = 2 * math.pi * i / n_angles
                x = int(cx + r * math.cos(a))
                y = int(cy + r * math.sin(a))
                if 0 <= x < img.shape[1] and 0 <= y < img.shape[0]:
                    vals.append(float(img[y, x]))
                else:
                    vals.append(0.0)
        if not vals:
            return None
        return np.array(vals, dtype=np.float32)

    def _drag_rotation_slider(self, page, degree):
        try:
            track = page.locator('div.gc-drag-slide-bar').first
            handle = page.locator('div.gc-drag-block').first
            track_box = track.bounding_box()
            handle_box = handle.bounding_box()
            if not handle_box or not track_box:
                return False

            ratio = max(0, min(360, float(degree))) / 360.0
            usable_w = track_box['width'] - handle_box['width']
            target_x = track_box['x'] + handle_box['width'] / 2 + ratio * usable_w
            start_x = handle_box['x'] + handle_box['width'] / 2
            start_y = handle_box['y'] + handle_box['height'] / 2
            return self._drag_by_track(page, start_x, start_y, target_x, start_y)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 拖拽执行
    # ------------------------------------------------------------------

    def _drag_by_track(self, page, start_x, start_y, end_x, end_y):
        page.mouse.move(start_x, start_y)
        time.sleep(random.uniform(0.08, 0.16))
        page.mouse.down()
        track = generate_slide_track(end_x - start_x)
        for pt in track:
            page.mouse.move(start_x + pt['x'], end_y + pt['y'], steps=2)
            time.sleep(pt['t'] / 1000.0)
        page.mouse.up()
        time.sleep(random.uniform(0.3, 0.6))
        return True

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _capture_element_bytes(self, page, selector):
        try:
            for sel in selector.split(','):
                sel = sel.strip()
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    return loc.first.screenshot()
        except Exception:
            pass
        return None
