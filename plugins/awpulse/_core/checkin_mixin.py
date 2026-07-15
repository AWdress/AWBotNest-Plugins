# -*- coding: utf-8 -*-
"""签到 Mixin: 每日签到 + 验证码调度"""

import logging
import os
import re
import time

from .captcha_solver import cleanup_debug_files
from .human_simulation import human_like_delay


class CheckinMixin:
    """每日签到流程（含验证码识别调度）"""

    def daily_checkin(self, test_mode=False):
        """每日签到"""
        import re
        
        try:
            logging.info("=" * 60)
            logging.info("开始每日签到")
            logging.info("=" * 60)
            
            # 第一步：访问主页检查签到状态
            main_url = f"{self.base_url}plugin.php?id=dd_sign"
            logging.debug(f"检查签到状态页面: {main_url}")
            
            self.page.goto(main_url, wait_until='domcontentloaded')
            time.sleep(3)
            
            # 等待页面稳定
            try:
                self.page.wait_for_load_state('networkidle', timeout=10000)
            except:
                logging.debug("等待网络空闲超时，继续执行")
            
            time.sleep(2)
            
            # 安全获取页面内容
            page_text = None
            for attempt in range(3):
                try:
                    page_text = self.page.content()
                    break
                except Exception as e:
                    if "navigating" in str(e).lower():
                        logging.debug(f"页面正在导航，等待... (尝试 {attempt + 1}/3)")
                        time.sleep(2)
                    else:
                        raise
            
            if not page_text:
                logging.error("无法获取页面内容")
                return False
            
            # 检查系统繁忙
            error_keywords = ['系统繁忙', '请稍等重试', '服务器错误', '页面错误', '访问过于频繁', '请稍后再试', '操作过于频繁']
            for error_keyword in error_keywords:
                if error_keyword in page_text:
                    logging.warning(f"检测到页面错误: {error_keyword}")
                    return False
            
            # 使用正则表达式检查签到状态
            # 未签到按钮: <a href="javascript:;" class="ddpc_sign_btn_grey">今日未签到，点击签到</a>
            not_signed_pattern = r'(ddpc_sign_btn|sign.*btn).*?>(.*?未签到.*?点击签到|.*?点击签到|.*?今日未签到)'
            has_not_signed = bool(re.search(not_signed_pattern, page_text, re.IGNORECASE | re.DOTALL))
            
            # 已签到按钮: <a href="javascript:;" class="ddpc_sign_btn_grey">今日已签到</a>
            # 注意：排除统计信息"今日已签到 31842 人"（后面跟着数字）
            signed_pattern = r'(ddpc_sign_btn|sign.*btn).*?>.*?今日已签到(?!\s*\d)'
            has_signed = False
            if not has_not_signed:
                has_signed = bool(re.search(signed_pattern, page_text, re.IGNORECASE | re.DOTALL))
            
            # 判断签到状态
            if has_signed:
                logging.info("论坛显示今日已签到")
                if not test_mode:
                    self.stats.mark_checkin_success()
                    return True
                else:
                    logging.info("[测试] 已签到状态不跳过，继续测试签到流程...")
            
            if has_not_signed:
                logging.info("论坛显示未签到，继续签到流程")
            else:
                logging.warning("未检测到明确的签到状态标识，继续尝试签到")
            
            # 第二步：在当前页面查找签到按钮并点击
            logging.info("查找签到按钮...")
            
            # 查找签到按钮的多种可能选择器
            checkin_button_selectors = [
                'a:has-text("今日未签到")',
                'a:has-text("点击签到")',
                'a.ddpc_sign_btn',
                'a[href*="dd_sign"]',
                'button:has-text("签到")',
            ]
            
            checkin_button = None
            for selector in checkin_button_selectors:
                try:
                    btn = self.page.locator(selector).first
                    if btn.is_visible(timeout=2000):
                        checkin_button = btn
                        logging.info(f"找到签到按钮: {selector}")
                        break
                except:
                    continue
            
            if not checkin_button:
                logging.error("找不到签到按钮")
                return False
            
            # 点击签到按钮（测试模式也要点击，以触发验证码）
            if test_mode:
                logging.info("[测试] 点击签到按钮（触发验证码）...")
            else:
                logging.info("点击签到按钮...")
            
            checkin_button.click()
            time.sleep(3)
            
            # 检查是否出现图形验证码（拼图滑块）
            logging.info("检查是否出现图形验证码...")
            
            # 等待可能出现的验证码弹窗
            time.sleep(2)
            
            # 先检查是否有错误提示
            page_content = self.page.content()
            
            # 检查验证码次数限制
            captcha_limit_keywords = [
                '今日获取验证码次数已用完',
                '验证码次数已用完',
                '验证码获取次数超限',
                '今日验证码已达上限',
            ]
            
            for keyword in captcha_limit_keywords:
                if keyword in page_content:
                    logging.error(f"{keyword}")
                    logging.info("建议：")
                    logging.info("   1. 明天再试")
                    logging.info("   2. 或者手动在浏览器中完成签到")
                    logging.info("   3. 或者使用其他账号")
                    return False
            
            # 验证码识别 - 最多重试10次
            max_captcha_attempts = 10
            captcha_solved = False
            
            # 测试模式：检测到验证码就算成功
            if test_mode:
                logging.info("[测试] 检测到验证码，测试模式跳过识别")
                logging.info("[测试] 签到测试成功（已触发验证码）")
                return True
            
            for captcha_attempt in range(max_captcha_attempts):
                if captcha_attempt > 0:
                    wait = min(2 + 2 ** min(captcha_attempt, 4), 20)
                    logging.info(f"第 {captcha_attempt + 1}/{max_captcha_attempts} 次尝试识别验证码（等待 {wait}s）...")
                    time.sleep(wait)
                
                # 每次都重新检测验证码类型（因为失败后会刷新）
                captcha_type = 'none'
                try:
                    # 使用单例模式
                    if not self.captcha_solver:
                        from .captcha_solver import CaptchaSolver
                        self.captcha_solver = CaptchaSolver(self.config)

                    captcha_type = self.captcha_solver.detect_captcha_type(self.page)
                except Exception as e:
                    logging.debug(f"检测验证码类型失败: {e}")
                    captcha_type = 'none'
                
                if captcha_type == 'none':
                    logging.info("未检测到验证码，继续检查签到结果")
                    captcha_solved = True
                    break
                
                # 根据验证码类型选择识别方法
                success = False
                
                try:
                    if captcha_type == 'slider':
                        # 滑块验证码（拖动底部滑块）
                        if captcha_attempt == 0:
                            logging.info("检测到滑块验证码")
                        
                        if self.captcha_solver.is_available():
                            success = self.captcha_solver.solve_slider_captcha(self.page)
                            
                            if not success:
                                logging.info("滑块验证码识别失败，等待页面自动刷新后重新检测...")
                                continue
                        else:
                            logging.error("ddddocr 不可用")
                            return False
                    
                    elif captcha_type == 'drag_tile':
                        # 拖动拼图块验证码（直接拖动拼图块）
                        if captcha_attempt == 0:
                            logging.info("检测到拖动拼图块验证码")
                        
                        if self.captcha_solver.is_available():
                            # 使用相同的识别方法，但会自动识别拼图块
                            success = self.captcha_solver.solve_slider_captcha(self.page)
                            
                            if not success:
                                logging.info("拖动拼图块验证码识别失败，等待页面自动刷新后重新检测...")
                                continue
                        else:
                            logging.error("ddddocr 不可用")
                            return False
                    
                    elif captcha_type == 'click':
                        # 点选文字验证码 - 失败后等待页面自动刷新
                        if captcha_attempt == 0:
                            logging.info("检测到点选文字验证码")

                        if self.captcha_solver.is_available():
                            success = self.captcha_solver.solve_click_captcha(self.page)

                            if not success:
                                logging.info("点选验证码识别失败，等待页面自动刷新后重新检测...")
                                continue
                        else:
                            logging.error("ddddocr 不可用")
                            return False

                    elif captcha_type == 'icon_click':
                        # 图标点选验证码 - 按提示顺序点击大图中的图标
                        if captcha_attempt == 0:
                            logging.info("检测到图标点选验证码")

                        if self.captcha_solver.is_available():
                            success = self.captcha_solver.solve_icon_click_captcha(self.page)

                            if not success:
                                logging.info("图标点选验证码识别失败，等待页面自动刷新后重新检测...")
                                continue
                        else:
                            logging.error("ddddocr 不可用")
                            return False

                    elif captcha_type == 'rotate':
                        # 旋转验证码 - 失败后等待页面自动刷新
                        if captcha_attempt == 0:
                            logging.info("检测到旋转验证码")
                        
                        if self.captcha_solver.is_available():
                            success = self.captcha_solver.solve_rotate_captcha(self.page)
                            
                            if not success:
                                logging.info("旋转验证码识别失败，等待页面自动刷新后重新检测...")
                                continue
                        else:
                            logging.error("ddddocr 不可用")
                            return False
                    
                    else:
                        # 未知类型的验证码
                        logging.error(f"不支持的验证码类型: {captcha_type}")
                        return False
                
                except Exception as e:
                    logging.error(f"验证码识别异常: {e}")
                    success = False
                
                # 检查是否成功
                if success:
                    logging.info("验证码识别成功")
                    captcha_solved = True
                    break
                else:
                    logging.warning(f"第 {captcha_attempt + 1} 次验证码识别失败")
                    
                    if captcha_attempt >= max_captcha_attempts - 1:
                        logging.error("验证码识别失败，已达到最大重试次数")
                        return False
            
            if not captcha_solved:
                logging.error("验证码识别失败")
                return False
            
            result_content = ''
            last_error_keyword = None
            transient_error_keywords = ['请稍后再试', '请稍等重试', '访问过于频繁', '操作过于频繁']

            # 验证码通过后，部分页面只关闭验证码弹窗，不会自动提交签到；此时需要再次点击签到按钮。
            for result_attempt in range(3):
                time.sleep(3)
                result_content = self.page.content()

                if re.search(signed_pattern, result_content, re.IGNORECASE | re.DOTALL):
                    logging.info("=" * 60)
                    logging.info("签到成功！")
                    logging.info("=" * 60)
                    self.stats.mark_checkin_success()
                    return True

                last_error_keyword = next((keyword for keyword in error_keywords if keyword in result_content), None)
                if last_error_keyword:
                    if last_error_keyword in transient_error_keywords:
                        logging.warning(f"检测到临时页面提示: {last_error_keyword}，刷新签到页确认最终状态...")
                        try:
                            self.page.goto(main_url, wait_until='domcontentloaded')
                            time.sleep(3)
                            result_content = self.page.content()
                            if re.search(signed_pattern, result_content, re.IGNORECASE | re.DOTALL):
                                logging.info("=" * 60)
                                logging.info("签到成功！")
                                logging.info("=" * 60)
                                self.stats.mark_checkin_success()
                                return True
                        except Exception as e:
                            logging.debug(f"刷新签到页确认状态失败: {e}")
                        if result_attempt < 2:
                            continue
                    logging.warning(f"检测到页面错误: {last_error_keyword}")
                    return False

                if result_attempt >= 2:
                    break

                still_not_signed = bool(re.search(not_signed_pattern, result_content, re.IGNORECASE | re.DOTALL))
                if not still_not_signed:
                    continue

                logging.info("验证码通过后仍显示未签到，重新提交签到...")
                submitted_again = False
                for selector in checkin_button_selectors:
                    try:
                        btn = self.page.locator(selector).first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            submitted_again = True
                            time.sleep(2)
                            break
                    except:
                        continue

                if not submitted_again:
                    logging.warning("未找到可重新提交的签到按钮")
                    break
            
            logging.error("签到失败")
            # 保存调试信息
            try:
                debug_dir = os.path.join(base_dir, 'debug')
                os.makedirs(debug_dir, exist_ok=True)
                self.page.screenshot(path=os.path.join(debug_dir, 'checkin_failed.png'))
                with open(os.path.join(debug_dir, 'checkin_result.html'), 'w', encoding='utf-8') as f:
                    f.write(result_content)
                cleanup_debug_files(debug_dir, ['checkin_failed*.png', 'checkin_result*.html'])
                logging.info("已保存调试信息到 debug/ 目录")
            except:
                pass
            return False
                
        except Exception as e:
            logging.error(f"签到失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return False
    
