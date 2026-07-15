# -*- coding: utf-8 -*-
"""回复 Mixin: 论坛帖子获取、智能回复生成、回复提交"""

import json
import logging
import os
import random
import re
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from .human_simulation import human_like_delay, random_scroll, random_mouse_movement


class ReplyMixin:
    """论坛帖子获取、跳过判断、智能回复、回复提交"""

    def get_forum_posts(self, forum_id="fid=141", max_posts=20, test_mode=False):
        """获取论坛帖子列表"""
        try:
            forum_url = f"{self.base_url}forum.php?mod=forumdisplay&{forum_id}"
            forum_name = self.forum_names.get(forum_id, forum_id)
            
            logging.info("=" * 60)
            logging.info(f"获取帖子列表: {forum_name}")
            logging.info(f"URL: {forum_url}")
            logging.info("=" * 60)
            
            self.page.goto(forum_url, wait_until='domcontentloaded')
            
            # 等待页面加载（测试模式使用更短延迟）
            if test_mode:
                time.sleep(1)
            else:
                time.sleep(3)
            
            # 随机滚动页面
            random_scroll(self.page, times=random.randint(1, 2), test_mode=test_mode)
            
            # 获取所有帖子链接 - 同时匹配 thread- 和 tid=
            post_links = []
            
            # 兼容不同帖子链接格式
            elements = self.page.locator("a[href*='thread-'], a[href*='tid=']").all()
            
            logging.debug(f"找到 {len(elements)} 个链接元素，开始解析...")
            
            seen_tids = set()  # 用于去重
            
            for idx, element in enumerate(elements):
                if len(post_links) >= max_posts:
                    break
                
                try:
                    href = element.get_attribute('href')
                    title = element.text_content().strip()
                    
                    if not href or not title or 'thread' not in href:
                        continue
                    
                    # 提取 tid 进行去重
                    import re
                    tid_match = re.search(r'tid[=-](\d+)', href)
                    if tid_match:
                        tid = tid_match.group(1)
                        if tid in seen_tids:
                            continue  # 跳过重复的帖子
                        seen_tids.add(tid)
                        
                        # 清理 URL
                        clean_url = re.sub(r'&page=\d+', '', href)
                        clean_url = re.sub(r'&extra=.*', '', clean_url)
                        
                        # 处理相对路径
                        if clean_url.startswith('/'):
                            clean_url = self.base_url.rstrip('/') + clean_url
                        elif not clean_url.startswith('http'):
                            clean_url = self.base_url + clean_url
                        
                        post_links.append({
                            'url': clean_url,
                            'title': title,
                            'tid': tid
                        })
                        
                        logging.debug(f"找到帖子 {len(post_links)}: {title[:30]}...")
                        
                except Exception as e:
                    logging.debug(f"提取元素失败: {e}")
                    continue
            
            logging.debug(f"找到 {len(post_links)} 个有效帖子")
            
            if not post_links:
                logging.warning("未找到帖子")
                
                # 保存调试信息
                try:
                    debug_dir = os.path.join(base_dir, 'debug')
                    os.makedirs(debug_dir, exist_ok=True)
                    
                    # 保存截图
                    self.page.screenshot(path=os.path.join(debug_dir, 'forum_no_posts.png'))
                    
                    # 保存 HTML
                    with open(os.path.join(debug_dir, 'forum_page.html'), 'w', encoding='utf-8') as f:
                        f.write(self.page.content())
                    
                    # 保存所有链接信息用于调试
                    all_links = []
                    for elem in self.page.locator('a').all()[:50]:  # 只取前50个
                        try:
                            href = elem.get_attribute('href')
                            text = elem.text_content().strip()
                            if href:
                                all_links.append(f"{text[:50]} -> {href}")
                        except:
                            pass
                    
                    with open(os.path.join(debug_dir, 'forum_links.txt'), 'w', encoding='utf-8') as f:
                        f.write('\n'.join(all_links))
                    
                    logging.info("已保存调试信息到 debug/ 目录")
                except Exception as e:
                    logging.debug(f"保存调试信息失败: {e}")
                
                return []
            
            logging.debug(f"找到 {len(post_links)} 个帖子")
            
            # 过滤帖子
            filtered_posts = []
            for post in post_links:
                if not self.should_skip_post(post['title'], post['url']):
                    filtered_posts.append(post)
            
            logging.info(f"过滤后剩余 {len(filtered_posts)} 个帖子")
            
            return filtered_posts[:max_posts]
            
        except Exception as e:
            logging.error(f"获取帖子列表失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return []
    
    def should_skip_post(self, title, post_url="", check_replied=True):
        """判断是否应该跳过该帖子"""
        # 检查关键词
        for keyword in self.skip_keywords:
            if keyword in title:
                logging.info(f"跳过（关键词匹配）: {title}")
                return True
        
        # 检查前缀
        for prefix in self.skip_prefixes:
            if title.startswith(prefix):
                logging.info(f"跳过（前缀匹配）: {title}")
                return True
        
        # 检查是否已回复
        if check_replied:
            all_replies = self.stats.get_all_replies(limit=1000)
            replied_urls = [reply['url'] for reply in all_replies]
            if post_url in replied_urls:
                logging.info(f"跳过（已回复）: {title}")
                return True
        
        return False
    
    def get_smart_reply(self, title, content=""):
        """根据帖子标题和内容生成纯色情风格回复"""
        if not self.enable_smart_reply:
            return random.choice(self.reply_templates)
        
        # 优先尝试使用AI生成回复
        if self.ai_service.is_enabled():
            ai_reply = self.ai_service.generate_reply(title, content)
            if ai_reply:
                # 检查是否需要跳过（由调用方统一打印跳过日志）
                if ai_reply in ['SKIP_FISHING_POST', 'SKIP_ADMIN_POST', 'SKIP_POST']:
                    return ai_reply

                # 检查AI是否拒绝生成内容
                reject_keywords = [
                    '抱歉，我无法', '抱歉，我不能', '我无法满足', '我不能满足',
                    '无法提供', '不能提供', '违反',
                    'sorry', "can't help", "cannot help", 'unable to', 'i refuse'
                ]
                is_reject = any(keyword in ai_reply.lower() for keyword in reject_keywords)

                if is_reject:
                    logging.warning(f"AI拒绝生成内容，降级使用规则回复")
                    try:
                        self.stats.record_ai_error()
                    except:
                        pass
                else:
                    try:
                        self.stats.record_ai_reply()
                    except:
                        pass
                    return ai_reply
            else:
                logging.warning("AI回复失败，降级使用规则回复")
                try:
                    self.stats.record_ai_error()
                except:
                    pass
        
        # AI未启用或失败时，使用规则生成回复
        # 尝试从外部 JSON 加载规则（优先），否则用内置模板
        external_reply = self._try_external_reply_rules(title, content)
        if external_reply:
            return external_reply

        # 内置规则回复（fallback）
        # 合并标题和内容
        full_text = title + " " + content
        import re
        
        # 提取明星名字（中国明星优先）
        star_name = ""
        
        # 中国明星名字列表
        chinese_stars = [
            '刘亦菲', '杨幂', '赵丽颖', '古力娜扎', '迪丽热巴', 
            '范冰冰', '杨颖', 'Angelababy', '唐嫣', '郑爽',
            '关晓彤', '欧阳娜娜', '宋茜', '倪妮', '周冬雨',
            '刘诗诗', '高圆圆', '林志玲', '舒淇', '徐若瑄'
        ]
        
        for star in chinese_stars:
            if star in full_text:
                star_name = star
                break
        
        # 如果没找到中国明星，尝试提取日本女优名字
        if not star_name:
            # 日本女优名字模式
            jp_patterns = [
                r'[^\x00-\xff]{2,5}(?:かな|なるみ|みゆ|結衣|美穂|百合香)',
                r'京野結衣|森沢かな|綾瀬なるみ|鳳みゆ|沢北みなみ|川北メイサ|三宮つばき|葵百合香'
            ]
            for pattern in jp_patterns:
                name_match = re.search(pattern, title)
                if name_match:
                    star_name = name_match.group(0)
                    break
        
        # 详细特征检测
        has_高清 = any(x in full_text for x in ['4K', '8K', '1080P', '2160P', 'HEVC', '高清', '原档'])
        
        # 身材细节特征
        has_巨乳 = any(x in full_text for x in ['巨乳', '爆乳', '大奶', 'G罩杯', 'H罩杯', 'I罩杯', '大きな'])
        has_美腿 = any(x in full_text for x in ['美腿', '长腿', '美脚', '腿'])
        has_翘臀 = any(x in full_text for x in ['翘臀', '美臀', '屁股', 'お尻'])
        has_细腰 = any(x in full_text for x in ['细腰', '小蛮腰', 'A4腰', '纤腰'])
        has_嫩 = any(x in full_text for x in ['嫩', '粉嫩', '少女', '清纯'])
        has_紧 = any(x in full_text for x in ['激狭', '狭', '紧', '紧致', 'マ◯コ', 'きつい'])
        has_湿润 = any(x in full_text for x in ['湿', '濡れ', '潮吹', '喷水'])
        
        # 性格特征
        has_淫荡 = any(x in full_text for x in ['淫荡', '骚', '浪', '淫乱', 'エロい'])
        has_可爱 = any(x in full_text for x in ['可爱', 'かわいい', '愛嬌', '甜美'])
        
        # 内容特征
        has_无码 = '无码' in full_text
        has_VR = 'VR' in full_text
        has_中出 = any(x in full_text for x in ['中出', '内射', '射精'])
        has_多P = any(x in full_text for x in ['3P', '4P', '多P', '群交', '輪姦'])
        has_口交 = any(x in full_text for x in ['口交', 'フェラ', '吹箫'])
        has_肛交 = any(x in full_text for x in ['肛交', 'アナル', '后入'])
        has_AI换脸 = any(x in full_text for x in ['AI换脸', 'AI增强', 'deepfake', 'Deepfake'])
        has_明星 = any(x in full_text for x in ['刘亦菲', '杨幂', '赵丽颖', '古力娜扎', '迪丽热巴', '明星'])
        
        # 构建有文采的色情回复（参考示例风格）
        reply_sentences = []
        
        # 根据特征构建描述性句子
        
        # 紧致特征（100个回复）
        if has_紧:
            tight_phrases = [
                "激狭美穴让人心痒难耐，真想亲身体验那种紧致的快感",
                "那紧致的小穴一定爽到爆，想狠狠插进去感受",
                "光是想象那紧窄的感觉就让人欲罢不能",
                "紧致的蜜穴肯定能把鸡巴夹得死死的，太爽了",
                "紧窄的小逼插进去肯定爽翻天",
                "激狭名器，想插进去感受那极致的包裹感",
                "这么紧的屄，进去肯定夹得很舒服",
                "紧致蜜穴，每次抽插都能爽到头皮发麻",
                "狭窄小穴太诱人了，想狠狠贯穿",
                "那种紧致感想想就硬了，太想操了"
            ]
            reply_sentences.append(random.choice(tight_phrases))
        
        # 巨乳特征（100个回复）
        if has_巨乳:
            breast_phrases = [
                "那对巨乳摇曳的样子肯定很诱人，想狠狠揉捏",
                "大奶子晃来晃去太刺激了，忍不住想埋进去",
                "丰满的胸部让人食指大动，真想好好玩弄一番",
                "爆乳太诱人了，想边插边抓着那对大奶",
                "奶子又大又软，想狠狠揉搓",
                "巨乳在身下摇晃的景象肯定很爽",
                "大波霸看着就想含在嘴里吸",
                "丰满巨乳，想埋进去窒息而亡",
                "奶子这么大，乳交肯定很舒服",
                "波涛汹涌，看着就想上手揉"
            ]
            reply_sentences.append(random.choice(breast_phrases))
        
        # 美腿特征（100个回复）
        if has_美腿:
            leg_phrases = [
                "那双美腿修长诱人，真想架在肩上好好操",
                "美腿太性感了，想边抚摸边深入",
                "看着那双腿就硬了，想舔遍每一寸",
                "纤细的美腿缠上来肯定很爽",
                "大长腿太诱人，想分开狠狠插",
                "美腿玩年，想从脚趾舔到大腿根",
                "这腿又长又直，想架在肩上狂操",
                "美腿太骚了，想边舔边插",
                "修长美腿，想让她用腿夹着我",
                "腿这么美，想把玩一整晚"
            ]
            reply_sentences.append(random.choice(leg_phrases))
        
        # 嫩/粉嫩特征（100个回复）
        if has_嫩:
            tender_phrases = [
                "粉嫩的小穴一看就很敏感，轻轻一碰就出水",
                "嫩得让人想温柔疼爱，又想狠狠蹂躏",
                "粉嫩嫩的屄水肯定很多，想舔个够",
                "看着那粉嫩的小逼就想狠狠插入",
                "嫩屄太诱人，想慢慢品尝那青涩的味道",
                "粉嫩小穴，插进去肯定嫩滑湿润",
                "嫩得出水，想好好疼爱这小骚货",
                "粉粉嫩嫩的，看着就想舔",
                "嫩逼太骚了，想狠狠开苞",
                "粉嫩美穴，想温柔插入感受那紧致"
            ]
            reply_sentences.append(random.choice(tender_phrases))
        
        # 湿润/潮吹特征（100个回复）
        if has_湿润:
            wet_phrases = [
                "淫水泛滥的样子太骚了，想舔干净",
                "潮吹喷得到处都是的景象光想就硬了",
                "那湿润的蜜穴肯定水声很大",
                "屄水流得满床都是，太淫荡了",
                "湿淋淋的小穴太诱人",
                "潮吹的瞬间最刺激",
                "淫水直流，想舔个够",
                "湿透的样子太骚浪",
                "潮喷画面太刺激",
                "屄水多得流出来"
            ]
            reply_sentences.append(random.choice(wet_phrases))
        
        # 明星/女优名字特征
        if star_name:
            # 区分是中国明星还是日本女优
            is_chinese = star_name in chinese_stars
            
            if is_chinese:
                # 中国明星专用回复
                star_phrases = [
                    f"{star_name}的脸太美了，看着被操的样子简直绝了",
                    f"终于能看到{star_name}被狂操的样子，AI技术万岁",
                    f"{star_name}这种女神级的，想象着操她就硬了",
                    f"看{star_name}被插的样子太爽了，虽然是换脸也很带劲"
                ]
            else:
                # 日本女优专用回复
                star_phrases = [
                    f"{star_name}的身体太诱人了，想好好品尝",
                    f"就喜欢{star_name}这种骚浪的，叫床声肯定很撩人",
                    f"{star_name}真是极品，想和她来一发",
                    f"看{star_name}的表演就能射，太他妈骚了"
                ]
            reply_sentences.append(random.choice(star_phrases))
        
        # 无码特征（100个回复）
        if has_无码:
            uncensored_phrases = [
                "无码看得一清二楚，连屄毛都看得见",
                "无码真爽，能清楚看到鸡巴插入的每个细节",
                "就爱看无码的，有码根本不够劲",
                "无码高清，屄的每个褶皱都看得清清楚楚",
                "无码才是王道，看着鸡巴进出太爽了",
                "无码看着真实，插入的感觉看得一清二楚",
                "就喜欢无码的，能看清逼穴被撑开的样子",
                "无码画质，连阴蒂都看得清清楚楚",
                "无马赛克真爽，小穴被插得变形都看得见",
                "无码就是好，屄水流出来都看得清"
            ]
            reply_sentences.append(random.choice(uncensored_phrases))
        
        # 中出特征（100个回复）
        if has_中出:
            creampie_phrases = [
                "中出内射最刺激，看着精液流出来太爽了",
                "就爱看中出，射在里面的感觉一定爽翻",
                "内射画面太带感了，想象自己也射进去",
                "中出最爽，看着精液从逼里流出来硬了",
                "内射瞬间太刺激，想狠狠射满她",
                "就喜欢中出结局，看着精液溢出太爽",
                "射在里面的画面绝了，想感受那温热",
                "中出才够劲，看着被灌满的样子硬了",
                "内射深处，想把精液全射进去",
                "中出画面太刺激，看着就想射"
            ]
            reply_sentences.append(random.choice(creampie_phrases))
        
        # 多P特征（100个回复）
        if has_多P:
            group_phrases = [
                "多P场面太刺激了，几根鸡巴同时插肯定爽爆",
                "群交看着就硬，这种淫乱场面我最爱",
                "被轮流操的样子太淫荡了，骚货",
                "3P画面太刺激，前后一起插肯定爽翻",
                "群P太淫乱，看着几个男人轮流上硬了",
                "多人运动最带劲，看着就想加入",
                "轮奸场景太刺激，一个接一个操真骚",
                "群交淫乱，看着被多根鸡巴填满太爽",
                "多P最爽，各种姿势各种插",
                "被几个男人同时玩弄，骚屄一个"
            ]
            reply_sentences.append(random.choice(group_phrases))
        
        # AI换脸/明星特征（100个回复）
        if has_AI换脸 or has_明星:
            ai_phrases = [
                "AI换脸技术太牛了，看着和真的一样，撸得更带劲",
                "换脸换得真像，想象着操女神的感觉太爽了",
                "AI技术真是造福宅男，终于能看到女神被操了",
                "换脸效果太逼真了，看着明星被狂操心里爽翻",
                "科技改变生活，AI让我们能看到平时看不到的画面",
                "AI技术万岁，女神终于肯下海了",
                "换脸太真实，看着女神被插就硬了",
                "AI增强版画质更清晰，看得更爽",
                "deepfake技术绝了，满足了所有幻想",
                "看着女神被操的样子，AI技术真牛逼"
            ]
            reply_sentences.append(random.choice(ai_phrases))
        
        # 如果没有明显特征，添加通用描述（200个回复）
        if not reply_sentences:
            general_sexy_phrases = [
                "看着那骚浪的样子就想狠狠插进去，操到她求饶",
                "淫荡的表情太勾人了，真想好好调教一番",
                "骚屄一个，看着那浪样就知道很会叫床",
                "这种骚货最好操了，肯定水很多",
                "看得鸡巴硬邦邦的，恨不得马上操进去",
                "骚浪贱，看着就想狠狠蹂躏",
                "淫荡小骚货，想操得她欲仙欲死",
                "这身材太顶了，想从头玩到尾",
                "骚到骨子里了，想好好品尝",
                "淫娃一个，看着就想狂操不止"
            ]
            reply_sentences.append(random.choice(general_sexy_phrases))
        
        # 随机选择1-2个句子组合
        if len(reply_sentences) > 1:
            num_sentences = random.randint(1, min(2, len(reply_sentences)))
            selected = random.sample(reply_sentences, k=num_sentences)
            reply = "，".join(selected) + "！"
        else:
            reply = reply_sentences[0] + "！"
        
        logging.info(f"智能回复 - 特征: 紧={has_紧}, 巨乳={has_巨乳}, 美腿={has_美腿}, 嫩={has_嫩}, 无码={has_无码}")
        
        return reply

    def _try_external_reply_rules(self, title, content):
        """尝试从 config/reply_rules.json 加载规则生成回复，文件不存在则返回 None"""
        try:
            # 平台插件模式：优先用注入配置里的 reply_rules；否则回退 config/reply_rules.json
            rules = self.config.get('reply_rules') if isinstance(getattr(self, 'config', None), dict) else None
            if not rules:
                base_dir = os.environ.get('AWPULSE_BASE', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                rules_file = os.path.join(base_dir, 'config', 'reply_rules.json')
                if not os.path.exists(rules_file):
                    return None
                with open(rules_file, 'r', encoding='utf-8') as f:
                    rules = json.load(f)

            full_text = title + " " + content
            features = rules.get('features', {})
            sentences = []

            for feat_data in features.values():
                keywords = feat_data.get('keywords', [])
                replies = feat_data.get('replies', [])
                if replies and any(kw in full_text for kw in keywords):
                    sentences.append(random.choice(replies))

            if not sentences:
                fallback = rules.get('generic_fallback', [])
                if fallback:
                    return random.choice(fallback)
                return None

            num = min(len(sentences), random.randint(1, 2))
            selected = random.sample(sentences, k=num)
            return "，".join(selected) + "！"
        except Exception:
            return None

    def reply_to_post(self, post_url, reply_content=None, post_title="", test_mode=False):
        """回复帖子"""
        try:
            import re as _re
            tid_match = _re.search(r'tid[=](\d+)', post_url)
            short_url = f"tid={tid_match.group(1)}" if tid_match else post_url
            title_display = f"[{post_title}] " if post_title else ""
            if test_mode:
                logging.info(f"[测试] 回复帖子 {title_display}({short_url})")
            else:
                logging.info(f"回复帖子 {title_display}({short_url})")
            
            # 添加随机延迟（测试模式使用更短延迟）
            if test_mode:
                delay = random.randint(1, 2)
                logging.info(f"[测试] 等待 {delay} 秒后打开帖子...")
            else:
                delay = random.randint(5, 10)
                logging.info(f"等待 {delay} 秒后打开帖子...")
            time.sleep(delay)
            
            # 访问帖子页面
            try:
                self.page.goto(post_url, wait_until='domcontentloaded', timeout=30000)
            except Exception as e:
                logging.warning(f"打开帖子超时，尝试继续...")
                current_url = self.page.url
                if 'viewthread' not in current_url and 'tid=' not in current_url:
                    logging.error("页面未正确加载")
                    return False
                logging.info("页面已部分加载，继续执行...")
            
            # 等待页面加载
            human_like_delay(4, 8, test_mode=test_mode)
            
            # 检查是否被 Cloudflare 拦截
            page_source = self.page.content()
            is_cloudflare_error = (
                ('cloudflare' in page_source.lower() and 'error 1015' in page_source.lower()) or
                ('rate limit' in page_source.lower() and 'you are being rate limited' in page_source.lower())
            )
            
            if is_cloudflare_error:
                logging.error("打开帖子时检测到 Cloudflare 拦截（Error 1015）")
                return False
            
            # 模拟真实用户阅读：随机滚动页面
            random_scroll(self.page, times=random.randint(2, 4), test_mode=test_mode)
            
            # 模拟阅读时间
            human_like_delay(3, 6, test_mode=test_mode)
            
            # 使用智能回复选择内容
            if not reply_content:
                # 尝试获取帖子内容（首楼部分文字）
                post_content = ""
                try:
                    time.sleep(1)
                    
                    # 更完整的选择器列表
                    content_selectors = [
                        ".t_f",
                        ".pcb",
                        "td.t_f",
                        "div.t_f",
                        "[id^='postmessage_']",
                        ".message",
                        ".post_content",
                        ".content"
                    ]
                    
                    for selector in content_selectors:
                        try:
                            element = self.page.locator(selector).first
                            if element.is_visible(timeout=2000):
                                text = element.text_content().strip()
                                if text and len(text) > 10:
                                    post_content = text[:1000]
                                    logging.debug(f"成功读取帖子内容 (选择器: {selector}, 长度: {len(text)})")
                                    break
                        except:
                            continue
                    
                    if not post_content:
                        logging.debug(f"未能读取帖子内容（尝试了 {len(content_selectors)} 个选择器）")
                except Exception as e:
                    logging.debug(f"获取帖子内容失败: {e}")
                
                # 使用标题和内容生成智能回复
                if post_title:
                    reply_content = self.get_smart_reply(post_title, post_content)
                    # 检查是否需要跳过
                    if reply_content in ['SKIP_FISHING_POST', 'SKIP_ADMIN_POST', 'SKIP_POST']:
                        logging.info(f"跳过非资源帖: {post_title[:40]}")
                        return False
                else:
                    reply_content = random.choice(self.reply_templates)
            
            # 查找回复框
            try:
                # 尝试不同的回复框选择器
                reply_selectors = [
                    "textarea[name='message']",
                    "#fastpostmessage",
                    "textarea#e_textarea",
                    "textarea.pt",
                    ".reply_textarea",
                    "textarea"
                ]
                
                reply_box = None
                for selector in reply_selectors:
                    try:
                        elements = self.page.locator(selector).all()
                        for elem in elements:
                            if elem.is_visible() and elem.is_enabled():
                                reply_box = elem
                                logging.info(f"找到回复框: {selector}")
                                break
                        if reply_box:
                            break
                    except Exception as e:
                        logging.debug(f"选择器 {selector} 失败: {e}")
                        continue
                
                if not reply_box:
                    logging.error("找不到回复框")
                    # 保存页面HTML用于调试
                    try:
                        debug_dir = os.path.join(base_dir, 'debug')
                        os.makedirs(debug_dir, exist_ok=True)
                        html_path = os.path.join(debug_dir, 'reply_page_debug.html')
                        with open(html_path, 'w', encoding='utf-8') as f:
                            f.write(self.page.content())
                        logging.info(f"已保存页面HTML到 {html_path}")
                    except:
                        pass
                    return False
                
                # 填写回复内容
                reply_box.fill('')  # 清空
                reply_box.fill(reply_content)
                logging.info(f"填写回复内容: {reply_content}")
                
                # 查找并点击提交按钮（排除搜索按钮）
                submit_selectors = [
                    "input[type='submit'][value*='回复']",
                    "input[type='submit'][value*='发表']",
                    "button[name='replysubmit']",
                    "button[name='topicsubmit']",
                    ".btn_submit"
                ]
                
                submit_button = None
                for selector in submit_selectors:
                    try:
                        buttons = self.page.locator(selector).all()
                        for btn in buttons:
                            if btn.is_visible():
                                btn_name = btn.get_attribute('name') or ''
                                btn_id = btn.get_attribute('id') or ''
                                btn_value = btn.get_attribute('value') or ''
                                btn_text = btn.text_content() or ''
                                
                                # 排除搜索相关按钮
                                if 'search' in btn_name.lower() or 'search' in btn_id.lower():
                                    continue
                                if 'scbar' in btn_id.lower():
                                    continue
                                
                                # 确认是回复按钮
                                if '回复' in btn_value or '发表' in btn_value or '回复' in btn_text or '发表' in btn_text or 'reply' in btn_name.lower():
                                    submit_button = btn
                                    logging.info(f"找到回复提交按钮: {selector}")
                                    break
                        
                        if submit_button:
                            break
                    except:
                        continue
                
                if submit_button:
                    # 测试模式：不实际提交
                    if test_mode:
                        logging.info("[测试] 找到提交按钮，但测试模式不实际提交")
                        logging.info(f"[测试] 回复内容: {reply_content[:100]}...")
                        logging.info("[测试] 回复测试完成（未实际提交）")
                        return True
                    
                    # 正式模式：实际提交
                    # 滚动到按钮位置
                    try:
                        submit_button.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        
                        # 点击提交
                        submit_button.click()
                        logging.info("提交回复")
                        time.sleep(3)
                    except Exception as e:
                        logging.error(f"点击提交按钮失败: {e}")
                        return False
                    
                    # 检查回复是否成功
                    page_source = self.page.content()
                    current_url = self.page.url
                    
                    success_indicators = [
                        "回复发表成功" in page_source,
                        "感谢您的回复" in page_source,
                        "回复成功" in page_source,
                        "发表成功" in page_source,
                        "帖子已提交" in page_source,
                        "tid=" in current_url and "forum.php" in current_url
                    ]
                    
                    if any(success_indicators):
                        if test_mode:
                            logging.info("[测试] 回复成功（测试模式不记录统计）")
                        else:
                            logging.info("回复成功")
                            # 记录回复统计
                            self.stats.add_reply(post_title, post_url, reply_content)
                        return True
                    else:
                        # 保存页面用于调试
                        try:
                            debug_dir = os.path.join(base_dir, 'debug')
                            os.makedirs(debug_dir, exist_ok=True)
                            html_path = os.path.join(debug_dir, 'reply_result_debug.html')
                            with open(html_path, 'w', encoding='utf-8') as f:
                                f.write(page_source)
                            logging.info(f"已保存回复结果页面到 {html_path}")
                        except:
                            pass
                        logging.warning("回复可能失败，请检查调试文件")
                        return False
                else:
                    logging.error("找不到提交按钮")
                    return False
                    
            except Exception as e:
                logging.error(f"回复过程出错: {e}")
                return False
                
        except Exception as e:
            logging.error(f"回复帖子失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return False

    

    def _do_auto_reply(self, today_replies, test_mode=False):
        """执行自动回复，返回本次回复数量"""
        reply_count = 0
        
        for forum_id in self.target_forums:
            if self.stop_flag():
                logging.info("收到停止信号")
                break
            
            # 检查是否达到限额
            if test_mode:
                # 测试模式使用配置的 daily_reply_limit
                if reply_count >= self.daily_reply_limit:
                    logging.info(f"[测试] 已完成 {reply_count} 个测试回复")
                    break
            else:
                # 正常模式检查每日限额
                if today_replies + reply_count >= self.daily_reply_limit:
                    logging.info(f"已达到每日回复限额: {self.daily_reply_limit}")
                    break
            
            # 获取帖子列表
            posts = self.get_forum_posts(
                forum_id=forum_id,
                max_posts=20,
                test_mode=test_mode
            )
            
            if not posts:
                logging.warning(f"论坛 {forum_id} 没有可回复的帖子")
                continue
            
            # 回复帖子
            for post in posts:
                if self.stop_flag():
                    break
                
                # 再次检查限额
                if test_mode:
                    if reply_count >= self.daily_reply_limit:
                        break
                else:
                    if today_replies + reply_count >= self.daily_reply_limit:
                        break
                
                # 回复帖子
                success = self.reply_to_post(
                    post_url=post['url'],
                    post_title=post['title'],
                    test_mode=test_mode
                )
                
                if success:
                    reply_count += 1
                    
                    # 测试模式不记录统计和进度
                    if test_mode:
                        logging.info(f"[测试] 回复测试成功 ({reply_count}/{self.daily_reply_limit})")
                        logging.info("[测试] 跳过回复间隔等待")
                    else:
                        current_total = today_replies + reply_count
                        logging.info(f"今日回复进度: {current_total}/{self.daily_reply_limit}")
                        
                        # 随机延迟
                        if current_total < self.daily_reply_limit:
                            delay = random.randint(self.reply_interval_min, self.reply_interval_max)
                            logging.info(f"等待 {delay} 秒后继续...")
                            time.sleep(delay)
        
        return reply_count
    
