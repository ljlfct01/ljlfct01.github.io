# -*- coding: utf-8 -*-
# 影探4K 聚合版 (2026-08-30)
# ============ 本版特性 ============
# 1) 影探本体修复: host→HTTPS / 去二次编码 / 补 lvdou 解密 / 全接口异常保护
# 2) 官方线路(qq/优酷等VIP页) → 内置 5 个实测可用 Web 解析轮询
# 3) 【新增】内嵌 4 个 4K 解析引擎(直接挂载同目录爬虫文件):
#      多多影视(CO4K protobuf解码) / 剧下饭(秒播解析) /
#      真不错·星海(站内parse)      / 星影(站内+外部parse)
#    打开影片详情时自动跨站搜索同名影片, 将其线路(4K优先)并入影探线路列表,
#    播放时按线路自动路由到对应引擎解码出直链。
#    引擎文件路径: /sdcard/TVBox/py/{多多影视4K,剧下饭4K,真不错4K,星影}.py
#    (文件缺失或站点挂了会自动跳过, 不影响影探本体)
# ==================================
import re, sys, json, base64
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except Exception:
    AES = None
    def unpad(b, n): return b[:-(b[-1] if 0 < b[-1] <= 16 else 0)] if b else b
from urllib.parse import urljoin, quote, unquote
from base.spider import Spider

sys.path.append('..')


