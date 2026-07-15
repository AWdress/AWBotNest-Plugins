#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWPulse - 自动发帖模块 (Playwright版本)
自动识别文件名 · 提取内容预览 · 上传附件 · 自动发布
"""

import os
import re
import time
import logging
from datetime import datetime
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout


class PlaywrightAutoPostThread:
    """自动发帖类 (Playwright版本)"""
    
    def __init__(self, page: Page, config: dict, test_mode: bool = None):
        self.page = page
        self.config = config
        self.base_url = config.get('base_url', 'https://sehuatang.org/')
        
        # 测试模式：优先使用传入的参数，否则从配置读取
        if test_mode is not None:
            self.test_mode = test_mode
        else:
            self.test_mode = config.get('enable_test_post', False)
        
        # 调试日志
        if self.test_mode:
            logging.info(f"PlaywrightAutoPostThread 初始化：测试模式已启用")
        
    def parse_filename(self, filename, file_path=None):
        """
        解析文件名，提取标题信息
        优先级：AI识别 > 标准格式匹配 > 关键词提取
        标准格式：【书名】(1-84) 作者：作者名.txt
        返回: {
            'title': '书名',
            'chapters': '1-84',
            'author': '作者名',
            'full_title': '【书名】(1-84) 作者：作者名'
        }
        """
        # 移除文件扩展名
        name_without_ext = os.path.splitext(filename)[0]
        
        # 优先级1: 使用AI识别（最准确）
        if file_path:
            ai_title_info = self._extract_title_by_ai(filename, file_path)
            if ai_title_info:
                return ai_title_info
        
        # 优先级2: 检查是否符合标准格式
        # 标准格式: 【书名】(章节) 作者：作者名
        pattern = r'^【([^】]+)】\s*\((.+?)\)\s*作者[：:]\s*(.+)$'
        match = re.match(pattern, name_without_ext)
        
        if match:
            title = match.group(1).strip()
            chapters = match.group(2).strip()
            author = match.group(3).strip()
            
            logging.info(f"文件名符合标准格式")
            return {
                'title': title,
                'chapters': chapters,
                'author': author,
                'full_title': f"【{title}】({chapters}) 作者：{author}"
            }
        
        # 优先级3: 使用关键词从内容提取
        logging.warning(f"文件名格式不匹配标准格式: {filename}")
        if file_path:
            logging.debug(f"尝试从文件内容提取信息...")
            content_info = self._extract_info_from_content(file_path)
            if content_info:
                return content_info
        
        # 都失败了，使用原文件名
        logging.info(f"建议格式: 【书名】(1-84) 作者：作者名.txt")
        return {
            'title': name_without_ext,
            'chapters': '',
            'author': '',
            'full_title': name_without_ext
        }
    
    def _extract_title_by_ai(self, filename, file_path):
        """使用AI识别并生成标准格式的标题"""
        try:
            # 检查是否启用AI发帖识别
            if not self.config.get('enable_ai_post', False):
                return None
            
            # 检查AI配置
            ai_api_url = self.config.get('ai_api_url', '')
            ai_api_key = self.config.get('ai_api_key', '')
            
            if not ai_api_url or not ai_api_key:
                logging.debug("AI配置不完整，跳过AI识别")
                return None
            
            logging.info("使用AI识别标题...")
            
            # 读取文件内容（前2000字符）
            content = self._read_file_content(file_path, max_chars=2000)
            if not content:
                return None
            
            # 构建AI提示词
            prompt = f"""请分析以下小说内容，提取书名、章节范围和作者信息。

文件名: {filename}
内容预览:
{content[:1000]}

请按以下格式返回（如果无法确定某项，请留空）:
书名: 
章节: 
作者: 

