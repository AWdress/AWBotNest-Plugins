import datetime
import re
from html import unescape
from urllib.parse import parse_qs, urlparse

from ...core.config import config_manager
from pyquery import PyQuery as pq

from ...utils import safe_post
from ...utils.log import logger


class X1080X:
    domain = 'https://agaghhh.cc'

    def bypass_cf(self, url):
        if not config_manager.get().FLARE_SOLVERR_URL:
            logger.warning("未配置FlareSolver")
            return None
        logger.info(f"开始请求: {url}")
        flare_url = config_manager.get().FLARE_SOLVERR_URL.rstrip('/')
        flare_url = flare_url if flare_url.endswith("/v1") else f"{flare_url}/v1"
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 20000,
            "session": "x1080x_session"
        }
        res = safe_post(
            flare_url,
            headers={"Content-Type": "application/json"},
            timeout=25,
            use_proxy=False,
            json=payload
        )
        if res is None:
            logger.error(f"FlareSolver 请求失败，返回 None: {url}")
            return None
        result = res.json()
        status = result.get("solution", {}).get("status")
        if status != 200:
            logger.error(f"FlareSolver 返回非 200 状态: status={status}, {url}")
            return None
        html = result.get("solution", {}).get("response")
        if not html:
            logger.error(f"FlareSolver 获取页面失败: {url}")
            return None

        logger.success(f"FlareSolver 获取页面成功: {url}")
        return html

    def get_tid_from_list(self, typeid, page):
        url = (
            f"{self.domain}/forum.php?mod=forumdisplay"
            f"&fid=244&archiver=1&page={page}"
            f"&filter=typeid&typeid={typeid}"
        )
        html = self.bypass_cf(url)
        tid_list = []
        if html:
            doc = pq(html)
            content = doc("#content")
            for a in content('a[href*="viewthread"]').items():
                try:
                    href = a.attr("href")
                    if not href:
                        continue
                    parsed = urlparse(href)
                    query_params = parse_qs(parsed.query)

                    tid_values = query_params.get("tid")
                    if not tid_values:
                        continue
                    tid = int(tid_values[0])
                    tid_list.append(tid)
                except (ValueError, TypeError) as e:
                    logger.error(f"值类型解析错误: {e}")
                    continue
                except Exception:
                    logger.exception("")
                    continue
        return tid_list

    def get_detail_by_tid(self, tid):
        url = f"{self.domain}/forum.php?mod=viewthread&tid={tid}&archiver=1"
        html = self.bypass_cf(url)
        if html:
            doc = pq(html)
            try:
                content_html = doc("#content").html() or ""
                code_blocks = re.findall(
                    r"\[code](.*?)\[/code]",
                    content_html,
                    re.S
                )
                magnet_links = []
                for block in code_blocks:
                    try:
                        block = unescape(block).strip()
                        if block.startswith("magnet:?"):
                            magnet_links.append(block)
                    except Exception:
                        continue
                if magnet_links:
                    img_urls = re.findall(r"\[img](.*?)\[/img]", content_html)
                    nav_text = doc("#nav").text() or ""
                    if "›" in nav_text:
                        title = nav_text.split("›")[-1].strip()
                    else:
                        title = nav_text.strip()
                    publish_date = None
                    author_text = doc("p.author").text() or ""
                    if "发表于" in author_text:
                        try:
                            publish_date = (
                                author_text.split("发表于")[-1]
                                .strip()
                                .split(" ")[0]
                            )
                        except Exception:
                            publish_date = None

                    if not publish_date:
                        publish_date = datetime.date.today().isoformat()
                    return {
                        "title": title,
                        "category": "",
                        "publish_date": publish_date,
                        "magnet": magnet_links,
                        "preview_images": img_urls,
                        "size": 0,
                        "detail_url": url,
                        "website": "x1080x",
                    }
            except Exception:
                logger.exception("")
        return None


x1080x = X1080X()
