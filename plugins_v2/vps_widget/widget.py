"""Build an independent Forward-compatible catalogue widget.

The generated script contains a read-only catalogue credential, never upstream
provider keys. Its metadata follows the public ForwardWidget module contract.
"""
from __future__ import annotations

import json
from urllib.parse import quote


_SORTS = [("保持榜单顺序", "default"), ("最近更新", "update"),
          ("最近上映", "release"), ("热度优先", "popularity"), ("评分优先", "rating")]


def _choice(name: str, title: str, choices: list[tuple[str, str]]) -> dict:
    return {"name": name, "title": title, "type": "enumeration", "value": choices[0][1],
            "enumOptions": [{"title": label, "value": value} for label, value in choices]}


def _module(source: str, title: str, function: str, *filters: dict) -> dict:
    return {"id": source, "title": title, "description": "读取已缓存的影视榜单，不在播放器内抓取上游网站。",
            "functionName": function, "requiresWebView": False, "sectionMode": False,
            "cacheDuration": 1800,
            "params": [*filters, _choice("sort", "排序", _SORTS),
                       {"name": "page", "title": "页码", "type": "page", "startPage": 1}]}


def build_widget(base_url: str, token: str) -> str:
    """Return a widget for an already validated plugin endpoint prefix.

    ``base_url`` includes ``/api/plugin/vps_widget`` and any deployment subpath.
    """
    if not isinstance(base_url, str) or not isinstance(token, str):
        raise TypeError("访问地址与只读密钥必须是字符串")
    base_url = base_url.strip().rstrip("/")
    if not base_url or not token:
        raise ValueError("请先设置平台访问地址并生成只读密钥")
    metadata = {
        "id": "awbotnest.vps_widget.catalogue", "title": "VPS 影视榜单",
        "description": "读取 AWBotNest 缓存的影视与动画榜单；每页 24 条，可按更新、上映、热度或评分排序。",
        "author": "AWdress", "site": "https://github.com/AWdress/AWBotNest-Plugins",
        "version": "0.0.1", "requiredVersion": "0.0.1", "detailCacheDuration": 600,
        "modules": [
            _module("guduo", "骨朵热度", "loadGuduo",
                    _choice("category", "分类", [(name, name) for name in ["剧集", "综艺", "动漫", "电影"]])),
            _module("douban", "豆瓣榜单", "loadDouban", _choice("channel", "分类", [
                ("全部剧集", "tv"), ("大陆剧集", "tv_domestic"), ("欧美剧集", "tv_american"),
                ("日本剧集", "tv_japanese"), ("韩国剧集", "tv_korean"), ("动画", "tv_animation"),
                ("纪录片", "tv_documentary"), ("大陆综艺", "show_domestic"), ("海外综艺", "show_foreign")
            ])),
            _module("mgtv", "芒果 TV", "loadMangoTV",
                    _choice("sort_by", "分类", [("剧集", "tv"), ("综艺", "show")])),
            _module("theater", "平台剧场", "loadTheater", _choice("brand", "剧场", [
                ("迷雾剧场", "迷雾剧场"), ("白夜剧场", "白夜剧场"), ("X剧场", "X剧场"),
                ("玛卡巴卡悬疑剧场", "玛卡巴卡的悬疑剧"), ("横屏短剧", "横屏短剧"), ("生花剧场", "生花剧场"),
                ("大家剧场", "大家剧场"), ("小逗剧场", "小逗剧场"), ("十分剧场", "十分剧场"),
                ("板凳剧场", "板凳单元"), ("萤火剧场", "萤火单元"), ("正午阳光", "正午阳光"),
                ("恋恋剧场", "恋恋剧场"), ("悬疑剧场", "悬疑剧场"), ("微尘剧场", "微尘剧场")
            ]), _choice("status", "播出状态", [("全部", "all"), ("已开播", "aired"), ("即将开播", "upcoming")])),
            _module("bangumi", "Bangumi 动画", "loadBangumi"),
            _module("tmdb", "TMDB 趋势", "loadTmdb", _choice("type", "分类", [
                ("趋势剧集", "tv"), ("趋势电影", "movie"), ("热门剧集", "tv_popular"), ("热门电影", "movie_popular")
            ])),
            _module("bili", "B站动画榜", "loadBili",
                    _choice("cat", "分类", [("番剧", "bangumi"), ("国创", "guochuang")])),
            _module("mal", "MAL 热播动画", "loadMAL"),
            _module("anilist", "AniList 趋势动画", "loadAniList"),
            _module("trakt", "Trakt 榜单", "loadTrakt", _choice("type", "分类", [
                ("趋势剧集", "trending"), ("热门剧集", "popular"),
                ("趋势电影", "movie_trending"), ("热门电影", "movie_popular")
            ])),
        ],
    }
    urls = {source: f"{base_url}/data/{source}.json?token={quote(token, safe='')}"
            for source in ["guduo", "douban", "mgtv", "theater", "bangumi", "tmdb", "bili", "mal", "anilist", "trakt"]}
    # JSON encoding includes line separators and quotes. Neither string can
    # close a JS literal or inject source text into the generated widget.
    return ("var WidgetMetadata = " + json.dumps(metadata, ensure_ascii=True) + ";\n"
            + "var AW_VPS_ENDPOINTS = " + json.dumps(urls, ensure_ascii=True) + ";\n"
            + _RUNTIME)


