#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWPulse - 论坛消息服务 (Playwright版本)
获取和管理论坛系统消息
"""

import logging
import time
import re
from datetime import datetime
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout


class PlaywrightForumMessageService:
    """论坛消息服务类 (Playwright版本)"""
    
    def __init__(self, page: Page, base_url: str):
        """
        初始化论坛消息服务
        :param page: Playwright Page实例
        :param base_url: 论坛基础URL
        """
        self.page = page
        self.base_url = base_url
        self.message_url = f"{base_url}home.php?mod=space&do=notice&view=system"
        
    def get_messages(self, max_count=20):
        """
        获取论坛系统消息列表
        :param max_count: 最多获取的消息数量
        :return: 消息列表 [{'id', 'title', 'content', 'time', 'is_read', 'link'}]
        """
        try:
            # 检查页面是否还活着（用 evaluate 真正跟浏览器通信）
            try:
                self.page.evaluate("1")
            except Exception:
                return {'success': False, 'error': '浏览器未运行', 'messages': []}

            logging.info("正在获取论坛消息...")
            
            # 访问消息页面（添加超时）
            try:
                self.page.goto(self.message_url, wait_until='domcontentloaded', timeout=30000)
                time.sleep(3)
            except PlaywrightTimeout:
                logging.error("访问消息页面超时")
                return {'success': False, 'error': '页面加载超时', 'messages': []}
            
            logging.debug(f"消息页面已加载: {self.page.url}")
            
            # 检查是否需要登录
            page_source = self.page.content()
            current_url = self.page.url
            if "需要先登录" in page_source or "请先登录" in page_source or "member.php?mod=logging" in current_url:
                logging.warning("需要登录才能查看消息")
                return {'success': False, 'error': '需要登录', 'messages': []}
            
            messages = []
            
            # 解析消息列表
            try:
                logging.debug("开始解析消息列表...")
                
                # 直接从 HTML 解析，避免 Playwright 元素定位卡住
                messages = self._parse_messages_from_html(page_source, max_count)
                
                if not messages:
                    logging.info("暂无消息")
                else:
                    logging.info(f"成功获取 {len(messages)} 条消息")
                
                # 统计未读消息数量
                unread_count = sum(1 for msg in messages if not msg.get('is_read', True))
                
                return {
                    'success': True,
                    'messages': messages,
                    'total': len(messages),
                    'unread': unread_count
                }
                
            except Exception as e:
                logging.error(f"解析消息列表失败: {e}")
                import traceback
                logging.debug(traceback.format_exc())
                return {'success': False, 'error': str(e), 'messages': []}
                
        except Exception as e:
            logging.error(f"获取论坛消息失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return {'success': False, 'error': str(e), 'messages': []}
    
    def _parse_message_element(self, element, idx):
        """解析单个消息元素"""
        try:
            message = {
                'id': f"msg_{idx}_{int(time.time())}",
                'title': '',
                'content': '',
                'time': '',
                'is_read': True,
                'link': ''
            }
            
            # 设置较短的超时时间，避免卡住
            timeout = 2000  # 2秒
            
            # 获取消息标题和链接
            try:
                # 先获取链接
                try:
                    link_elem = element.locator("dt a").first
                    message['link'] = link_elem.get_attribute('href', timeout=timeout) or ''
                except:
                    pass
                
                # 标题在 dd.ntc_body 中
                try:
                    ntc_body = element.locator("dd.ntc_body").first
                    full_text = ntc_body.text_content(timeout=timeout).strip()
                    
                    # 尝试移除 blockquote 的内容
                    try:
                        blockquote_elem = ntc_body.locator("blockquote").first
                        blockquote_text = blockquote_elem.text_content(timeout=timeout).strip()
                        title_text = full_text.replace(blockquote_text, '').strip()
                        if title_text:
                            message['title'] = title_text
                        else:
                            message['title'] = full_text
                    except:
                        message['title'] = full_text
                except:
                    # 如果找不到 ntc_body，使用元素文本的第一行
                    try:
                        element_text = element.text_content(timeout=timeout).strip()
                        if element_text:
                            message['title'] = element_text.split('\n')[0][:100]
                    except:
                        message['title'] = '无标题'
            except:
                message['title'] = '无标题'
            
            # 获取消息内容
            try:
                try:
                    blockquote_elem = element.locator("blockquote").first
                    message['content'] = blockquote_elem.text_content(timeout=timeout).strip()
                except:
                    try:
                        content_elem = element.locator("dd.ntc_body").first
                        message['content'] = content_elem.text_content(timeout=timeout).strip()
                    except:
                        try:
                            content_elem = element.locator("dd").first
                            message['content'] = content_elem.text_content(timeout=timeout).strip()
                        except:
                            message['content'] = ''
            except:
                message['content'] = ''
            
            # 获取时间
            try:
                time_elem = element.locator("span.xg1").first
                message['time'] = time_elem.text_content(timeout=timeout).strip()
            except:
                # 尝试从标题中提取时间
                try:
                    element_text = element.text_content(timeout=timeout).strip()
                    time_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2})', element_text)
                    if time_match:
                        message['time'] = time_match.group(1)
                except:
                    pass
            
            # 判断是否已读
            try:
                class_name = element.get_attribute('class', timeout=timeout) or ''
                message['is_read'] = 'new' not in class_name.lower() and 'unread' not in class_name.lower()
            except:
                pass
            
            # 过滤掉不需要的系统消息
            skip_keywords = [
                '本次登录位置',
                '上次登录位置',
                '登录位置',
                '安全提醒'
            ]
            
            for keyword in skip_keywords:
                if keyword in message['title'] or keyword in message['content']:
                    logging.debug(f"跳过系统消息: {message['title'][:30]}")
                    return None
            
            # 如果标题和内容都为空，返回None
            if not message['title'] and not message['content']:
                return None
            
            return message
            
        except Exception as e:
            logging.debug(f"解析消息元素失败: {e}")
            return None
    
    def _parse_messages_from_html(self, html, max_count=20):
        """从HTML源码中解析消息"""
        messages = []
        
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html, 'lxml')
            
            # 查找所有消息元素（通常在 dl 标签中）
            message_elements = soup.find_all('dl', class_='cl', limit=max_count)
            
            if not message_elements:
                # 尝试其他选择器
                message_elements = soup.find_all('dl', limit=max_count)
            
            logging.debug(f"从HTML找到 {len(message_elements)} 个消息元素")
            
            for idx, element in enumerate(message_elements):
                try:
                    message = {
                        'id': f"msg_{idx}_{int(time.time())}",
                        'title': '',
                        'content': '',
                        'time': '',
                        'is_read': True,
                        'link': ''
                    }
                    
                    # 获取链接
                    link_elem = element.find('a')
                    if link_elem and link_elem.get('href'):
                        href = link_elem.get('href')
                        message['link'] = href if href.startswith('http') else self.base_url + href
                    
                    # 获取标题（在 dd.ntc_body 中，但不包括 blockquote）
                    ntc_body = element.find('dd', class_='ntc_body')
                    if ntc_body:
                        # 获取完整文本
                        full_text = ntc_body.get_text(strip=True)
                        
                        # 移除 blockquote 的内容
                        blockquote = ntc_body.find('blockquote')
                        if blockquote:
                            blockquote_text = blockquote.get_text(strip=True)
                            message['content'] = blockquote_text
                            message['title'] = full_text.replace(blockquote_text, '').strip()
                        else:
                            message['title'] = full_text
                    
                    # 获取时间
                    time_elem = element.find('span', class_='xg1')
                    if time_elem:
                        message['time'] = time_elem.get_text(strip=True)
                    else:
                        # 尝试从文本中提取时间
                        element_text = element.get_text()
                        time_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2})', element_text)
                        if time_match:
                            message['time'] = time_match.group(1)
                    
                    # 判断是否已读
                    class_name = element.get('class', [])
                    if isinstance(class_name, list):
                        class_name = ' '.join(class_name)
                    message['is_read'] = 'new' not in class_name.lower() and 'unread' not in class_name.lower()
                    
                    # 过滤系统消息
                    skip_keywords = ['本次登录位置', '上次登录位置', '登录位置', '安全提醒']
                    if any(keyword in message['title'] or keyword in message['content'] for keyword in skip_keywords):
                        logging.debug(f"跳过系统消息: {message['title'][:30]}")
                        continue
                    
                    # 如果标题和内容都为空，跳过
                    if not message['title'] and not message['content']:
                        continue
                    
                    messages.append(message)
                    logging.debug(f"解析消息 {idx+1}: {message['title'][:30]}")
                    
                except Exception as e:
                    logging.debug(f"解析消息 {idx+1} 失败: {e}")
                    continue
            
            logging.debug(f"从HTML成功解析 {len(messages)} 条消息")
            
        except Exception as e:
            logging.error(f"从HTML解析消息失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
        
        return messages
    
    def get_unread_count(self):
        """
        获取未读消息数量（快速检查）
        :return: 未读消息数量
        """
        try:
            # 访问首页或个人中心，查找未读消息提示
            current_url = self.page.url
            
            # 如果不在论坛页面，先访问首页
            if self.base_url not in current_url:
                self.page.goto(self.base_url, wait_until='domcontentloaded')
                time.sleep(2)
            
            page_source = self.page.content()
            
            # 查找未读消息数量标识
            # 常见格式：<a>消息(3)</a> 或 <span class="num">3</span>
            unread_patterns = [
                r'消息\s*\((\d+)\)',
                r'通知\s*\((\d+)\)',
                r'<span[^>]*class="[^"]*num[^"]*"[^>]*>(\d+)</span>',
            ]
            
            for pattern in unread_patterns:
                match = re.search(pattern, page_source)
                if match:
                    count = int(match.group(1))
                    logging.debug(f"检测到 {count} 条未读消息")
                    return count
            
            return 0
            
        except Exception as e:
            logging.debug(f"获取未读消息数量失败: {e}")
            return 0