要求:
1. 书名要准确，不要包含章节信息
2. 章节格式如: 1-84 或 第1-84章
3. 作者名要完整
"""
            
            # 调用AI API
            import requests
            import json
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {ai_api_key}'
            }
            
            data = {
                'model': self.config.get('ai_model', 'gpt-3.5-turbo'),
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'max_tokens': 200
            }
            
            # 使用代理（如果配置了）
            proxies = None
            ai_proxy = self.config.get('ai_proxy', '')
            if ai_proxy:
                proxies = {
                    'http': ai_proxy,
                    'https': ai_proxy
                }
            
            response = requests.post(
                ai_api_url,
                headers=headers,
                json=data,
                proxies=proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content'].strip()
                
                # 解析AI返回的结果
                title_match = re.search(r'书名[：:]\s*(.+)', ai_response)
                chapters_match = re.search(r'章节[：:]\s*(.+)', ai_response)
                author_match = re.search(r'作者[：:]\s*(.+)', ai_response)
                
                title = title_match.group(1).strip() if title_match else ''
                chapters = chapters_match.group(1).strip() if chapters_match else ''
                author = author_match.group(1).strip() if author_match else ''
                
                if title:
                    logging.info(f"AI识别成功: 书名={title}, 章节={chapters}, 作者={author}")
                    return {
                        'title': title,
                        'chapters': chapters,
                        'author': author,
                        'full_title': f"【{title}】({chapters}) 作者：{author}" if chapters and author else title
                    }
            else:
                logging.debug(f"AI API调用失败: {response.status_code}")
                
        except Exception as e:
            logging.debug(f"AI识别失败: {e}")
        
        return None
    
    def _extract_info_from_content(self, file_path):
        """从文件内容中提取标题、作者等信息"""
        try:
            content = self._read_file_content(file_path, max_chars=5000)
            if not content:
                return None
            
            # 提取作者
            author = self._extract_author_from_content(content)
            
            # 提取书名（从文件名或内容）
            filename = os.path.basename(file_path)
            title = os.path.splitext(filename)[0]
            
            # 尝试从内容中提取书名
            title_patterns = [
                r'《(.+?)》',
                r'书名[：:]\s*(.+)',
                r'作品[：:]\s*(.+)',
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, content[:500])
                if match:
                    extracted_title = match.group(1).strip()
                    if len(extracted_title) < 50:  # 合理的书名长度
                        title = extracted_title
                        break
            
            if author:
                logging.debug(f"从内容提取: 书名={title}, 作者={author}")
                return {
                    'title': title,
                    'chapters': '',
                    'author': author,
                    'full_title': f"【{title}】 作者：{author}"
                }
            
        except Exception as e:
            logging.debug(f"从内容提取信息失败: {e}")
        
        return None
    
    def _extract_author_from_content(self, content):
        """从内容中提取作者名"""
        author_patterns = [
            r'作者[：:]\s*([^\n\r]{2,20})',
            r'作\s*者[：:]\s*([^\n\r]{2,20})',
            r'著[：:]\s*([^\n\r]{2,20})',
        ]
        
        for pattern in author_patterns:
            match = re.search(pattern, content[:1000])
            if match:
                author = match.group(1).strip()
                # 清理作者名
                author = re.sub(r'[\s\n\r]+', '', author)
                if 2 <= len(author) <= 20:
                    return author
        
        return ''
    
    def _read_file_content(self, file_path, max_chars=10000):
        """读取文件内容"""
        try:
            # 尝试不同的编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'big5']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read(max_chars)
                        return content
                except UnicodeDecodeError:
                    continue
            
            logging.warning(f"无法读取文件内容: {file_path}")
            return ''
            
        except Exception as e:
            logging.debug(f"读取文件失败: {e}")
            return ''
    
    def extract_content_preview(self, file_path, max_length=500):
        """提取文件内容预览"""
        try:
            content = self._read_file_content(file_path, max_chars=max_length * 2)
            if not content:
                return ''
            
            # 清理内容
            content = content.strip()
            
            # 移除元数据
            content = self._remove_metadata(content)
            
            # 截取预览
            if len(content) > max_length:
                content = content[:max_length] + '...'
            
            return content
            
        except Exception as e:
            logging.debug(f"提取内容预览失败: {e}")
            return ''
    
    def _remove_metadata(self, content):
        """移除文件开头的元数据"""
        lines = content.split('\n')
        clean_lines = []
        
        metadata_keywords = ['作者', '书名', '简介', '内容', '来源', '网站', '更新']
        skip_lines = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # 跳过前几行的元数据
            if i < 10 and any(keyword in line for keyword in metadata_keywords):
                skip_lines = i + 1
                continue
            
            if i >= skip_lines and line:
                clean_lines.append(line)
        
        return '\n'.join(clean_lines)
    
    def _detect_category(self, title, content):
        """
        根据标题和内容自动识别主题分类
        优先级：AI识别 > 关键词识别 > 随机选择
        """
        import random
        
        # 1. 尝试使用AI识别
        if self.config.get('enable_ai_post', False):
            ai_category = self._detect_category_by_ai(title, content)
            if ai_category:
                logging.info(f"AI识别分类: {ai_category}")
                return ai_category
        
        # 2. 降级到关键词识别
        keyword_category = self._detect_category_by_keywords(title, content)
        if keyword_category:
            return keyword_category
        
        # 3. 都失败了，随机选择
        default_categories = ['凌辱虐情', '唯美纯爱', '都市奇缘']
        random_category = random.choice(default_categories)
        logging.info(f"随机选择分类: {random_category}")
        return random_category
    
    def _detect_category_by_ai(self, title, content):
        """使用AI识别分类"""
        try:
            # 检查AI配置
            ai_api_url = self.config.get('ai_api_url', '')
            ai_api_key = self.config.get('ai_api_key', '')
            
            if not ai_api_url or not ai_api_key:
                return None
            
            # 准备AI提示词
            available_categories = [
                '凌辱虐情', '唯美纯爱', '都市奇缘', '女警英雄', 
                '青春校园', '历史古香', '同人衍生', '作者合集', 
                '绿意盎然', '玄幻武侠'
            ]
            
            prompt = f"""请根据以下小说标题和内容预览，从给定的分类中选择最合适的一个。