_RUNTIME = r"""
async function awCatalogue(source) {
  var endpoint = AW_VPS_ENDPOINTS[source];
  if (!endpoint) throw new Error("不支持的榜单来源");
  var response;
  try {
    response = await Widget.http.get(endpoint, {
      allow_redirects: false,
      headers: {"Accept": "application/json"}
    });
  } catch (error) {
    throw new Error("榜单连接失败，请检查平台地址与网络");
  }
  if (!response || response.ok === false || (response.status && Number(response.status) !== 200)) {
    throw new Error("榜单暂不可用，请检查插件是否启用及只读密钥是否有效");
  }
  var content = response.data;
  if (typeof content === "string") {
    try { content = JSON.parse(content); }
    catch (error) { throw new Error("榜单数据格式不正确"); }
  }
  if (!content || typeof content !== "object" || Array.isArray(content) || content.ok === false) {
    throw new Error("榜单尚未更新，请在插件中刷新该来源");
  }
  return content;
}

function awList(value) { return Array.isArray(value) ? value : []; }

function awNumber(value) {
  var result = Number(value);
  return Number.isFinite(result) ? result : 0;
}

function awImage(value) {
  if (typeof value !== "string") return "";
  return /^\/(?!\/)/.test(value) || /^https?:\/\//i.test(value) ? value : "";
}

function awVideo(record) {
  if (!record || typeof record !== "object" || Array.isArray(record)) return null;
  var rawId = record.tmdbId != null ? record.tmdbId : record.tmdb_id != null ? record.tmdb_id : record.id;
  var media = record.mediaType || record.media_type || record.type;
  if (typeof rawId === "string" && /^(tv|movie)\.\d+$/.test(rawId)) {
    var segments = rawId.split(".");
    if (media !== "tv" && media !== "movie") media = segments[0];
    rawId = segments[1];
  }
  if (typeof rawId !== "number" && !(typeof rawId === "string" && /^\d+$/.test(rawId))) return null;
  var identity = Number(rawId);
  if (!Number.isSafeInteger(identity) || identity < 1 || (media !== "tv" && media !== "movie")) return null;
  var title = record.title || record.tmdbTitle || record.name;
  var poster = awImage(record.posterPath || record.poster_path || record.posterUrl);
  if (typeof title !== "string" || !title.trim() || !poster) return null;
  return {
    id: identity, tmdbId: identity, type: "tmdb", mediaType: media,
    title: title, posterPath: poster, posterUrl: poster,
    backdropPath: awImage(record.backdropPath || record.backdrop_path || record.backdropUrl),
    rating: awNumber(record.rating != null ? record.rating : record.vote_average),
    releaseDate: String(record.releaseDate || record.release_date || record.first_air_date || ""),
    description: String(record.description || record.overview || ""),
    popularity: awNumber(record.popularity != null ? record.popularity : record.heat),
    lastUpdateDate: String(record.lastUpdateDate || record.last_update_date || "")
  };
}

function awPage(records, options) {
  options = options && typeof options === "object" ? options : {};
  var items = [], seen = Object.create(null);
  awList(records).forEach(function(record) {
    var video = awVideo(record);
    if (!video) return;
    var unique = video.mediaType + ":" + video.tmdbId;
    if (!seen[unique]) { seen[unique] = true; items.push(video); }
  });
  var keys = {update: "lastUpdateDate", release: "releaseDate", popularity: "popularity", rating: "rating"};
  var key = keys[options.sort];
  if (key) {
    items.sort(function(left, right) {
      if (key === "releaseDate" || key === "lastUpdateDate") {
        var a = Date.parse(left[key]), b = Date.parse(right[key]);
        return (Number.isFinite(b) ? b : 0) - (Number.isFinite(a) ? a : 0);
      }
      return right[key] - left[key];
    });
  }
  var page = Number(options.page == null ? 1 : options.page);
  if (!Number.isSafeInteger(page) || page < 1) page = 1;
  var start = (page - 1) * 24;
  return items.slice(start, start + 24);
}

async function loadGuduo(params) {
  params = params || {};
  var data = await awCatalogue("guduo");
  return awPage(data.categories && data.categories[params.category || "剧集"], params);
}

async function loadDouban(params) {
  params = params || {};
  var data = await awCatalogue("douban");
  return awPage(data[params.channel || "tv"], params);
}

async function loadMangoTV(params) {
  params = params || {};
  var data = await awCatalogue("mgtv");
  return awPage(data[params.sort_by || "tv"], params);
}

async function loadTheater(params) {
  params = params || {};
  var data = await awCatalogue("theater");
  var group = data[params.brand || "迷雾剧场"];
  if (Array.isArray(group)) return awPage(group, params);
  if (!group || typeof group !== "object") return [];
  var records = params.status === "aired" ? awList(group.aired)
    : params.status === "upcoming" ? awList(group.upcoming)
    : awList(group.aired).concat(awList(group.upcoming));
  return awPage(records, params);
}

async function loadBangumi(params) {
  var data = await awCatalogue("bangumi");
  return awPage(data.hot_anime, params);
}

async function loadTmdb(params) {
  params = params || {};
  var data = await awCatalogue("tmdb");
  return awPage(data[params.type || "tv"], params);
}

async function loadBili(params) {
  params = params || {};
  var data = await awCatalogue("bili");
  return awPage(data[params.cat || "bangumi"], params);
}

async function loadMAL(params) {
  var data = await awCatalogue("mal");
  return awPage(data.airing, params);
}

async function loadAniList(params) {
  var data = await awCatalogue("anilist");
  return awPage(data.trending, params);
}

async function loadTrakt(params) {
  params = params || {};
  var data = await awCatalogue("trakt");
  return awPage(data[params.type || "trending"], params);
}
"""
