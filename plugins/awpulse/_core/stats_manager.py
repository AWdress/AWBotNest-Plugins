"""
统计管理器 - 记录每日回复和签到数据
"""
import json
import os
from datetime import datetime
from typing import Dict, List

class StatsManager:
    def __init__(self, stats_file=None):
        if stats_file is None:
            # 获取项目根目录
            base_dir = os.environ.get('AWPULSE_BASE', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            stats_file = os.path.join(base_dir, 'data', 'stats.json')
        self.stats_file = stats_file
        self.ensure_data_dir()
        self.stats = self.load_stats()
    
    def ensure_data_dir(self):
        """确保数据目录存在"""
        data_dir = os.path.dirname(self.stats_file)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def load_stats(self) -> Dict:
        """加载统计数据"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载统计数据失败: {e}")
                return self.get_default_stats()
        return self.get_default_stats()
    
    def get_default_stats(self) -> Dict:
        """获取默认统计数据结构"""
        return {
            "today": datetime.now().strftime("%Y-%m-%d"),
            "reply_count": 0,
            "post_count": 0,    # 今日发帖数
            "checkin_success": False,
            "checkin_time": None,
            "replies": [],
            "posts": [],        # 今日发帖记录
            "history": [],
            "all_replies": [],  # 保存所有历史回复
            "all_posts": [],    # 保存所有历史发帖
            "user_info": {      # 用户信息
                "user_group": "",
                "credits": 0,
                "money": 0,
                "coins": 0,
                "rating": 0,
                "last_update": None
            },
            "ai_stats": {       # AI调用统计
                "total": {      # 累计统计
                    "reply_generated": 0,    # AI生成回复次数
                    "post_filtered": 0,      # AI帖子过滤次数
                    "errors": 0              # AI调用失败次数
                },
                "today": {      # 今日统计（每天重置）
                    "reply_generated": 0,
                    "post_filtered": 0,
                    "errors": 0
                }
            }
        }
    
    def save_stats(self):
        """保存统计数据（today和total都会保存）"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存统计数据失败: {e}")
    
    def check_and_reset_daily(self):
        """检查并重置每日统计"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.stats.get("today") != today:
            # 保存昨天的数据到历史
            if self.stats.get("reply_count", 0) > 0 or self.stats.get("checkin_success", False):
                history_entry = {
                    "date": self.stats.get("today"),
                    "reply_count": self.stats.get("reply_count", 0),
                    "checkin_success": self.stats.get("checkin_success", False),
                    "checkin_time": self.stats.get("checkin_time"),
                    "replies_summary": len(self.stats.get("replies", []))
                }
                if "history" not in self.stats:
                    self.stats["history"] = []
                self.stats["history"].insert(0, history_entry)
                # 只保留最近30天的历史
                self.stats["history"] = self.stats["history"][:30]
            
            # 重置今日数据
            self.stats["today"] = today
            self.stats["reply_count"] = 0
            self.stats["post_count"] = 0
            self.stats["checkin_success"] = False
            self.stats["checkin_time"] = None
            self.stats["replies"] = []
            self.stats["posts"] = []
            
            # 重置今日AI统计
            if "ai_stats" in self.stats and "today" in self.stats["ai_stats"]:
                self.stats["ai_stats"]["today"] = {
                    "reply_generated": 0,
                    "post_filtered": 0,
                    "errors": 0
                }
            
            self.save_stats()
    
    def add_reply(self, thread_title: str, thread_url: str, reply_content: str):
        """添加回复记录"""
        self.check_and_reset_daily()
        
        reply_record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "title": thread_title,
            "url": thread_url,
            "content": reply_content
        }
        
        if "replies" not in self.stats:
            self.stats["replies"] = []
        if "all_replies" not in self.stats:
            self.stats["all_replies"] = []
        
        # 添加到今日回复
        self.stats["replies"].append(reply_record)
        self.stats["reply_count"] = len(self.stats["replies"])
        
        # 添加到所有回复历史（保留最近1000条）
        self.stats["all_replies"].insert(0, reply_record)
        self.stats["all_replies"] = self.stats["all_replies"][:1000]
        
        self.save_stats()
    
    def mark_checkin_success(self):
        """标记签到成功"""
        self.check_and_reset_daily()
        self.stats["checkin_success"] = True
        self.stats["checkin_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_stats()
    
    def add_post(self, thread_title: str, thread_url: str, file_name: str):
        """添加发帖记录"""
        self.check_and_reset_daily()
        
        post_record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "title": thread_title,
            "url": thread_url,
            "file": file_name
        }
        
        if "posts" not in self.stats:
            self.stats["posts"] = []
        if "all_posts" not in self.stats:
            self.stats["all_posts"] = []
        
        # 添加到今日发帖
        self.stats["posts"].append(post_record)
        self.stats["post_count"] = len(self.stats["posts"])
        
        # 添加到所有发帖历史（保留最近1000条）
        self.stats["all_posts"].insert(0, post_record)
        self.stats["all_posts"] = self.stats["all_posts"][:1000]
        
        self.save_stats()
    
    def get_today_stats(self) -> Dict:
        """获取今日统计"""
        self.check_and_reset_daily()
        return {
            "date": self.stats.get("today"),
            "reply_count": self.stats.get("reply_count", 0),
            "post_count": self.stats.get("post_count", 0),
            "checkin_success": self.stats.get("checkin_success", False),
            "checkin_time": self.stats.get("checkin_time"),
            "replies": self.stats.get("replies", []),
            "posts": self.stats.get("posts", [])
        }
    
    def get_history(self, days: int = 7) -> List[Dict]:
        """获取历史统计"""
        return self.stats.get("history", [])[:days]
    
    def get_all_replies(self, limit: int = 100) -> List[Dict]:
        """获取所有历史回复"""
        all_replies = self.stats.get("all_replies", [])
        return all_replies[:limit]
    
    def get_all_posts(self, limit: int = 100) -> List[Dict]:
        """获取所有历史发帖"""
        all_posts = self.stats.get("all_posts", [])
        return all_posts[:limit]
    
    def get_all_stats(self) -> Dict:
        """获取完整统计数据"""
        self.check_and_reset_daily()
        return {
            "today": self.get_today_stats(),
            "history": self.get_history(),
            "all_replies": self.get_all_replies(100),
            "all_posts": self.get_all_posts(100),
            "user_info": self.get_user_info()
        }
    
    def update_user_info(self, user_group: str = "", credits: int = 0, money: int = 0, coins: int = 0, rating: int = 0):
        """更新用户信息"""
        if "user_info" not in self.stats:
            self.stats["user_info"] = {}
        
        self.stats["user_info"]["user_group"] = user_group
        self.stats["user_info"]["credits"] = credits
        self.stats["user_info"]["money"] = money
        self.stats["user_info"]["coins"] = coins
        self.stats["user_info"]["rating"] = rating
        self.stats["user_info"]["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.save_stats()
    
    def get_user_info(self) -> Dict:
        """获取用户信息"""
        default_info = {
            "user_group": "",
            "credits": 0,
            "money": 0,
            "coins": 0,
            "rating": 0,
            "last_update": None
        }
        return self.stats.get("user_info", default_info)
    
    def ensure_ai_stats(self):
        """确保AI统计结构存在"""
        if "ai_stats" not in self.stats:
            self.stats["ai_stats"] = {}
        
        # 确保 total 存在（累计统计，永久保存）
        if "total" not in self.stats["ai_stats"]:
            self.stats["ai_stats"]["total"] = {"reply_generated": 0, "post_filtered": 0, "errors": 0}
        else:
            # 确保所有键存在
            if "reply_generated" not in self.stats["ai_stats"]["total"]:
                self.stats["ai_stats"]["total"]["reply_generated"] = 0
            if "post_filtered" not in self.stats["ai_stats"]["total"]:
                self.stats["ai_stats"]["total"]["post_filtered"] = 0
            if "errors" not in self.stats["ai_stats"]["total"]:
                self.stats["ai_stats"]["total"]["errors"] = 0
        
        # 确保 today 存在（今日统计）
        if "today" not in self.stats["ai_stats"]:
            self.stats["ai_stats"]["today"] = {"reply_generated": 0, "post_filtered": 0, "errors": 0}
        else:
            # 确保所有键存在
            if "reply_generated" not in self.stats["ai_stats"]["today"]:
                self.stats["ai_stats"]["today"]["reply_generated"] = 0
            if "post_filtered" not in self.stats["ai_stats"]["today"]:
                self.stats["ai_stats"]["today"]["post_filtered"] = 0
            if "errors" not in self.stats["ai_stats"]["today"]:
                self.stats["ai_stats"]["today"]["errors"] = 0
    
    def record_ai_reply(self):
        """记录AI生成回复"""
        self.ensure_ai_stats()
        self.stats["ai_stats"]["today"]["reply_generated"] += 1
        self.stats["ai_stats"]["total"]["reply_generated"] += 1
        self.save_stats()
    
    def record_ai_filter(self):
        """记录AI帖子过滤"""
        self.ensure_ai_stats()
        self.stats["ai_stats"]["today"]["post_filtered"] += 1
        self.stats["ai_stats"]["total"]["post_filtered"] += 1
        self.save_stats()
    
    def record_ai_error(self):
        """记录AI调用失败"""
        self.ensure_ai_stats()
        self.stats["ai_stats"]["today"]["errors"] += 1
        self.stats["ai_stats"]["total"]["errors"] += 1
        self.save_stats()
    
    def get_ai_stats(self) -> Dict:
        """获取AI调用统计"""
        self.ensure_ai_stats()
        return self.stats.get("ai_stats", {
            "total": {"reply_generated": 0, "post_filtered": 0, "errors": 0},
            "today": {"reply_generated": 0, "post_filtered": 0, "errors": 0}
        })

