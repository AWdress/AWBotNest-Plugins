# -*- coding: utf-8 -*-
"""人类行为模拟工具函数"""

import time
import random
from playwright.sync_api import Page


def human_like_delay(min_sec=1, max_sec=3, test_mode=False):
    if test_mode:
        delay = random.uniform(min_sec * 0.3, max_sec * 0.3)
    else:
        delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def random_scroll(page: Page, times=None, test_mode=False):
    if test_mode:
        times = 1
    elif times is None:
        times = random.randint(1, 3)

    for _ in range(times):
        scroll_amount = random.randint(-300, 500)
        try:
            page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            time.sleep(random.uniform(0.3, 1.2) if not test_mode else 0.2)
        except Exception:
            pass


def random_mouse_movement(page: Page, test_mode=False):
    if test_mode:
        return
    try:
        for _ in range(random.randint(1, 3)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.1, 0.3))
    except Exception:
        pass
