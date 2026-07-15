# -*- coding: utf-8 -*-
"""认证相关 Mixin: 登录、年龄验证、状态检查"""

import logging
import os
import re
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from .human_simulation import human_like_delay


class AuthMixin:
    """登录、年龄验证、登录状态检查、用户信息获取"""

    def handle_age_verification(self):
        """处理年龄验证"""
        try:
            time.sleep(1)
            content = self.page.content()
            
            if "满18岁" not in content and "If you are over 18" not in content:
                logging.debug("ℹ无需年龄验证")
                return True
            
            logging.debug("检测到年龄验证页面")
            time.sleep(2)
            
            # 尝试点击按钮
            selectors = [
                'a.enter-btn',
                'a:has-text("满18岁")',
                'a:has-text("click here")',
                'a'
            ]
            
            for selector in selectors:
                try:
                    button = self.page.locator(selector).first
                    if button.is_visible(timeout=2000):
                        logging.debug(f"找到年龄验证按钮: {selector}")
                        button.click()
                        time.sleep(3)
                        
                        if "满18岁" not in self.page.content():
                            logging.info("年龄验证通过")
                            return True
                except:
                    continue
            
            # 尝试直接访问绕过
            logging.info("尝试直接访问绕过...")
            self.page.goto(self.base_url + "forum.php", wait_until='domcontentloaded')
            time.sleep(3)
            
            if "满18岁" not in self.page.content():
                logging.info("成功绕过年龄验证")
                return True
            
            logging.error("年龄验证失败")
            return False
            
        except Exception as e:
            logging.error(f"年龄验证处理失败: {e}")
            return False

    
    def login(self):
        """自动登录"""
        try:
            logging.info("开始自动登录...")
            
            login_url = f"{self.base_url}member.php?mod=logging&action=login"
            logging.debug(f"访问登录页面: {login_url}")
            
            self.page.goto(login_url, wait_until='domcontentloaded')
            time.sleep(3)
            
            # 处理年龄验证
            self.handle_age_verification()
            
            # 等待CF验证
            logging.debug("等待页面加载...")
            max_wait = 60
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                content = self.page.content()
                
                if "Checking your browser" in content or "Just a moment" in content:
                    elapsed = int(time.time() - start_time)
                    logging.info(f"等待Cloudflare验证... ({elapsed}秒)")
                    time.sleep(3)
                    continue
                
                # 检查是否找到登录表单
                try:
                    if self.page.locator('input[name="username"]').count() > 0:
                        elapsed = int(time.time() - start_time)
                        logging.info(f"页面加载完成 (耗时 {elapsed}秒)")
                        break
                except:
                    pass
                
                # 检查是否已登录
                if "logging&action=logout" in content or "退出" in content:
                    logging.info("检测到已登录状态")
                    return True
                
                time.sleep(3)
            
            # 填写表单
            logging.debug("填写登录表单...")
            
            try:
                # 用户名
                username_input = self.page.locator('input[name="username"]').first
                username_input.fill(self.username, timeout=30000)
                logging.debug(f"填写用户名: {self.username}")
                
                # 密码
                password_input = self.page.locator('input[type="password"]').first
                password_input.fill(self.password, timeout=30000)
                logging.debug("填写密码")
            except Exception as e:
                logging.error(f"填写登录表单失败: {e}")
                # 保存调试信息
                try:
                    debug_dir = os.path.join(base_dir, 'debug')
                    os.makedirs(debug_dir, exist_ok=True)
                    self.page.screenshot(path=os.path.join(debug_dir, 'login_form_timeout.png'))
                    with open(os.path.join(debug_dir, 'login_form_timeout.html'), 'w', encoding='utf-8') as f:
                        f.write(self.page.content())
                    logging.info("已保存调试信息到 debug/ 目录")
                except Exception as debug_error:
                    logging.error(f"保存调试信息失败: {debug_error}")
                return False
            
            # 安全提问
            if self.security_question_id and self.security_answer:
                try:
                    question_select = self.page.locator('select[name="questionid"]').first
                    if question_select.is_visible(timeout=2000):
                        question_select.select_option(self.security_question_id)
                        logging.debug(f"选择安全提问: {self.security_question_id}")
                        time.sleep(1)
                        
                        answer_input = self.page.locator('input[name="answer"]').first
                        answer_input.fill(self.security_answer)
                        logging.debug("填写安全提问答案")
                        time.sleep(2)
                except:
                    logging.debug("ℹ未发现安全提问")
            
            time.sleep(3)
            
            # 查找并点击登录按钮
            logging.debug("查找登录按钮...")
            
            login_selectors = [
                'button[name="loginsubmit"]',
                'input[name="loginsubmit"]',
                'button.pn.pnc',
                'input[value="登录"]',
                'button:has-text("登录")',
            ]
            
            login_button = None
            for selector in login_selectors:
                try:
                    button = self.page.locator(selector).first
                    if button.is_visible(timeout=2000):
                        login_button = button
                        logging.debug(f"找到登录按钮: {selector}")
                        break
                except:
                    continue
            
            if not login_button:
                logging.error("找不到登录按钮")
                # 保存调试信息
                try:
                    debug_dir = os.path.join(base_dir, 'debug')
                    os.makedirs(debug_dir, exist_ok=True)
                    self.page.screenshot(path=os.path.join(debug_dir, 'login_failed.png'))
                    with open(os.path.join(debug_dir, 'login_page_debug.html'), 'w', encoding='utf-8') as f:
                        f.write(self.page.content())
                    logging.info("已保存调试信息")
                except:
                    pass
                return False
            
            # 点击登录
            login_button.click()
            logging.debug("点击登录按钮")
            time.sleep(5)
            
            # 检查登录结果
            content = self.page.content()
            
            # 检查错误提示
            error_indicators = {
                "密码错误": "账号密码错误",
                "用户名错误": "账号不存在",
                "安全提问答案不正确": "安全提问答案错误",
                "登录失败超过限制": "登录失败次数过多",
                "您的账号已被禁止": "账号已被封禁",
            }
            
            for error_keyword, error_msg in error_indicators.items():
                if error_keyword in content:
                    logging.error(f"{error_msg}")
                    self.fatal_error = error_msg
                    return False
            
            # 检查是否登录成功
            if "logging&action=logout" in content or "退出" in content or "home.php" in self.page.url:
                logging.info("=" * 60)
                logging.info("登录成功！")
                logging.info("=" * 60)
                
                # 保存登录状态
                self.save_cookies()
                
                return True
            else:
                logging.warning("登录状态不明确，尝试访问个人中心确认...")
                self.page.goto(self.base_url + "home.php?mod=space", wait_until='domcontentloaded')
                time.sleep(3)
                
                content = self.page.content()
                if "退出" in content or "logging&action=logout" in content:
                    logging.info("登录成功")
                    self.save_cookies()
                    return True
                else:
                    logging.error("登录失败")
                    return False
                    
        except Exception as e:
            logging.error(f"登录失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return False
    
    def check_login_status(self):
        """检查登录状态"""
        try:
            content = self.page.content()
            
            if "member.php?mod=logging&action=logout" in content or "退出" in content:
                logging.info(f"已登录 (用户: {self.username})")
                return True
            
            # 访问个人中心确认
            logging.debug("访问个人中心确认登录状态...")
            self.page.goto(self.base_url + "home.php?mod=space&do=profile", wait_until='domcontentloaded')
            time.sleep(2)
            
            content = self.page.content()
            current_url = self.page.url
            
            if "退出" in content or "个人资料" in content or "member.php?mod=logging&action=logout" in content:
                logging.info("登录状态有效")
                return True
            
            if "member.php?mod=logging" in current_url and "action=login" in current_url:
                logging.debug("ℹ已跳转到登录页面，登录状态已过期")
                return False
            
            logging.warning("登录状态不明确")
            return False
            
        except Exception as e:
            logging.error(f"检查登录状态失败: {e}")
            return False

    
    def get_user_info(self):
        """获取用户信息（等级、积分、金钱等）"""
        try:
            logging.debug("开始获取用户信息...")
            
            # 访问个人中心页面
            profile_url = f"{self.base_url}home.php?mod=space&uid=&do=profile"
            self.page.goto(profile_url, wait_until='domcontentloaded')
            time.sleep(3)
            
            user_info = {
                "user_group": "",
                "credits": 0,
                "money": 0,
                "coins": 0,
                "rating": 0
            }
            
            # 获取页面源码
            page_source = self.page.content()
            
            # 使用正则表达式提取信息
            import re
            
            # 提取用户组
            group_patterns = [
                r'用户组[：:]\s*([^<\n]+)',
                r'用户组[：:]</em>\s*([^<\n]+)',
                r'>用户组[：:]\s*</em>\s*<em[^>]*>([^<]+)</em>',
            ]
            for pattern in group_patterns:
                group_match = re.search(pattern, page_source)
                if group_match:
                    user_info["user_group"] = group_match.group(1).strip()
                    logging.info(f"用户组: {user_info['user_group']}")
                    break
            
            # 提取积分
            credits_patterns = [
                r'<em>积分</em>\s*(\d+)',
                r'>积分</em>\s*(\d+)',
                r'积分[：:]\s*(\d+)',
            ]
            for pattern in credits_patterns:
                credits_match = re.search(pattern, page_source)
                if credits_match:
                    user_info["credits"] = int(credits_match.group(1))
                    logging.info(f"积分: {user_info['credits']}")
                    break
            
            # 提取金钱
            money_patterns = [
                r'<em>金钱</em>\s*(\d+)',
                r'>金钱</em>\s*(\d+)',
                r'金钱[：:]\s*(\d+)',
            ]
            for pattern in money_patterns:
                money_match = re.search(pattern, page_source)
                if money_match:
                    user_info["money"] = int(money_match.group(1))
                    logging.info(f"金钱: {user_info['money']}")
                    break
            
            # 提取色币
            coins_patterns = [
                r'<em>色币</em>\s*(\d+)',
                r'>色币</em>\s*(\d+)',
                r'色币[：:]\s*(\d+)',
            ]
            for pattern in coins_patterns:
                coins_match = re.search(pattern, page_source)
                if coins_match:
                    user_info["coins"] = int(coins_match.group(1))
                    logging.info(f"色币: {user_info['coins']}")
                    break
            
            # 提取评分
            rating_patterns = [
                r'<em>评分</em>\s*(\d+)',
                r'>评分</em>\s*(\d+)',
                r'评分[：:]\s*(\d+)',
            ]
            for pattern in rating_patterns:
                rating_match = re.search(pattern, page_source)
                if rating_match:
                    user_info["rating"] = int(rating_match.group(1))
                    logging.info(f"评分: {user_info['rating']}")
                    break
            
            # 保存到统计数据
            self.stats.update_user_info(
                user_group=user_info["user_group"],
                credits=user_info["credits"],
                money=user_info["money"],
                coins=user_info["coins"],
                rating=user_info["rating"]
            )
            
            logging.info("用户信息获取成功")
            return user_info
            
        except Exception as e:
            logging.error(f"获取用户信息失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return None
    
