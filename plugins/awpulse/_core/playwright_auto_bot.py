#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWPulse - 98堂智能自动化系统核心机器人程序 (Playwright版本)
智能回复 · 自动签到 · 验证码识别 · 完全自动化
"""

import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from playwright.sync_api import Page
from .stats_manager import StatsManager
from .ai_reply_service import AIReplyService
from .captcha_solver import cleanup_debug_files
from .human_simulation import human_like_delay, random_scroll, random_mouse_movement
from .browser_mixin import BrowserMixin
from .auth_mixin import AuthMixin
from .checkin_mixin import CheckinMixin
from .reply_mixin import ReplyMixin

# 可写根目录（由插件在运行前注入 AWPULSE_BASE = ctx.data_dir）
# 注意：这里绝不调用 logging.basicConfig / 重配 root logger —— 插件运行在平台单进程内，
# 日志由平台/宿主统一处理（见插件 __init__.py 的日志适配）。
base_dir = os.environ.get('AWPULSE_BASE', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PlaywrightAutoBot(BrowserMixin, AuthMixin, CheckinMixin, ReplyMixin):
    def __init__(self, config=None, config_file=None):
        # 平台插件模式：直接注入配置 dict；兼容旧的 config_file 方式
        if config is not None:
            self.config = config
        else:
            if config_file is None:
                config_file = os.path.join(base_dir, 'config', 'config.json')
            self.config = self.load_config(config_file)

        log_level_str = self.config.get('log_level', 'INFO').upper()
        logging.getLogger().setLevel(getattr(logging, log_level_str, logging.INFO))

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.stop_flag = lambda: False
        self.fatal_error = None
        self.stats = StatsManager()
        self.ai_service = AIReplyService(self.config)
        self.message_service = None
        self.captcha_solver = None

        self.base_url = self.config.get('base_url', 'https://sehuatang.org/')
        self.username = self.config.get('username', '')
        self.password = self.config.get('password', '')
        self.security_question_id = self.config.get('security_question_id', '')
        self.security_answer = self.config.get('security_answer', '')

        self.storage_state_file = os.path.join(base_dir, 'data', 'storage_state.json')
        os.makedirs(os.path.join(base_dir, 'data'), exist_ok=True)

        self.daily_reply_limit = self.config.get('max_replies_per_day', 10)
        reply_interval = self.config.get('reply_interval', 120)
        if isinstance(reply_interval, list) and len(reply_interval) == 2:
            self.reply_interval_min = reply_interval[0]
            self.reply_interval_max = reply_interval[1]
        else:
            self.reply_interval_min = reply_interval
            self.reply_interval_max = reply_interval

        self.target_forums = self.config.get('target_forums', ['fid=141'])
        self.enable_daily_checkin = self.config.get('enable_daily_checkin', True)
        self.enable_auto_reply = self.config.get('enable_auto_reply', True)
        self.enable_test_mode = self.config.get('enable_test_mode', False)
        self.enable_test_checkin = self.config.get('enable_test_checkin', False)
        self.enable_test_reply = self.config.get('enable_test_reply', False)
        self.enable_test_post = self.config.get('enable_test_post', False)
        self.enable_smart_reply = self.config.get('enable_smart_reply', True)
        self.enable_ai_post_filter = self.config.get('enable_ai_post_filter', True)
        self.skip_admin_posts = self.config.get('skip_admin_posts', True)
        self.skip_keywords = self.config.get('skip_keywords', [])
        self.skip_prefixes = self.config.get('skip_prefixes', [])
        self.forum_names = self.config.get('forum_names', {})

        self.smart_reply_templates = self.config.get('smart_reply_templates', {})
        self.reply_templates = self.config.get('reply_templates', [
            '感谢分享！', '很不错的内容', '支持楼主！', '谢谢分享，收藏了'
        ])

        self.browser_headers = self.config.get('browser_headers', {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'accept_language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })

    def load_config(self, config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"配置文件不存在: {config_file}")
            return {}
        except json.JSONDecodeError as e:
            logging.error(f"配置文件格式错误: {e}")
            return {}

    def init_message_service(self):
        try:
            if self.page:
                from .playwright_forum_message_service import PlaywrightForumMessageService
                self.message_service = PlaywrightForumMessageService(self.page, self.base_url)
                logging.info("论坛消息服务初始化成功")
                return True
        except Exception as e:
            logging.debug(f"初始化消息服务失败: {e}")
        return False

    # PLACEHOLDER_RUN_AUTO_TASKS

    def run_auto_tasks(self):
        try:
            self.stats.check_and_reset_daily()
            today_stats = self.stats.get_today_stats()
            today_replies = today_stats['reply_count']

            is_test_mode = self.enable_test_mode or self.enable_test_checkin or self.enable_test_reply or self.enable_test_post
            test_checkin = self.enable_test_mode or self.enable_test_checkin
            test_reply = self.enable_test_mode or self.enable_test_reply
            test_post = self.enable_test_mode or self.enable_test_post
            should_run_checkin = test_checkin if is_test_mode else self.enable_daily_checkin
            should_run_reply = test_reply if is_test_mode else self.enable_auto_reply
            should_run_post = test_post if is_test_mode else self.config.get('enable_auto_post', False)

            if is_test_mode:
                logging.info("=" * 60)
                logging.info("测试模式已启用")
                if test_checkin: logging.info("  签到测试")
                if test_reply: logging.info("  回复测试")
                if test_post: logging.info("  发帖测试")
                logging.info("=" * 60)

            already_checked_in = False
            if should_run_checkin:
                try:
                    logging.info("=" * 60)
                    logging.info("检查今日签到状态...")
                    logging.info("=" * 60)
                    main_url = f"{self.base_url}plugin.php?id=dd_sign"
                    self.page.goto(main_url, wait_until='domcontentloaded')
                    time.sleep(2)
                    page_text = self.page.content()
                    signed_pattern = r'(ddpc_sign_btn|sign.*btn).*?>.*?今日已签到(?!\s*\d)'
                    if re.search(signed_pattern, page_text, re.IGNORECASE | re.DOTALL):
                        logging.info("今日已签到")
                        already_checked_in = True
                        if not is_test_mode:
                            self.stats.mark_checkin_success()
                    else:
                        logging.info("今日未签到")
                except Exception as e:
                    logging.warning(f"检查签到状态失败: {e}")

            if should_run_reply:
                if not test_reply:
                    if today_replies >= self.daily_reply_limit:
                        logging.info(f"今日已完成 {today_replies} 个回复，达到限额")
                    else:
                        logging.info("=" * 60)
                        logging.info("开始自动回复任务")
                        logging.info(f"今日已回复: {today_replies}/{self.daily_reply_limit}")
                        logging.info("=" * 60)
                        self._do_auto_reply(today_replies)
                else:
                    logging.info("=" * 60)
                    logging.info("[回复测试] 开始测试回复功能")
                    logging.info("=" * 60)
                    self._do_auto_reply(0, test_mode=True)

            if should_run_checkin:
                if already_checked_in:
                    logging.info("=" * 60)
                    logging.info("今日已签到，跳过签到执行步骤")
                    logging.info("=" * 60)
                else:
                    logging.info("=" * 60)
                    logging.info("开始签到..." if not test_checkin else "[签到测试] 开始测试签到功能")
                    logging.info("=" * 60)
                    self.daily_checkin(test_mode=test_checkin)

            if should_run_post:
                if test_post:
                    logging.info("=" * 60)
                    logging.info("[发帖测试] 开始测试发帖功能")
                    logging.info("=" * 60)
                self.run_auto_post(test_mode=test_post)

            if not is_test_mode:
                try:
                    self.get_user_info()
                except Exception as e:
                    logging.warning(f"获取用户信息失败: {e}")
                try:
                    if self.page:
                        from .playwright_forum_message_service import PlaywrightForumMessageService
                        self.message_service = PlaywrightForumMessageService(self.page, self.base_url)
                        unread_count = self.message_service.get_unread_count()
                        if unread_count > 0:
                            logging.info(f"您有 {unread_count} 条未读消息")
                        else:
                            logging.info("暂无未读消息")
                except Exception as e:
                    logging.warning(f"获取论坛消息失败: {e}")

            logging.info("=" * 60)
            logging.info("测试完成" if is_test_mode else "自动化任务完成")
            logging.info("=" * 60)
        except Exception as e:
            logging.error(f"自动化任务失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())

    def run(self):
        try:
            if not self.setup_browser():
                return False

            logged_in = False
            if self.is_cookie_valid():
                logging.info("=" * 60)
                logging.info("发现有效的登录状态")
                logging.info("尝试使用已保存的登录状态...")
                logging.info("=" * 60)
                try:
                    self.page.goto(self.base_url + "home.php?mod=space", wait_until='domcontentloaded')
                    time.sleep(2)
                    if self.check_login_status():
                        logging.info("登录状态验证成功！无需重新登录")
                        logged_in = True
                    else:
                        logging.warning("登录状态已过期")
                        self._cleanup_invalid_cookies()
                except Exception as e:
                    logging.warning(f"验证登录状态失败: {e}")
                    self._cleanup_invalid_cookies()

            if not logged_in:
                logging.info("=" * 60)
                logging.info("开始账号密码登录...")
                logging.info("=" * 60)
                if not self.login():
                    return False

            logging.info("登录成功，等待 5-10 秒...")
            time.sleep(random.randint(5, 10))
            self.run_auto_tasks()
            return True
        except Exception as e:
            logging.error(f"程序运行失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return False
        finally:
            self.cleanup()

    def run_auto_post(self, test_mode=False):
        try:
            from .playwright_auto_post_thread import PlaywrightAutoPostThread

            auto_post_config = self.config.get('auto_post', {})
            post_folder = auto_post_config.get('post_folder', 'novels')
            target_fid = auto_post_config.get('target_fid', 139)
            category_id = auto_post_config.get('category_id')
            max_posts = auto_post_config.get('max_posts_per_day', 5)
            post_interval = auto_post_config.get('post_interval', 300)
            move_after_post = auto_post_config.get('move_after_post', True)

            if test_mode:
                max_posts = 1
                logging.info("[测试] 测试模式：只发布 1 个文件")

            folder_path = os.path.join(base_dir, post_folder)
            if not os.path.exists(folder_path):
                logging.warning(f"发帖文件夹不存在: {folder_path}")
                return

            file_extensions = ['.txt', '.pdf', '.doc', '.docx', '.epub', '.mobi']
            files = [
                os.path.join(folder_path, f) for f in os.listdir(folder_path)
                if os.path.isfile(os.path.join(folder_path, f))
                and os.path.splitext(f)[1].lower() in file_extensions
            ]

            if not files:
                logging.info(f"ℹ文件夹中没有待发布的文件: {folder_path}")
                return

            files_to_post = files[:max_posts]
            logging.info(f"找到 {len(files)} 个文件，本次发布 {len(files_to_post)} 个")

            poster = PlaywrightAutoPostThread(self.page, self.config, test_mode=test_mode)
            success_count = 0

            for i, file_path in enumerate(files_to_post, 1):
                if self.stop_flag():
                    logging.info("检测到停止信号，停止发帖")
                    break

                logging.info(f"[{i}/{len(files_to_post)}] 处理文件: {os.path.basename(file_path)}")

                try:
                    success, thread_url = poster.post_thread(target_fid, file_path, category_id)
                    if thread_url == 'LIMIT_REACHED':
                        logging.warning("已达到今日发帖限额，停止发帖")
                        break
                    if success:
                        success_count += 1
                        logging.info(f"发帖成功！")
                        if thread_url:
                            logging.info(f"帖子链接: {thread_url}")
                        self.stats.add_post(os.path.basename(file_path), thread_url or '', os.path.basename(file_path))
                        if move_after_post:
                            posted_dir = os.path.join(base_dir, 'posted')
                            os.makedirs(posted_dir, exist_ok=True)
                            import shutil
                            shutil.move(file_path, os.path.join(posted_dir, os.path.basename(file_path)))
                    else:
                        logging.warning(f"发帖失败: {os.path.basename(file_path)}")
                except Exception as e:
                    logging.error(f"发帖异常: {e}")

                if i < len(files_to_post):
                    wait = random.randint(int(post_interval * 0.8), int(post_interval * 1.2))
                    logging.info(f"等待 {wait} 秒后发布下一个...")
                    time.sleep(wait)

            logging.info(f"发帖完成: 成功 {success_count}/{len(files_to_post)}")
        except Exception as e:
            logging.error(f"自动发帖任务失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())


def main():
    print("=" * 50)
    print("AWPulse - 98堂智能自动化系统 (Playwright版)")
    print("=" * 50)
    bot = PlaywrightAutoBot()
    success = bot.run()
    if success:
        print("所有任务完成！")
    else:
        print("任务执行失败")


if __name__ == "__main__":
    main()