标题：{title}

内容预览：
{content[:300]}

可选分类：{', '.join(available_categories)}

要求：
1. 只返回分类名称，不要其他内容
2. 必须从可选分类中选择
3. 如果无法判断，返回"无法识别"

分类："""
            
            # 调用AI API
            import requests
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {ai_api_key}'
            }
            
            data = {
                'model': self.config.get('ai_model', 'gpt-3.5-turbo'),
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'max_tokens': 50
            }
            
            # 设置代理
            proxies = None
            if self.config.get('proxy', {}).get('use_for_ai', False):
                http_proxy = self.config.get('proxy', {}).get('http_proxy', '')
                https_proxy = self.config.get('proxy', {}).get('https_proxy', http_proxy)
                if http_proxy:
                    proxies = {
                        'http': http_proxy,
                        'https': https_proxy
                    }
            
            response = requests.post(
                ai_api_url,
                headers=headers,
                json=data,
                proxies=proxies,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                category = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                # 验证返回的分类是否有效
                if category in available_categories:
                    return category
                elif '无法识别' in category:
                    logging.info("AI无法识别分类，降级到关键词识别")
                    return None
            
            return None
            
        except Exception as e:
            logging.debug(f"AI识别失败: {e}")
            return None
    
    def _detect_category_by_keywords(self, title, content):
        """使用关键词检测分类"""
        text = title + ' ' + content
        
        # 分类关键词映射（与旧代码保持一致）
        category_keywords = {
            '玄幻武侠': ['玄幻', '武侠', '修仙', '仙侠', '修真', '异界', '大帝', '圣人', '修炼', '仙朝', '证道', '踏天', '准帝', '道身'],
            '凌辱虐情': ['凌辱', '虐', 'NTR', '调教', '羞辱', '母狗', '淫妇', '乱伦', '肉便器'],
            '绿意盎然': ['NTR', '绿', '出轨', '背叛', '牛头人', '戴绿帽'],
            '青春校园': ['校园', '学生', '青春', '大学', '高中', '学院', '书院'],
            '都市奇缘': ['都市', '现代', '都会', '职场', '豪门', '总裁'],
            '历史古香': ['古代', '历史', '穿越', '宫廷', '武林', '朝廷'],
            '唯美纯爱': ['纯爱', '恋爱', '甜文', '温馨', '治愈', '初恋'],
            '女警英雄': ['女警', '警察', '英雄', '特工', '女侠', '女将'],
            '同人衍生': ['同人', '衍生', '二次创作', '同人文'],
            '作者合集': ['合集', '作品集', '全集', '精选集']
        }
        
        # 检测匹配的分类
        for category_name, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    logging.info(f"关键词识别分类: {category_name} (关键词: {keyword})")
                    return category_name
        
        return None
    
    def post_thread(self, fid, file_path, category_id=None):
        """
        发布新帖子
        :param fid: 版块ID (如: 139)
        :param file_path: 附件文件路径
        :param category_id: 主题分类ID (可选)
        :return: (是否成功, 帖子URL或错误信息)
        """
        try:
            # 0. 验证文件路径
            abs_file_path = os.path.abspath(file_path)
            if not os.path.exists(abs_file_path):
                logging.error(f"文件不存在: {abs_file_path}")
                return False, None
            
            file_path = abs_file_path
            logging.info(f"文件路径: {file_path}")
            
            # 1. 解析文件名
            filename = os.path.basename(file_path)
            title_info = self.parse_filename(filename, file_path)
            logging.debug(f"解析标题: {title_info['full_title']}")
            
            # 2. 提取内容预览
            content_preview = self.extract_content_preview(file_path)
            logging.debug(f"提取内容预览: {len(content_preview)} 字符")
            
            # 3. 访问发帖页面
            post_url = f"{self.base_url}forum.php?mod=post&action=newthread&fid={fid}"
            logging.info(f"访问发帖页面: {post_url}")
            self.page.goto(post_url, wait_until='domcontentloaded')
            time.sleep(3)
            
            # 4. 检查是否达到发帖限额
            page_source = self.page.content()
            if any(keyword in page_source for keyword in [
                '本版块每天限制发主题',
                '请明天再发表', 
                '限制发主题',
                '抱歉，本版块每天限制',
                '每天限制发主题'
            ]):
                logging.warning("=" * 60)
                logging.warning("已达到今日发帖限额")
                logging.info("论坛提示：本版块每天限制发主题数量，请明天再发表")
                logging.warning("=" * 60)
                return False, 'LIMIT_REACHED'
            
            # 5. 等待页面加载
            try:
                self.page.wait_for_selector('input[name="subject"]', timeout=10000)
                logging.info("发帖页面加载完成")
            except PlaywrightTimeout:
                logging.error("发帖页面加载超时")
                return False, None
            
            # 6. 选择主题分类（如果需要）
            if not category_id:
                detected_category = self._detect_category(title_info['full_title'], content_preview)
                if detected_category:
                    self._select_category(detected_category)
            
            # 7. 填写标题
            logging.info("填写标题...")
            subject_input = self.page.locator('input[name="subject"]').first
            subject_input.fill(title_info['full_title'])
            logging.info(f"填写标题: {title_info['full_title']}")
            time.sleep(1)
            
            # 8. 构建帖子内容
            post_content = self._build_post_content(title_info, content_preview, filename)
            
            # 9. 先上传附件（在填写内容之前）
            logging.info("先上传附件，然后再填写内容...")
            upload_success = self._upload_attachment(file_path)
            if not upload_success:
                logging.error("附件上传失败，停止发帖")
                return False, None
            time.sleep(2)  # 等待附件插入完成
            
            # 10. 上传附件后填写内容（这样附件链接会在内容前面）
            logging.info("上传附件后填写内容...")
            self._fill_content(post_content)
            
            # 11. 等待内容同步
            logging.info("等待 3 秒，确保内容完全同步...")
            time.sleep(3)
            
            # 12. 提交发帖（测试模式下跳过）
            logging.debug(f"检查测试模式: self.test_mode={self.test_mode}")
            if self.test_mode:
                logging.info("=" * 60)
                logging.info("测试模式：跳过提交步骤")
                logging.info("所有步骤已完成（未实际发布）")
                logging.info("=" * 60)
                return True, None  # 测试模式返回成功但无URL
            else:
                logging.info("正常模式：准备提交帖子")
                return self._submit_post()
            
        except Exception as e:
            logging.error(f"发帖失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return False, None
    
    def _select_category(self, category_name):
        """选择主题分类"""
        try:
            logging.info(f"准备选择分类: {category_name}")

            # 步骤1: 点击分类下拉触发按钮
            trigger_selectors = [
                "a[onclick*='showMenu'][onclick*='typeid']",
                "a[id*='typeid_menu']",
                "a.showmenu[onclick*='typeid']",
                "#typeid_ctrl",
                "a:has-text('选择主题分类')",
                "span:has-text('选择主题分类')",
            ]

            trigger_clicked = False
            for selector in trigger_selectors:
                try:
                    trigger = self.page.locator(selector).first
                    if trigger.is_visible():
                        trigger.click()
                        logging.info("已点击分类下拉按钮")
                        time.sleep(1.5)
                        trigger_clicked = True
                        break
                except Exception:
                    continue

            if not trigger_clicked:
                logging.warning("未找到分类下拉触发按钮")
                return False

            time.sleep(0.5)

            # 步骤2: 获取所有分类选项文本
            try:
                category_items = self.page.locator("div[id='typeid_ctrl_menu'] li").all()
                if not category_items:
                    category_items = self.page.locator("div[id*='typeid'] li").all()

                if not category_items:
                    logging.warning("未找到任何分类选项")
                    return False

                available_categories = []
                for item in category_items:
                    try:
                        t = item.text_content().strip()
                        if t and t != '选择主题分类':
                            available_categories.append(t)
                    except:
                        pass

                logging.info(f"可用分类: {', '.join(available_categories)}")

                # 步骤3: 匹配目标分类
                clean_name = category_name.replace(' ', '').replace('　', '')
                matched = None
                for cat in available_categories:
                    clean_cat = cat.replace(' ', '').replace('　', '')
                    if (clean_cat == clean_name or clean_name in clean_cat or clean_cat in clean_name):
                        matched = cat
                        break

                if matched:
                    if self._click_category_item(matched):
                        return True

                logging.warning(f"未找到匹配的分类 '{category_name}'")

                # fallback: 随机选一个默认分类
                import random
                for fallback in ['凌辱虐情', '唯美纯爱', '都市奇缘']:
                    if fallback in available_categories:
                        if self._click_category_item(fallback):
                            logging.info(f"随机选择分类: {fallback}")
                            return True
                return False

            except Exception as e:
                logging.warning(f"查找分类选项失败: {e}")
                return False

        except Exception as e:
            logging.warning(f"选择分类失败: {e}")
            return False

    def _click_category_item(self, text):
        """点击指定文本的分类选项"""
        try:
            item = self.page.locator(f"div[id*='typeid'] li a:has-text('{text}')").first
            if item.count() > 0:
                item.click(force=True)
                logging.info(f"已选择分类: {text}")
                time.sleep(1)
                return True
        except:
            pass
        try:
            item = self.page.locator(f"div[id*='typeid'] li:has-text('{text}')").first
            item.click(force=True)
            logging.info(f"已选择分类: {text}")
            time.sleep(1)
            return True
        except:
            pass
        return False

    def _build_post_content(self, title_info, content_preview, filename):
        """构建帖子内容"""
        content_parts = []
        
        # 添加书名和作者信息
        if title_info.get('title'):
            content_parts.append(f"[b]书名：[/b]{title_info['title']}")
        
        if title_info.get('author'):
            content_parts.append(f"[b]作者：[/b]{title_info['author']}")
        
        if title_info.get('chapters'):
            content_parts.append(f"[b]章节：[/b]{title_info['chapters']}")
        
        # 添加分隔线
        content_parts.append("\n" + "=" * 50 + "\n")
        
        # 添加内容预览
        if content_preview:
            content_parts.append("[b]内容预览：[/b]\n")
            content_parts.append(content_preview)
        
        # 添加附件说明
        content_parts.append("\n\n" + "=" * 50)
        content_parts.append(f"\n[b]附件：[/b]{filename}")
        content_parts.append("\n[color=red]完整内容请下载附件查看[/color]")
        
        return '\n'.join(content_parts)
    
    def _fill_content(self, content):
        """填写帖子内容（操作iframe中的body元素）"""
        try:
            logging.info(f"准备填写内容，长度: {len(content)} 字符")
            logging.debug(f"内容预览: {content[:100]}...")
            
            # 使用JavaScript操作iframe中的body元素
            result = self.page.evaluate("""
                (newContent) => {
                    // 尝试多种方式查找iframe
                    let iframe = document.getElementById('iframe_bodyhtml');
                    if (!iframe) {
                        iframe = document.querySelector('iframe[id*="body"]');
                    }
                    if (!iframe) {
                        iframe = document.querySelector('iframe[name*="body"]');
                    }
                    if (!iframe) {
                        const iframes = document.querySelectorAll('iframe');
                        if (iframes.length > 0) {
                            iframe = iframes[0];
                        }
                    }
                    
                    if (iframe) {
                        try {
                            const doc = iframe.contentDocument || iframe.contentWindow.document;
                            const body = doc.body;
                            
                            if (body) {
                                // 获取当前内容
                                const currentContent = body.innerHTML || '';
                                
                                // 追加新内容（转换换行符为<br>）
                                const htmlContent = newContent.replace(/\\n/g, '<br>');
                                
                                if (currentContent.trim().length > 0) {
                                    body.innerHTML = currentContent + '<br><br>' + htmlContent;
                                } else {
                                    body.innerHTML = htmlContent;
                                }
                                
                                // 触发事件
                                try {
                                    const event = new Event('input', { bubbles: true });
                                    body.dispatchEvent(event);
                                } catch(e) {}
                                
                                return {
                                    success: true,
                                    iframe_id: iframe.id,
                                    currentLength: currentContent.length,
                                    finalLength: body.innerHTML.length,
                                    preview: body.innerText.substring(0, 100)
                                };
                            }
                        } catch(e) {
                            return {success: false, error: 'cannot access iframe: ' + e.message};
                        }
                    }
                    return {success: false, error: 'iframe not found'};
                }
            """, content)
            
            if result and result.get('success'):
                logging.info(f"填写内容成功（iframe方式）")
                logging.debug(f"   Iframe ID: {result.get('iframe_id')}")
                logging.debug(f"   原内容: {result.get('currentLength')} 字符")
                logging.debug(f"   最终: {result.get('finalLength')} 字符")
                logging.debug(f"   预览: {result.get('preview')}...")
                time.sleep(2)
                return True
            else:
                error_msg = result.get('error') if result else 'unknown error'
                logging.error(f"填写内容失败: {error_msg}")
                return False
            
        except Exception as e:
            logging.error(f"填写内容失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return False
    
    def _upload_attachment(self, file_path):
        """上传附件 - 完整流程：点击附件 -> 上传文件 -> 插入附件 -> 确定"""
        try:
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            logging.info(f"开始上传附件: {filename} ({file_size/1024/1024:.2f} MB)")
            logging.info("=" * 60)
            
            # 步骤1: 点击附件按钮打开上传对话框
            logging.info("步骤1: 点击附件按钮")
            try:
                attach_btn = self.page.locator("a[id*='attach']").first
                attach_btn.click()
                time.sleep(2)
                logging.info("附件对话框已打开")
            except Exception as e:
                logging.error(f"点击附件按钮失败: {e}")
                return False
            
            # 步骤2: 定位文件输入框并上传
            logging.info("步骤2: 上传文件")
            try:
                # 查找文件输入框（多种方式）
                file_input = None
                input_selectors = [
                    'input[type="file"][accept*="txt"]',
                    'input[type="file"][name="Filedata"]',
                    'input[type="file"].filedata',
                    'input[type="file"]'
                ]
                
                for selector in input_selectors:
                    try:
                        file_input = self.page.locator(selector).first
                        if file_input.count() > 0:
                            logging.debug(f"找到文件输入框: {selector}")
                            break
                    except:
                        continue
                
                if not file_input:
                    logging.error("未找到文件输入框")
                    return False
                
                # 上传文件
                file_input.set_input_files(file_path)
                logging.info("文件已选择")
                
                # 等待上传完成（根据文件大小）
                file_size_mb = file_size / (1024 * 1024)
                wait_seconds = max(10, min(60, int(file_size_mb * 3)))
                logging.info(f"等待上传完成 ({wait_seconds} 秒)...")
                time.sleep(wait_seconds)
                
            except Exception as e:
                logging.error(f"上传文件失败: {e}")
                return False
            
            # 步骤3: 插入附件到帖子内容
            logging.info("步骤3: 插入附件到帖子内容")
            insert_clicked = False
            
            try:
                time.sleep(2)  # 等待文件列表更新
                
                # 方法1: 点击"插入全部附件"按钮
                insert_all_selectors = [
                    "text=插入全部附件",
                    "text=插入全部",
                    "a:has-text('插入全部附件')",
                    "button:has-text('插入全部附件')"
                ]
                
                for selector in insert_all_selectors:
                    try:
                        btn = self.page.locator(selector).first
                        if btn.is_visible():
                            btn.click()
                            logging.info("点击'插入全部附件'按钮成功")
                            insert_clicked = True
                            time.sleep(1)
                            break
                    except:
                        continue
                
                # 方法2: 如果没有"插入全部附件"，点击文件名
                if not insert_clicked:
                    filename_short = filename[:30]
                    filename_selectors = [
                        f"text={filename_short}",
                        f"a:has-text('{filename_short}')"
                    ]
                    
                    for selector in filename_selectors:
                        try:
                            link = self.page.locator(selector).first
                            if link.is_visible():
                                link.click()
                                logging.info("点击文件名成功")
                                insert_clicked = True
                                time.sleep(1)
                                break
                        except:
                            continue
                
            except Exception as e:
                logging.warning(f"插入附件失败: {e}")
            
            if insert_clicked:
                logging.info("附件已插入到帖子内容")
            else:
                logging.warning("未能插入附件，继续执行...")
            
            # 步骤4: 点击确定按钮关闭对话框
            logging.info("步骤4: 点击确定按钮关闭对话框")
            confirm_clicked = False
            
            try:
                time.sleep(1)
                
                # 查找确定按钮
                confirm_selectors = [
                    '#attach_confirm',
                    'button.pn.pnc:has-text("确定")',
                    'button:has-text("确定")',
                    'text=确定'
                ]
                
                for selector in confirm_selectors:
                    try:
                        btn = self.page.locator(selector).first
                        if btn.is_visible():
                            btn.click()
                            logging.info("确定按钮已点击")
                            confirm_clicked = True
                            time.sleep(2)
                            break
                    except:
                        continue
                
                if not confirm_clicked:
                    logging.warning("未找到确定按钮，尝试强制关闭对话框")
                    # 强制关闭对话框
                    self.page.evaluate("""
                        () => {
                            const modals = document.querySelectorAll('div[id*="attach"], div[class*="dialog"]');
                            modals.forEach(m => m.style.display = 'none');
                            const overlays = document.querySelectorAll('div[class*="overlay"], div[class*="mask"]');
                            overlays.forEach(o => o.style.display = 'none');
                        }
                    """)
                    time.sleep(1)
                    
            except Exception as e:
                logging.warning(f"关闭对话框失败: {e}")
            
            # 步骤5: 验证上传成功
            logging.info("步骤5: 验证上传成功")
            try:
                time.sleep(1)
                
                # 检查页面中是否有附件标识
                has_attachment = self.page.evaluate(f"""
                    () => {{
                        const hasAttachId = document.querySelector('[id*="attach_"]') !== null;
                        const hasAttachList = document.querySelector('[id*="attachlist"]') !== null;
                        const hasFilename = document.body.innerHTML.includes('{filename}');
                        return hasAttachId || hasAttachList || hasFilename;
                    }}
                """)
                
                if has_attachment:
                    logging.info("附件上传成功")
                    logging.info("=" * 60)
                    return True
                else:
                    logging.warning("附件可能未上传成功")
                    logging.info("=" * 60)
                    return False
                    
            except Exception as e:
                logging.warning(f"验证失败: {e}")
                logging.info("=" * 60)
                return False
            
        except Exception as e:
            logging.error(f"上传附件失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            logging.info("=" * 60)
            return False
    
    def _submit_post(self):
        """提交帖子"""
        try:
            logging.info("准备提交帖子...")
            
            # 查找提交按钮
            submit_selectors = [
                'button[name="topicsubmit"]',
                'button[name="postsubmit"]',
                'input[name="topicsubmit"]',
                'input[name="postsubmit"]',
                'button.pn.pnc',
                'button[type="submit"]'
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    btn = self.page.locator(selector).first
                    if btn.is_visible():
                        submit_button = btn
                        logging.info(f"找到提交按钮: {selector}")
                        break
                except:
                    continue
            
            if not submit_button:
                logging.error("未找到提交按钮")
                return False, None
            
            # 点击提交
            submit_button.click()
            logging.info("点击提交按钮")
            
            # 等待页面跳转或加载完成
            logging.info("等待页面响应...")
            try:
                # 等待导航完成（最多15秒）
                self.page.wait_for_load_state('networkidle', timeout=15000)
                logging.debug("页面加载完成")
            except Exception as e:
                logging.debug(f"等待页面加载超时: {e}")
                # 即使超时也继续检查
            
            time.sleep(3)
            
            # 安全地检查URL和页面内容
            try:
                current_url = self.page.url
                logging.debug(f"当前URL: {current_url}")
                
                # 判断成功：URL包含 thread- 或 viewthread
                if "thread-" in current_url or "viewthread" in current_url:
                    logging.info("帖子发布成功！")
                    logging.info(f"帖子URL: {current_url}")
                    return True, current_url
                
                # 尝试获取页面内容（可能失败）
                try:
                    page_source = self.page.content()
                except Exception as e:
                    logging.debug(f"无法获取页面内容: {e}")
                    # 如果无法获取内容，但URL正确，认为成功
                    if "thread-" in current_url or "viewthread" in current_url or "forum.php" in current_url:
                        logging.info("帖子可能已发布成功（根据URL判断）")
                        return True, current_url
                    else:
                        logging.warning("无法确认发布状态")
                        return False, None
                
                # 检查是否达到发帖限额
                if any(keyword in page_source for keyword in [
                    '本版块每天限制发主题',
                    '请明天再发表', 
                    '限制发主题',
                    '抱歉，本版块每天限制',
                    '每天限制发主题'
                ]):
                    logging.warning("=" * 60)
                    logging.warning("已达到今日发帖限额")
                    logging.info("论坛提示：本版块每天限制发主题数量，请明天再发表")
                    logging.warning("=" * 60)
                    return False, 'LIMIT_REACHED'
                
                # 检查是否有其他错误提示
                if any(err in page_source for err in ['请填写', '标题不能为空', '内容不能为空', '发布失败']):
                    logging.error("帖子发布失败：论坛返回错误")
                    logging.error(f"当前URL: {current_url}")
                    return False, None
                
                # 如果URL回到了论坛列表页，可能是成功了
                if "forum.php" in current_url or "forumdisplay" in current_url:
                    logging.info("帖子可能已发布成功（已返回论坛列表）")
                    return True, current_url
                
                # 无法确定状态
                logging.warning("无法确认发布状态")
                logging.warning(f"当前URL: {current_url}")
                logging.debug(f"页面内容预览: {page_source[:500]}")
                return False, None
                
            except Exception as e:
                logging.error(f"检查发布状态失败: {e}")
                # 尝试通过URL判断
                try:
                    current_url = self.page.url
                    if "thread-" in current_url or "viewthread" in current_url or "forum.php" in current_url:
                        logging.info("帖子可能已发布成功（根据URL判断）")
                        return True, current_url
                except:
                    pass
                return False, None
                
        except Exception as e:
            logging.error(f"提交帖子失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return False, None
