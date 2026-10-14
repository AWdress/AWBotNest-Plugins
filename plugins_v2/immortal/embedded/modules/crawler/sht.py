import datetime
from urllib.parse import urlencode, urljoin, urlsplit
import ipaddress
from pyquery import PyQuery as pq
import re
import bencoder
import hashlib
import binascii

from ...core.config import config_manager
from ...utils import safe_get, safe_post
from ...utils.log import logger
from ...core.runtime import get_runtime


def extract_safeid(html_content):
    doc = pq(html_content)
    for script_elem in doc('script'):
        script_text = pq(script_elem).text().strip()
        if not script_text or 'safeid' not in script_text:
            continue
        match = re.search(r"safeid\s*=\s*['\"]([^'\"]+)['\"]", script_text)
        if match:
            return match.group(1)
    return None


class SHT:
    headers = {}
    cookie = {}
    domain = 'https://sehuatang.org'

    def __init__(self):
        self.headers = {}
        self.cookie = {
            '_safe': ''
        }
        self.mode = "direct"

    def get_original(self, url):
        proxies = {
            "http": config_manager.get().PROXY,
            "https": config_manager.get().PROXY
        }

        logger.info(f"开始请求 (mode={self.mode}): {url}")

        if self.mode == "flaresolverr":
            # 直接走 FlareSolver
            html = self.bypass_cf(url)
            if html is None:
                logger.error(f"FlareSolver 请求失败: {url}")
                return None
        else:
            # 直接请求
            res = safe_get(url, proxies=proxies, cookies=self.cookie, headers=self.headers,
                           allow_redirects=True, timeout=10)
            if res is None:
                logger.error(f"请求失败，返回 None: {url}")
                return None

            html = res.text.encode('utf-8')

            # 被 Cloudflare 拦截 → 切换到 FlareSolver 模式
            doc = pq(html)
            if 'Just a moment' in doc('head>title').text():
                logger.info(f"检测到 Cloudflare 拦截，切换为 FlareSolver 模式: {url}")
                self.mode = "flaresolverr"
                html = self.bypass_cf(url)
                if html is None:
                    logger.error(f"Cloudflare 绕过失败: {url}")
                    return None
                logger.success(f"Cloudflare 绕过成功: {url}")

        # 触发 18 禁确认页
        doc = pq(html)
        if "var safeid" in doc.text():
            logger.info(f"检测到 18 禁确认页，尝试绕过: {url}")
            html = self.bypass_r18(html, url)
            if html is None:
                logger.error(f"18 禁绕过失败: {url}")
                return None
            logger.success(f"18 禁绕过成功: {url}")

        # 最终验证页面标题
        doc = pq(html)
        page_title = doc('head>title').text()
        if "98堂" not in page_title:
            logger.error(f"页面标题不匹配，获取失败，title='{page_title}': {url}")
            return None
        logger.success(f"页面获取成功: {url}")
        return html

    def bypass_cf(self, url, _retried=False):
        if not config_manager.get().FLARE_SOLVERR_URL:
            logger.warning("未配置FlareSolver")
            return None
        flare_url = config_manager.get().FLARE_SOLVERR_URL.rstrip('/')
        flare_url = flare_url if flare_url.endswith("/v1") else f"{flare_url}/v1"
        logger.info(f"调用 FlareSolver 绕过 Cloudflare{'（重试）' if _retried else ''}: {url}")
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 20000,
            "session": "sht_session",
            "cookies": [{"name": k, "value": v} for k, v in self.cookie.items()]
        }
        res = safe_post(flare_url,
                        headers={"Content-Type": "application/json"},
                        timeout=25,
                        use_proxy=False,
                        json=payload)
        if res is None:
            logger.error(f"FlareSolver 请求失败: {res}")
            return None

        result = res.json()
        solution = result.get("solution", {})
        status = solution.get("status")
        if status != 200:
            logger.error(f"FlareSolver 返回非 200 状态: status={status}, {url}")
            return None

        response_text = solution.get("response")
        if not response_text:
            logger.error(f"FlareSolver 返回内容为空: {url}")
            return None

        html = response_text.encode("utf-8")

        # CF 绕过后仍有 18 禁拦截
        doc = pq(html)
        if "var safeid" in doc.text():
            if _retried:
                logger.error(f"重试后仍检测到 18 禁拦截，放弃: {url}")
                return None
            logger.info(f"Cloudflare 绕过后检测到 18 禁，提取 safeid 并重试: {url}")
            safeid = extract_safeid(html)
            if not safeid:
                logger.error(f"safeid 提取失败: {url}")
                return None
            logger.info(f"提取到 safeid={safeid}，更新 cookie 后重试: {url}")
            self.cookie['_safe'] = safeid
            return self.bypass_cf(url, _retried=True)
        return html

    def bypass_cf_get_cookies(self, url):
        """
        使用 FlareSolverr 过 Cloudflare，仅获取并返回 cookies
        """
        if not config_manager.get().FLARE_SOLVERR_URL:
            logger.warning("未配置 FlareSolverr")
            return None

        flare_url = config_manager.get().FLARE_SOLVERR_URL.rstrip('/')
        flare_url = flare_url if flare_url.endswith("/v1") else f"{flare_url}/v1"

        logger.info(f"使用 FlareSolverr 获取 cookies: {url}")

        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 20000,
            "session": "sht_session"
        }

        res = safe_post(
            flare_url,
            headers={"Content-Type": "application/json"},
            timeout=25,
            use_proxy=False,
            json=payload
        )

        if res is None:
            logger.error("FlareSolverr 请求失败")
            return None

        try:
            result = res.json()
            solution = result.get("solution", {})

            if solution.get("status") != 200:
                logger.error(f"FlareSolverr 返回非 200 状态: {solution.get('status')}")
                return None

            cookies = solution.get("cookies", [])
            if not cookies:
                logger.warning("未获取到 cookies")
                return None

            cookie_dict = {}
            for c in cookies:
                cookie_dict[c["name"]] = c["value"]

            # 🔥 同步到当前实例
            self.cookie.update(cookie_dict)
            ua = solution.get("userAgent")
            if ua:
                self.headers["User-Agent"] = ua

            logger.success(f"成功获取 CF cookies: {list(cookie_dict.keys())}")

            return cookie_dict

        except Exception:
            logger.exception("解析 FlareSolverr 返回结果失败")
            return None

    def bypass_r18(self, html, url):
        logger.info(f"开始提取 safeid: {url}")
        safeid = extract_safeid(html)
        if not safeid:
            logger.error(f"safeid 提取失败: {url}")
            return None

        logger.info(f"提取到 safeid={safeid}，更新 cookie 后重新请求: {url}")
        self.cookie['_safe'] = safeid
        proxies = {
            "http": config_manager.get().PROXY,
            "https": config_manager.get().PROXY
        }

        res = safe_get(url, proxies=proxies, cookies=self.cookie, headers=self.headers,
                       allow_redirects=True, timeout=10)
        if res is None:
            logger.error(f"重新请求失败: {url}")
            return None

        html = res.text.encode('utf-8')
        doc = pq(html)

        # 若仍被 CF 拦截（极端情况）
        if 'Just a moment' in doc('head>title').text():
            logger.info(f"重新请求后再次遭遇 Cloudflare 拦截，转交 bypass_cf 处理: {url}")
            return self.bypass_cf(url)

        page_title = doc('head>title').text()
        if "98堂" not in page_title:
            logger.error(f"[bypass_r18] 页面标题不匹配，绕过失败，title='{page_title}': {url}")
            return None
        logger.success(f"18 禁绕过成功: {url}")
        return html

    def crawler_tid_list(self, fid, page):
        url = f"{self.domain}/forum-{fid}-{page}.html"
        if fid == "95":
            url = f"{self.domain}/forum.php?mod=forumdisplay&fid=95&filter=typeid&typeid=716&page={page}"
        html = self.get_original(url)
        if not html:
            return []
        doc = pq(html)
        id_list = []
        for tbody in doc('tbody[id^="normalthread_"]').items():
            try:
                tid = int(tbody.attr('id').replace('normalthread_', ''))
                id_list.append(tid)
            except (ValueError, TypeError):
                continue
        return id_list

    def crawler_detail(self, tid):
        url = f"{self.domain}/thread-{tid}-1-2.html"
        html = self.get_original(url)
        if html:
            doc = pq(html)
            try:
                all_text = doc('div.blockcode').text()
                magnet_list = re.findall(r'magnet:\?xt=urn:btih:[0-9a-fA-F]+[^"\s]*', all_text)
                ed2k_list = re.findall(
                    r'ed2k://\|file\|[^|]+\|\d+\|[0-9a-fA-F]{32}\|/',
                    all_text
                )

                # 没有磁力则尝试所有 torrent 文件
                if not magnet_list:
                    for torrent in doc("a:contains('.torrent')").items():
                        torrent_url = torrent.attr('href')
                        if not torrent_url:
                            continue
                        full_url = torrent_url if torrent_url.startswith('http') else f"{self.domain}/{torrent_url}"
                        magnet = self.parse_torrent_get_magnet(url, full_url)
                        if magnet:
                            magnet_list.append(magnet)

                if not ed2k_list:
                    for a in doc("a:contains('.txt')").items():
                        txt_url = a.attr('href')
                        if not txt_url:
                            continue
                        full_url = txt_url if txt_url.startswith('http') else f"{self.domain}/{txt_url}"
                        ed2k_from_txt = self.parse_txt_get_ed2k(url, full_url, )
                        if ed2k_from_txt:
                            ed2k_list.extend(ed2k_from_txt)

                if magnet_list or ed2k_list:
                    # 发布日期
                    em_node = doc('em[id^="authorposton"]').eq(0)
                    date_str = ""

                    if em_node:
                        # 1️⃣ 先尝试 span[title]
                        date_span = em_node.find('span[title]')
                        if date_span:
                            title_attr = date_span.attr('title')
                            if title_attr:
                                date_str = title_attr.split(' ')[0]

                        # 2️⃣ 如果没有 span 或 title，则从文本中提取
                        if not date_str:
                            em_text = em_node.text()
                            m = re.search(r'\d{4}-\d{2}-\d{2}', em_text)
                            if m:
                                date_str = m.group(0)
                    if not date_str:
                        date_str = datetime.date.today().isoformat()
                    # 体积
                    first_post_text = doc('[id^="postmessage_"]').eq(0).text()
                    size = None
                    size_match = re.search(r'(\d+\.?\d*)\s*([GM])', first_post_text)
                    if size_match:
                        num, unit = size_match.groups()
                        num = float(num)
                        size = int(num * 1024) if unit.upper() == 'G' else int(num)
                    #     分类
                    category_raw = doc('h1.ts a').eq(0).text().strip()
                    category = category_raw.strip('[]')
                    # 标题
                    title_raw = doc('#thread_subject').text().strip()
                    title = re.sub(r'^\[.*?]', '', title_raw).strip()
                    # 图片列表
                    img_src_list = []
                    first_post = doc('[id^="postmessage_"]').eq(0)
                    for img in first_post('img[file]').items():
                        src = img.attr('file')
                        if src and 'static/image' not in src:
                            img_src_list.append(src.strip())

                    return {
                        "title": title,
                        "category": category,
                        "publish_date": date_str,
                        "magnet": magnet_list,
                        "edk": ed2k_list,
                        "preview_images": img_src_list,
                        "size": size,
                        "website": "sehuatang",
                        "detail_url": url
                    }
            except Exception:
                logger.exception("")
        return None

    def parse_txt_get_ed2k(self, refer, txt_url):
        logger.info(f"获取到文本文件,开始转换为Ed2k:{txt_url}")

        try:

            header = self.headers
            header['Referer'] = refer
            content = self.download_binary(txt_url, refer=refer)
            if not content:
                return []
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("gbk", errors="ignore")
            ed2k_list = re.findall(
                r'ed2k://\|file\|.*?\|/',
                text,
                re.IGNORECASE | re.DOTALL
            )
            return ed2k_list
        except Exception:
            logger.exception("")

    def parse_torrent_get_magnet(self, refer, torrent_source):
        logger.info(f"获取到磁链文件,开始转换为磁力链接:{torrent_source}")
        try:
            header = self.headers
            header['Referer'] = refer
            torrent_bin = self.download_binary(torrent_source, refer=refer)
            if not torrent_bin:
                return None


            if len(torrent_bin) < 100:
                logger.error("下载内容过小，非合法 torrent")
                return None

            torrent_dict = bencoder.decode(torrent_bin)
            if b"info" in torrent_dict:
                info_dict = torrent_dict[b"info"]
            elif "info" in torrent_dict:
                info_dict = torrent_dict["info"]
            else:
                logger.error("错误：种子缺少 info 核心字段（非合法 torrent 文件）")
                return None

            info_bin = bencoder.encode(info_dict)
            info_hash = hashlib.sha1(info_bin).digest()
            info_hash_hex = binascii.hexlify(info_hash).decode("utf-8")

            torrent_name = "Unknown_Torrent"
            if b"name" in info_dict:
                torrent_name = info_dict[b"name"]
            elif "name" in info_dict:
                torrent_name = info_dict["name"]

            if isinstance(torrent_name, bytes):
                try:
                    torrent_name = torrent_name.decode("utf-8")
                except UnicodeDecodeError:
                    torrent_name = torrent_name.decode("utf-8", errors="ignore")
            elif isinstance(torrent_name, str):
                pass
            else:
                torrent_name = str(torrent_name)
            encoded_name = urlencode({"dn": torrent_name})[3:]
            magnet_link = f"magnet:?xt=urn:btih:{info_hash_hex}&dn={encoded_name}"
            return magnet_link
        except Exception:
            logger.exception("")
            return None

    def download_binary(self, url, refer):
        url = self._attachment_url(url)
        res, final_url = self._binary_request(url, refer)
        if res.status_code == 200 and b'Just a moment' not in res.content:
            return self._binary_content(res)
        # The forum's session may be used to refresh forum attachments only.
        # Never pass its cookies to a third-party FlareSolverr target.
        if self._origin(final_url) != self._origin(self.domain):
            logger.warning('附件请求失败，不向第三方站点发送论坛 Cookie')
            return None
        logger.warning('附件需要安全验证，尝试刷新论坛会话')
        cookie_dict = self.bypass_cf_get_cookies(final_url)
        if not cookie_dict:
            return None
        res, _ = self._binary_request(final_url, refer)
        if res.status_code == 200:
            return self._binary_content(res)
        return None

    @staticmethod
    def _origin(url):
        parts = urlsplit(url)
        return parts.scheme.lower(), (parts.hostname or '').lower().rstrip('.'), parts.port or (443 if parts.scheme == 'https' else 80)

    def _attachment_url(self, value, base=None):
        raw = str(value or '')
        if not raw or raw != raw.strip() or '\\' in raw or any(ord(ch) < 32 for ch in raw):
            raise ValueError('附件地址格式无效')
        url = urljoin(base or self.domain.rstrip('/') + '/', raw)
        parts = urlsplit(url)
        if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password:
            raise ValueError('附件地址必须是无认证信息的 HTTP 或 HTTPS 地址')
        host = parts.hostname.lower().rstrip('.')
        forum_host = (urlsplit(self.domain).hostname or '').lower().rstrip('.')
        allowed = {forum_host} | {str(item).lower().rstrip('.') for item in getattr(self, 'attachment_hosts', ())}
        if host not in allowed or parts.port not in {None, 80, 443}:
            raise ValueError('附件地址不属于已允许的论坛或附件站点')
        if host in {'localhost', 'localhost.localdomain'}:
            raise ValueError('不允许从帖子访问本机附件地址')
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError('不允许从帖子访问内网附件地址')
        return url

    def _binary_request(self, url, refer):
        runtime = get_runtime()
        for attempt in range(4):
            runtime.check_cancelled()
            url = self._attachment_url(url)
            same_origin = self._origin(url) == self._origin(self.domain)
            headers = {key: value for key, value in self.headers.items()
                       if key.lower() in {'user-agent', 'accept', 'accept-language'}}
            if same_origin:
                # Remove any query/fragment from the referrer to avoid leaking tokens.
                source = urlsplit(str(refer))
                if self._origin(refer) == self._origin(self.domain):
                    headers['Referer'] = source._replace(query='', fragment='').geturl()
            response = runtime.request('GET', url, timeout=10, follow_redirects=False,
                                       headers=headers, cookies=dict(self.cookie) if same_origin else None,
                                       proxies={'http': config_manager.get().PROXY, 'https': config_manager.get().PROXY})
            if len(response.content) > 8 * 1024 * 1024:
                raise ValueError('附件超过 8 MiB 安全限制')
            if response.status_code in {301, 302, 303, 307, 308}:
                if attempt == 3 or not response.headers.get('location'):
                    raise ValueError('附件跳转次数过多或目标缺失')
                url = self._attachment_url(response.headers['location'], url)
                continue
            return response, url
        raise ValueError('附件跳转次数过多')

    @staticmethod
    def _binary_content(response):
        stripped = response.content.lstrip().lower()
        if 'text/html' in response.headers.get('content-type', '').lower() or stripped.startswith((b'<!doctype', b'<html')):
            logger.warning('附件返回了网页，已跳过')
            return None
        return response.content


class _SHTProxy:
    def __getattr__(self, name):
        runtime = get_runtime()
        if not hasattr(runtime, '_sht_crawler'):
            runtime._sht_crawler = SHT()
        return getattr(runtime._sht_crawler, name)


sht = _SHTProxy()