class Spider(Spider):
    headers = {'User-Agent': 'okhttp/4.12.0'}
    parse_headers = {'User-Agent': 'okhttp-okgo/jeasonlzy'}

    FIXED_CONFIG = {
        'host': 'https://cms.lyyytv.cn',
        'cmskey': 'wP5bvxoc3yv7FoBQENFZuAF0EUYr4LTy',
        'RawPlayUrl': 0,
        'parse_api': 'http://125.208.22.184:6019/api/index?parsesId=550266&appid=10000&videoUrl='
    }

    # 内置 Web 解析（2026-08-30 实测均可出流，官方线路轮询使用）
    WEB_PARSES = [
        'http://125.208.22.184:6019/api/index?parsesId=550266&appid=10000&videoUrl=',
        'http://125.208.22.184:6019/api/index?parsesId=550266&appid=10000&videoUrl=',
        'http://125.208.22.184:6019/api/index?parsesId=550266&appid=10000&videoUrl=',
        'http://125.208.22.184:6019/api/index?parsesId=550266&appid=10000&videoUrl=',
        'http://125.208.22.184:6019/api/index?parsesId=550266&appid=10000&videoUrl=',
    ]

    # ============ 4K 解析引擎挂载表 ============
    # (tag, 显示名, 文件路径)  —— 播放 id 形如 tag@@线路码@@引擎剧集id
    ENGINES = [
        ('dd', '多多4K', 'http://125.208.22.184:6019/api/index?parsesId=550266&appid=10000&videoUrl='),
        ('dd', '多多4K', 'http://61.184.23.217:6163/api/index?parsesId=4&appid=10002&videoUrl='),
        ('jxf', '剧下饭4K', 'http://125.208.22.184:6019/api/index?parsesId=550266&appid=10000&videoUrl='),
        ('jxf', '剧下饭4K', 'http://61.184.23.217:6163/api/index?parsesId=4&appid=10002&videoUrl='),
        ('zn', '真不错4K', 'http://125.208.22.184:6019/api/index?parsesId=550266&appid=10000&videoUrl='),
        ('zn', '真不错4K', 'http://61.184.23.217:6163/api/index?parsesId=4&appid=10002&videoUrl='),
        ('xy', '星影', 'http://125.208.22.184:6019/api/index?parsesId=550266&appid=10000&videoUrl='),
        ('xy', '星影', 'http://61.184.23.217:6163/api/index?parsesId=4&appid=10002&videoUrl='),
    ]

    def init(self, extend=''):
        self.host = self.FIXED_CONFIG['host']
        self.cmskey = self.FIXED_CONFIG.get('cmskey', '')
        self.parse_api = self.FIXED_CONFIG.get('parse_api', '')
        self.raw_play_url = self.FIXED_CONFIG.get('RawPlayUrl', 0)
        self._engine_cache = None        # [(tag, disp, spider), ...]
        self._detail_cache = {}          # (tag, 归一化片名) -> (from列表, url列表)

    # ==================== 引擎加载 ====================
    def _load_engines(self):
        if self._engine_cache is not None:
            return self._engine_cache
        out = []
        for tag, disp, path in self.ENGINES:
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location('eng_' + tag, path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                sp = mod.Spider()
                if hasattr(sp, 'init'):
                    sp.init('')
                out.append((tag, disp, sp))
            except Exception:
                continue
        self._engine_cache = out
        return out

    @staticmethod
    def _norm(s):
        s = re.sub(r'[\s:：·（）()\-_,，。.\[\]【】!！?？]', '', s or '')
        return s.lower()

    def _engine_lines(self, tag, disp, sp, title):
        """在单个引擎站搜索同名影片并取回线路; 返回 (from列表, url列表)"""
        try:
            tnorm = self._norm(title)
            if not tnorm:
                return [], []
            cached = self._detail_cache.get((tag, tnorm))
            if cached is not None:
                return cached
            res = sp.searchContent(title, '1', '1')
            if isinstance(res, str):
                res = json.loads(res)
            vid = None
            for it in (res.get('list') or []):
                if self._norm(it.get('vod_name')) == tnorm:
                    vid = it.get('vod_id')
                    break
            if vid is None:
                for it in (res.get('list') or []):
                    n = self._norm(it.get('vod_name'))
                    if n and (n in tnorm or tnorm in n):
                        vid = it.get('vod_id')
                        break
            if vid is None:
                self._detail_cache[(tag, tnorm)] = ([], [])
                return [], []

            det = sp.detailContent([vid])
            if isinstance(det, str):
                det = json.loads(det)
            vod = (det.get('list') or [{}])[0]
            raw_from = (vod.get('vod_play_from') or '').strip()
            raw_urls = (vod.get('vod_play_url') or '').strip()
            if not raw_from or not raw_urls:
                self._detail_cache[(tag, tnorm)] = ([], [])
                return [], []

            names = [n.strip() for n in raw_from.split('$$$')]
            groups = raw_urls.split('$$$')
            show, play_urls = [], []
            for i, group in enumerate(groups):
                eflag = names[i] if i < len(names) and names[i] else '线路%d' % (i + 1)
                episodes = []
                for part in group.split('#'):
                    part = part.strip()
                    if not part:
                        continue
                    if '$' in part:
                        ep_name, epid = part.split('$', 1)
                    else:
                        ep_name, epid = part, part
                    # id 内嵌: tag@@引擎线路码@@引擎剧集id (引擎id 可能自带@@)
                    episodes.append(f"{ep_name}${tag}@@{eflag}@@{epid}")
                if episodes:
                    show.append(f"{disp}·{eflag}")
                    play_urls.append('#'.join(episodes))
            pairs = sorted(zip(show, play_urls),
                           key=lambda p: 0 if re.search(r'4k|蓝光|co', p[0], re.I) else 1)
            show = [p[0] for p in pairs]
            play_urls = [p[1] for p in pairs]
            self._detail_cache[(tag, tnorm)] = (show, play_urls)
            return show, play_urls
        except Exception:
            return [], []

    # ==================== 影探本体 ====================
    def ldmax_decrypt(self, encrypted_base64, depth=0):
        if depth > 5:
            return None
        cleaned = re.sub(r'\s+', '', encrypted_base64 or '')
        try:
            decoded = base64.b64decode(cleaned, validate=True).decode('utf-8', errors='ignore')
        except Exception:
            return encrypted_base64
        url = re.sub(r'\s+', '', decoded)
        if 'ldmax.cooom' not in url:
            return url
        path = re.sub(r'https?://ldmax\.cooom/', '', url)
        if len(path) < 16:
            return None
        key = path[:16][::-1].encode('utf-8')
        ciphertext_b64 = re.sub(r'\s+', '', path[16:])
        try:
            ciphertext = base64.b64decode(ciphertext_b64, validate=True)
            cipher = AES.new(key, AES.MODE_CBC, key)
            decrypted = cipher.decrypt(ciphertext)
        except Exception:
            return None
        if decrypted:
            pad = decrypted[-1]
            if 0 < pad <= 16:
                decrypted = decrypted[:-pad]
        result = decrypted.decode('utf-8', errors='ignore').strip()
        if 'ldmax.cooom' in result:
            return self.ldmax_decrypt(base64.b64encode(result.encode('utf-8')).decode('utf-8'), depth + 1)
        return result

    def ldmax_parse(self, video_url):
        decrypted = self.ldmax_decrypt(video_url)
        if not decrypted or not re.match(r'^https?://', decrypted):
            return None
        try:
            parse_url = self.parse_api + quote(decrypted, safe='')
            resp = self.fetch(parse_url, headers=self.parse_headers, timeout=30).json()
        except Exception:
            return None
        if not resp or resp.get('code') != 200 or not resp.get('url'):
            return None
        final_url = self.ldmax_decrypt(resp['url'])
        if final_url and re.match(r'^https?://', final_url):
            return {'url': final_url, 'type': resp.get('type', 'video')}
        return None

    def lvdou(self, text):
        if AES is None:
            return text
        key = self.cmskey[:16].encode("utf-8")
        iv = self.cmskey[-16:].encode("utf-8")
        url_prefix = "lvdou+"
        text = text or ''
        if text.startswith(url_prefix):
            ciphertext_b64 = text[len(url_prefix):]
            try:
                cipher = AES.new(key, AES.MODE_CBC, iv)
                ct_bytes = base64.b64decode(ciphertext_b64)
                pt_bytes = cipher.decrypt(ct_bytes)
                return unpad(pt_bytes, AES.block_size).decode('utf-8')
            except Exception:
                return text
        return text

    @staticmethod
    def clean_url(url):
        if not url:
            return url
        url = url.strip().replace(' ', '%20')
        if url.startswith('http%3A') or url.startswith('https%3A'):
            try:
                url = unquote(url)
            except Exception:
                pass
        try:
            url = quote(url, safe=":/?&=#%@+,;$!'()*~[]")
        except Exception:
            pass
        return url

    # ---------- 详情(含跨站4K线路聚合) ----------
    def detailContent(self, ids):
        try:
            data = self.fetch(f"{self.host}/api.php/app/video_detail?id={ids[0]}",
                              headers=self.headers, timeout=20).json()
        except Exception:
            return {'list': []}

        vod_data = data.get('data') or {}
        if not vod_data:
            return {'list': []}

        show, play_urls = [], []

        # --- 影探本体线路 ---
        raw_from = (vod_data.get('vod_play_from') or '').strip()
        raw_urls = (vod_data.get('vod_play_url') or '').strip()
        if raw_from and raw_urls:
            names = [n.strip() for n in raw_from.split('$$$')]
            groups = raw_urls.split('$$$')
            for i, group in enumerate(groups):
                name = names[i] if i < len(names) and names[i] else '线路%d' % (i + 1)
                episodes = []
                for part in group.split('#'):
                    part = part.strip()
                    if not part:
                        continue
                    if '$' in part:
                        episode, url = part.split('$', 1)
                        episodes.append(f"{episode}${self.lvdou(url)}")
                    else:
                        episodes.append(self.lvdou(part))
                if episodes:
                    show.append('影探·' + name)
                    play_urls.append('#'.join(episodes))

        # --- 4K 引擎线路(跨站同名匹配) ---
        title = vod_data.get('vod_name') or ''
        if title:
            for tag, disp, sp in self._load_engines():
                s, u = self._engine_lines(tag, disp, sp, title)
                show.extend(s)
                play_urls.extend(u)

        if not show:
            return {'list': [vod_data]}

        vod_data.pop('vod_url_with_player', None)
        vod_data['vod_play_from'] = '$$$'.join(show)
        vod_data['vod_play_url'] = '$$$'.join(play_urls)
        return {'list': [vod_data]}

    # ---------- 播放 ----------
    def playerContent(self, flag, video_id, vipFlags):
        video_id = video_id or ''

        # ===== 引擎线路路由: tag@@线路码@@引擎剧集id =====
        if '@@' in video_id:
            eid = ''
            try:
                tag, eflag, eid = video_id.split('@@', 2)
                for t, _disp, sp in self._load_engines():
                    if t == tag:
                        r = sp.playerContent(eflag, eid, None)
                        if isinstance(r, str):
                            r = json.loads(r)
                        if r and r.get('url'):
                            r.setdefault('header', self.headers)
                            r.setdefault('parse', 0)
                            r.setdefault('jx', 0)
                            return r
                        break
            except Exception:
                pass
            # 引擎失败 → 落回影探官方链路处理(eid 若为空则按普通流程)
            video_id = eid

        video_id = self.lvdou(video_id)
        video_id = self.clean_url(video_id)

        if self.check_paly_url(video_id):
            return {'jx': 0, 'parse': 0, 'playUrl': '', 'url': video_id, 'header': self.headers}

        parsed = self.ldmax_parse(video_id)
        if parsed:
            return {'jx': 0, 'parse': 0, 'playUrl': '', 'url': parsed['url'], 'header': self.headers}

        # VIP 页面链接 → 内置 Web 解析轮询（嗅探模式）
        if re.match(r'^https?://', video_id):
            import random as _r
            parser = _r.choice(self.WEB_PARSES)
            return {'jx': 0, 'parse': 1, 'playUrl': '', 'url': parser + quote(video_id, safe=''),
                    'header': self.headers}

        return {'jx': 1, 'parse': 0, 'playUrl': '', 'url': video_id, 'header': self.headers}

    # ---------- 其他接口 ----------
    def homeVideoContent(self):
        try:
            data = self.fetch(f"{self.host}/api.php/app/index_video?token=",
                              headers=self.headers, timeout=20).json()
            videos = []
            for item in data.get('list') or []:
                videos.extend(item.get('vlist') or [])
            return {'list': videos}
        except Exception:
            return {'list': []}

    def homeContent(self, filter):
        try:
            data = self.fetch(f"{self.host}/api.php/app/nav?token=",
                              headers=self.headers, timeout=20).json()
        except Exception:
            return {"class": [], "filters": {}}

        keys = ["class", "area", "lang", "year", "letter", "by", "sort"]
        filters = {}
        classes = []
        for item in data.get('list') or []:
            has_non_empty_field = False
            jsontype_extend = item.get("type_extend") or {}
            classes.append({"type_name": item.get("type_name"), "type_id": item.get("type_id")})
            for key in keys:
                v = jsontype_extend.get(key, '')
                if v and v.strip() != "":
                    has_non_empty_field = True
                    break
            if has_non_empty_field:
                filters[str(item.get("type_id"))] = []
            for dkey in jsontype_extend:
                if dkey in keys and jsontype_extend[dkey].strip() != "":
                    values = jsontype_extend[dkey].split(",")
                    value_array = []
                    for value in values:
                        if value.strip() != "":
                            value_array.append({"n": value.strip(), "v": value.strip()})
                    filters.setdefault(str(item.get("type_id")), []).append(
                        {"key": dkey, "name": dkey, "value": value_array})
        return {"class": classes, "filters": filters}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            query_params = [f"tid={tid}", f"pg={pg}", "limit=18"]
            for k in ('class', 'area', 'lang', 'year'):
                if extend and extend.get(k):
                    query_params.append(f"{k}={extend.get(k)}")
            url = f"{self.host}/api.php/app/video?" + "&".join(query_params)
            return self.fetch(url, headers=self.headers, timeout=20).json()
        except Exception:
            return {'list': [], 'page': pg, 'pagecount': 0, 'total': 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            data = self.fetch(f"{self.host}/api.php/app/search?text={quote(key)}&pg={pg}",
                              headers=self.headers, timeout=20).json()
            videos = data.get('list') or []
            for item in videos:
                item.pop('type', None)
            return {'list': videos, 'page': pg}
        except Exception:
            return {'list': [], 'page': pg}

    def raw_url(self, original_url):
        try:
            response = self.fetch(original_url, allow_redirects=False, stream=True, timeout=20)
            if 300 <= response.status_code < 400:
                redirect_location = response.headers.get('Location')
                if redirect_location:
                    return urljoin(original_url, redirect_location)
            return original_url
        except Exception:
            return original_url

    def check_paly_url(self, content):
        pattern = r"https?://.*(?:\.(?:mp4|m3u8|flv|avi|mkv|ts|mov|wmv|webm)|lyyytv\.cn/)"
        return bool(re.search(pattern, content or '', re.IGNORECASE))

    def getName(self): return "lyyytv"
    def localProxy(self, param): pass
    def isVideoFormat(self, url): return self.check_paly_url(url)
    def manualVideoCheck(self): return True
