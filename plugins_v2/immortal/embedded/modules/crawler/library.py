import re
from asyncio import timeout

from ...core.config import config_manager
from ...utils import safe_post
from ...utils.log import logger
from pyquery import PyQuery as pq


class Library:
    domain = 'https://www.javlibrary.com'
    BESTRATED = 'vl_bestrated'
    MOSTWANTED = 'vl_mostwanted'
    STAR_MOSTFAV = 'star_mostfav'

    def crawler_html(self, url, session):
        flare_solver_url = config_manager.get().FLARE_SOLVERR_URL
        if not flare_solver_url:
            raise RuntimeError("JavLibrary 抓取需要配置 FlareSolverr 服务地址")
        flare_url = flare_solver_url.rstrip('/')
        flare_url = flare_url if flare_url.endswith("/v1") else f"{flare_url}/v1"
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 20000,
            "session": session,
            "tabs_till_verify": 8
        }
        res = safe_post(flare_url,
                        headers={"Content-Type": "application/json"},
                        timeout=25,
                        use_proxy=False,
                        json=payload)
        if res is None:
            raise RuntimeError("JavLibrary 页面获取失败：FlareSolverr 无响应")
        if res.status_code != 200:
            raise RuntimeError(f"JavLibrary 页面获取失败：FlareSolverr HTTP {res.status_code}")
        try:
            result = res.json()
        except ValueError as exc:
            raise RuntimeError("JavLibrary 页面获取失败：FlareSolverr 返回格式无效") from exc
        if not isinstance(result, dict):
            raise RuntimeError("JavLibrary 页面获取失败：FlareSolverr 返回格式无效")
        solution = result.get("solution", {})
        if not isinstance(solution, dict):
            raise RuntimeError("JavLibrary 页面获取失败：FlareSolverr 返回格式无效")
        status = solution.get("status")
        html = solution.get("response")
        if status == 200 and isinstance(html, str) and html.strip():
            return html
        raise RuntimeError("JavLibrary 页面获取失败：未取得可用页面")

    def get_top_movie(self, rank_type, page, session):
        top_url = f"{self.domain}/cn/{rank_type}.php?page={page}"
        html = self.crawler_html(top_url, session)
        movies = []
        if html:
            doc = pq(html)
            for item in doc(".video").items():
                raw_number = item.find(".id").text().strip()
                raw_number = re.sub(r'^\d+([A-Za-z])', r'\1', raw_number) if raw_number else raw_number
                movies.append({
                    "number": raw_number,
                    "title": item.find(".title").text().strip(),
                    "banner": item.find("img").attr("src").replace("ps.jpg", "pl.jpg"),
                    "poster": item.find("img").attr("src")
                })

        return movies

    def get_top_actor(self, session):
        top_url = f"{self.domain}/cn/{self.STAR_MOSTFAV}.php"
        html = self.crawler_html(top_url, session)
        if not html:
            return []
        doc = pq(html)
        stars = []

        for item in doc(".starbox .searchitem").items():
            img = item.find("img")

            name = img.attr("title")
            avatar = img.attr("src")

            if avatar and avatar.startswith("//"):
                avatar = "https:" + avatar

            stars.append({
                "name": name,
                "avatar": avatar
            })
        return stars


library = Library()
