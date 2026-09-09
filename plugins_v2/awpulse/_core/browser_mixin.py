# -*- coding: utf-8 -*-
"""浏览器生命周期管理 Mixin"""

import json
import logging
import os
import time

import cloakbrowser


class BrowserMixin:
    """浏览器启动、Cookie 管理、资源清理"""

    def setup_browser(self, headless=False):
        """设置Playwright浏览器"""
        try:
            # 从配置文件读取 headless 设置
            config_headless = self.config.get('headless', None)
            
            # 检测 Docker 环境
            is_docker = os.path.exists('/.dockerenv')
            
            if config_headless is not None:
                # 配置文件优先
                headless = config_headless
                logging.info(f"使用配置文件的 headless 设置: {headless}")
            else:
                # 自动检测：本地默认非 headless，Docker 视虚拟显示器情况决定
                headless = False if not is_docker else (os.environ.get('DISPLAY') is None)

            # 安全回退：若最终为非 headless 但当前无可用 DISPLAY，强制切回 headless，避免崩溃
            if not headless and is_docker and not os.environ.get('DISPLAY'):
                logging.warning("Docker 环境未检测到可用 DISPLAY，自动回退 headless 模式")
                headless = True

            logging.info(f"浏览器模式: {'headless' if headless else '有头(虚拟显示器)'}")
            
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
            
            # 启动 CloakBrowser（唯一浏览器内核）
            self.browser = cloakbrowser.launch(
                headless=headless,
                args=browser_args,
                locale='zh-CN',
                timezone='Asia/Shanghai',
            )
            
            # 创建上下文
            user_agent = self.browser_headers.get('user_agent')
            
            context_options = {
                'user_agent': user_agent,
                'viewport': {'width': 1920, 'height': 1080},
                'locale': 'zh-CN',
                'timezone_id': 'Asia/Shanghai',
                'extra_http_headers': {
                    'Accept-Language': self.browser_headers.get('accept_language', 'zh-CN,zh;q=0.9'),
                }
            }
            
            # 如果有保存的 storage state，加载它
            if os.path.exists(self.storage_state_file) and self.is_cookie_valid():
                try:
                    context_options['storage_state'] = self.storage_state_file
                    logging.info("使用已保存的登录状态创建浏览器上下文")
                except Exception as e:
                    logging.debug(f"加载storage state失败: {e}")
            
            self.context = self.browser.new_context(**context_options)
            self.page = self.context.new_page()
            
            # 设置默认超时
            self.page.set_default_timeout(30000)
            
            logging.info("CloakBrowser 浏览器启动成功")
            logging.debug(f"User-Agent: {user_agent}")
            
            # 初始化消息服务
            self.init_message_service()
            
            return True
            
        except Exception as e:
            logging.error(f"浏览器启动失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return False
    
    def is_cookie_valid(self):
        """检查Cookie是否在有效期内"""
        if not os.path.exists(self.storage_state_file):
            return False
        
        try:
            file_time = os.path.getmtime(self.storage_state_file)
            current_time = time.time()
            days_old = (current_time - file_time) / 86400
            
            if days_old > 7:
                logging.warning(f"Cookie已过期 ({days_old:.1f}天)")
                return False
            
            logging.debug(f"Cookie有效 (已保存 {days_old:.1f}天)")
            return True
        except Exception as e:
            logging.debug(f"Cookie检查失败: {e}")
            return False
    
    def save_cookies(self):
        """保存登录状态"""
        try:
            storage_state = self.context.storage_state()
            
            with open(self.storage_state_file, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, indent=2, ensure_ascii=False)
            
            cookies = storage_state.get('cookies', [])
            logging.info(f"登录状态已保存 ({len(cookies)} 个cookies)")
            
            # 检测关键cookie
            key_cookies = ['cPNj_2132_auth', 'cPNj_2132_saltkey', 'cf_clearance']
            found_keys = [c['name'] for c in cookies if c['name'] in key_cookies]
            if found_keys:
                logging.info(f"关键Cookie: {', '.join(found_keys)}")
            
            return True
        except Exception as e:
            logging.error(f"保存cookies失败: {e}")
            return False
    
    def _cleanup_invalid_cookies(self):
        """清理无效的Cookie文件"""
        try:
            if os.path.exists(self.storage_state_file):
                os.remove(self.storage_state_file)
                logging.info("已清理无效Cookie文件")
        except Exception as e:
            logging.debug(f"清理Cookie失败: {e}")
    

    def cleanup(self):
        """清理资源"""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logging.info("浏览器已关闭")
        except Exception as e:
            logging.debug(f"清理资源时出错: {e}")
    
