import re, sys, json, base64, requests
from Crypto.Cipher import AES
from urllib.parse import urljoin, quote, unquote
from Crypto.Util.Padding import unpad
from base.spider import Spider

sys.path.append('..')


class Spider(Spider):
    headers = {'User-Agent': 'okhttp/4.12.0'}

    FIXED_CONFIG = {
        'host': 'https://gh.bugdey.us.kg/https://raw.githubusercontent.com/ljlfct01/ljlfct01.github.io/refs/heads/main/txt',
        'cmskey': 'ziKv8NzFSwNoBUYRJclwwjRaiTWBb7ON',
        'RawPlayUrl': 0,
        # 嗅探解析代理配置（解析时使用固定IP）
        'proxy_host': 'http://202.189.11.83',  # 代理服务器地址
        'proxy_port': 9978,                 # 代理端口
        'sniffer': True,                    # 启用嗅探
        # 全局解析接口配置
        'parse_url': 'http://shenmijx.vip.cpolar.cn/%E5%85%AC%E5%BC%80/%E7%81%AB%E7%84%B0%E4%B9%8B%E5%B1%B1.php?url=',  # 全局解析接口
        'use_parse_api': True               # 是否启用全局解析
    }

    def init(self, extend=''):
        self.host = self.FIXED_CONFIG['host']
        self.cmskey = self.FIXED_CONFIG.get('cmskey', '')
        raw_play_url = self.FIXED_CONFIG.get('RawPlayUrl', 0)
        if raw_play_url == 1:
            self.raw_play_url = 1
        else:
            self.raw_play_url = 0
        # 嗅探解析代理配置
        self.proxy_host = self.FIXED_CONFIG.get('proxy_host', '')
        self.proxy_port = self.FIXED_CONFIG.get('proxy_port', 0)
        self.sniffer_enabled = self.FIXED_CONFIG.get('sniffer', True)
        
        # 全局解析接口配置
        self.parse_api = self.FIXED_CONFIG.get('parse_api', '')
        self.use_parse_api = self.FIXED_CONFIG.get('use_parse_api', False)
        
        # 构建代理URL（用于解析嗅探和全局解析）
        if self.proxy_host and self.proxy_port:
            self.proxy_url = f"{self.proxy_host}:{self.proxy_port}"
        else:
            self.proxy_url = None
    
    def _proxy_fetch(self, url, headers, timeout=15, **kwargs):
        """
        通过代理服务器转发请求（仅用于嗅探解析）
        让解析站点看到的是固定IP: 202.189.11.83
        """
        proxies = {
            'http': self.proxy_url,
            'https': self.proxy_url
        }
        
        try:
            response = requests.request(
                method=kwargs.get('method', 'GET'),
                url=url,
                headers=headers,
                proxies=proxies,
                timeout=timeout,
                allow_redirects=kwargs.get('allow_redirects', False),
                stream=kwargs.get('stream', False)
            )
            return response
        except Exception as e:
            print(f"代理解析失败: {e}")
            # 代理失败时，尝试直接请求
            try:
                response = requests.request(
                    method=kwargs.get('method', 'GET'),
                    url=url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=kwargs.get('allow_redirects', False),
                    stream=kwargs.get('stream', False)
                )
                return response
            except:
                raise e

    def homeVideoContent(self):
        data = self.fetch(f"{self.host}/api.php/app/index_video?token=", headers=self.headers).json()
        videos = []
        for item in data['list']:
            videos.extend(item['vlist'])
        return {'list': videos}

    def homeContent(self, filter):
        data = self.fetch(f"{self.host}/api.php/app/nav?token=", headers=self.headers).json()
        keys = ["class", "area", "lang", "year", "letter", "by", "sort"]
        filters = {}
        classes = []

        for item in data['list']:
            has_non_empty_field = False
            jsontype_extend = item["type_extend"]
            classes.append({"type_name": item["type_name"], "type_id": item["type_id"]})

            for key in keys:
                if key in jsontype_extend and jsontype_extend[key].strip() != "":
                    has_non_empty_field = True
                    break

            if has_non_empty_field:
                filters[str(item["type_id"])] = []

            for dkey in jsontype_extend:
                if dkey in keys and jsontype_extend[dkey].strip() != "":
                    values = jsontype_extend[dkey].split(",")
                    value_array = []
                    for value in values:
                        if value.strip() != "":
                            value_array.append({"n": value.strip(), "v": value.strip()})
                    filters[str(item["type_id"])].append({"key": dkey, "name": dkey, "value": value_array})

        return {"class": classes, "filters": filters}

    def categoryContent(self, tid, pg, filter, extend):
        # 构建URL查询参数
        query_params = [
            f"tid={tid}",
            f"pg={pg}",
            f"limit=18"
        ]
        if extend.get('class'):
            query_params.append(f"class={extend.get('class')}")
        if extend.get('area'):
            query_params.append(f"area={extend.get('area')}")
        if extend.get('lang'):
            query_params.append(f"lang={extend.get('lang')}")
        if extend.get('year'):
            query_params.append(f"year={extend.get('year')}")

        url = f"{self.host}/api.php/app/video?" + "&".join(query_params)
        data = self.fetch(url, headers=self.headers).json()
        return data

    def searchContent(self, key, quick, pg="1"):
        data = self.fetch(f"{self.host}/api.php/app/search?text={key}&pg={pg}", headers=self.headers).json()
        videos = data['list']
        for item in data['list']:
            item.pop('type', None)
        return {'list': videos, 'page': pg}

    def detailContent(self, ids):
        data = self.fetch(f"{self.host}/api.php/app/video_detail?id={ids[0]}", headers=self.headers).json()['data']
        show, paly_urls = [], []

        for i in data['vod_url_with_player']:
            urls = i['url'].split('#')
            urls2 = []
            for j in urls:
                if j:
                    url = j.split('$', 1)
                    urls2.append(f"{url[0]}${self.lvdou(url[1])}")
            paly_urls.append('#'.join(urls2))

            show.append(i['name'].strip())

        data.pop('vod_url_with_player')
        data['vod_play_from'] = '$$$'.join(show)
        data['vod_play_url'] = '$$$'.join(paly_urls)
        return {'list': [data]}

    def playerContent(self, flag, video_id, vipFlags):
        jx = 0
        parse = 0
        url = video_id

        # 检查是否是直接视频地址
        if self.check_paly_url(video_id):
            if self.raw_play_url == 1:
                url = self.raw_url(video_id)
            return {'jx': 0, 'playUrl': '', 'parse': 0, 'url': url, 'header': self.headers}
        
        # 需要解析的链接
        if self.use_parse_api and self.parse_api:
            # 使用全局解析接口（通过代理）
            parse_url = f"{self.parse_api}{quote(video_id)}"
            proxy_url = f"proxy://do=parse&url={quote(parse_url)}"
            print(f"使用全局解析接口: {self.parse_api}")
            return {'jx': 0, 'playUrl': '', 'parse': 0, 'url': proxy_url, 'header': self.headers}
        
        # 嗅探模式
        if self.sniffer_enabled:
            # 通过代理嗅探
            proxy_url = f"proxy://do=sniffer&url={quote(video_id)}"
            return {'jx': 0, 'playUrl': '', 'parse': 0, 'url': proxy_url, 'header': self.headers}
        
        # 默认使用jx解析
        return {'jx': 1, 'playUrl': '', 'parse': 0, 'url': url, 'header': self.headers}

    def lvdou(self, text):
        key = self.cmskey[:16].encode("utf-8")
        iv = self.cmskey[-16:].encode("utf-8")
        original_text = text
        url_prefix = "lvdou+"

        if original_text.startswith(url_prefix):
            ciphertext_b64 = original_text[len(url_prefix):]
            try:
                cipher = AES.new(key, AES.MODE_CBC, iv)
                ct_bytes = base64.b64decode(ciphertext_b64)
                pt_bytes = cipher.decrypt(ct_bytes)
                return unpad(pt_bytes, AES.block_size).decode('utf-8')
            except Exception:
                return original_text
        else:
            return original_text

    def raw_url(self, original_url):
        try:
            response = self.fetch(original_url, allow_redirects=False, stream=True, timeout=20)
            if 300 <= response.status_code < 400:
                redirect_location = response.headers.get('Location')
                if redirect_location:
                    real_url = urljoin(original_url, redirect_location)
                    return real_url
            return original_url
        except Exception:
            return original_url

    def check_paly_url(self, content):
        pattern = r"https?://.*(?:\.(?:mp4|m3u8|flv|avi|mkv|ts|mov|wmv|webm)|lyyytv\.cn/)"
        return bool(re.search(pattern, content, re.IGNORECASE))

    def getName(self):
        return "观影嗅探"

    def localProxy(self, param):
        """
        本地代理方法，支持嗅探、全局解析和服务器中转
        param: dict 包含 do(操作类型) 和 url(目标地址) 等参数
        """
        action = param.get('do', '')
        
        if action == 'sniffer':
            # 嗅探模式：访问页面提取真实视频地址
            return self._sniffer_video(param)
        elif action == 'parse':
            # 全局解析模式：调用第三方解析接口
            return self._parse_video(param)
        elif action == 'proxy':
            # 纯代理模式：直接转发请求
            return self._proxy_request(param)
        elif action == 'redirect':
            # 重定向模式：跟踪重定向获取真实地址
            return self._redirect_sniffer(param)
        
        return [404, 'text/plain', 'Not Found']
    
    def _sniffer_video(self, param):
        """
        嗅探视频地址（使用代理服务器，固定IP访问）
        从网页中提取真实的视频播放地址
        """
        url = unquote(param.get('url', ''))
        if not url:
            return [404, 'text/plain', 'URL is required']
        
        try:
            # 访问目标页面（通过代理）
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': url
            }
            
            # 使用代理嗅探（关键：通过固定IP访问）
            if self.proxy_url:
                print(f"使用代理 {self.proxy_url} 嗅探: {url}")
                response = self._proxy_fetch(url, headers, timeout=15)
            else:
                # 没有配置代理，直接请求
                response = requests.get(url, headers=headers, timeout=15)
            
            html = response.text
            
            # 嗅探规则：匹配常见的视频地址格式
            patterns = [
                r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)',
                r'(https?://[^\s"\'<>]+?\.mp4[^\s"\'<>]*)',
                r'(https?://[^\s"\'<>]+?\.flv[^\s"\'<>]*)',
                r'"url"\s*:\s*"(https?://[^"]+)"',
                r'videoUrl\s*[=:]\s*["\']([^"\']+)["\']',
                r'source\s*src\s*=\s*["\']([^"\']+)["\']',
                r'play_?url["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    video_url = match.group(1)
                    # 清理URL中的转义字符
                    video_url = video_url.replace('\\/', '/').replace('\\u0026', '&')
                    
                    print(f"嗅探成功: {video_url}")
                    # 返回302重定向到真实地址
                    return [302, 'text/plain', video_url, {'Location': video_url}]
            
            # 如果嗅探失败，返回错误
            print(f"嗅探失败: 未找到视频地址")
            return [404, 'text/plain', 'Failed to sniff video URL']
            
        except Exception as e:
            print(f"嗅探异常: {e}")
            return [500, 'text/plain', f'Sniffer error: {str(e)}']
    
    def _parse_video(self, param):
        """
        调用全局解析接口（使用代理服务器，固定IP访问）
        通过第三方解析服务获取视频地址
        """
        url = unquote(param.get('url', ''))
        if not url:
            return [404, 'text/plain', 'URL is required']
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': url
            }
            
            # 使用代理访问解析接口（固定IP）
            if self.proxy_url:
                print(f"使用代理 {self.proxy_url} 全局解析: {url}")
                response = self._proxy_fetch(url, headers, timeout=20)
            else:
                response = requests.get(url, headers=headers, timeout=20)
            
            html = response.text
            
            # 从解析结果中提取视频地址
            # 尝试多种匹配模式
            patterns = [
                r'url\s*[:=]\s*["\']([^"\']+)["\']',
                r'var\s+url\s*=\s*["\']([^"\']+)["\']',
                r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)',
                r'(https?://[^\s"\'<>]+?\.mp4[^\s"\'<>]*)',
                r'source\s+src\s*=\s*["\']([^"\']+)["\']',
                r'video\s*:\s*"(https?://[^"]+)"',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    video_url = match.group(1)
                    # 清理URL
                    video_url = video_url.replace('\\/', '/').replace('\\u0026', '&')
                    
                    # 检查是否是有效的视频地址
                    if self.check_paly_url(video_url):
                        print(f"全局解析成功: {video_url}")
                        return [302, 'text/plain', video_url, {'Location': video_url}]
            
            # 如果提取失败，尝试返回解析页面的iframe内容
            print(f"全局解析失败，返回原始内容")
            return [200, 'text/html', html]
            
        except Exception as e:
            print(f"全局解析异常: {e}")
            return [500, 'text/plain', f'Parse error: {str(e)}']
    
    def _proxy_request(self, param):
        """
        纯代理转发请求（使用代理服务器，固定IP访问）
        用于解决跨域或防盗链问题
        """
        url = unquote(param.get('url', ''))
        if not url:
            return [404, 'text/plain', 'URL is required']
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': param.get('referer', url)
            }
            
            # 使用代理访问（固定IP）
            if self.proxy_url:
                print(f"使用代理 {self.proxy_url} 转发: {url}")
                response = self._proxy_fetch(url, headers, stream=True, timeout=30)
            else:
                response = requests.get(url, headers=headers, stream=True, timeout=30)
            
            # 转发响应
            content_type = response.headers.get('Content-Type', 'application/octet-stream')
            return [200, content_type, response.content]
            
        except Exception as e:
            print(f"代理转发失败: {e}")
            return [500, 'text/plain', f'Proxy error: {str(e)}']
    
    def _redirect_sniffer(self, param):
        """
        通过跟踪重定向获取真实地址（使用代理服务器，固定IP访问）
        """
        url = unquote(param.get('url', ''))
        if not url:
            return [404, 'text/plain', 'URL is required']
        
        try:
            # 使用代理跟踪重定向
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            if self.proxy_url:
                print(f"使用代理 {self.proxy_url} 跟踪重定向: {url}")
                response = self._proxy_fetch(url, headers, allow_redirects=False, timeout=20)
            else:
                response = requests.get(url, headers=headers, allow_redirects=False, timeout=20)
            
            # 检查重定向
            if 300 <= response.status_code < 400:
                redirect_location = response.headers.get('Location')
                if redirect_location:
                    real_url = urljoin(url, redirect_location)
                    print(f"重定向到: {real_url}")
                    return [302, 'text/plain', real_url, {'Location': real_url}]
            
            return [200, 'text/plain', url]
            
        except Exception as e:
            print(f"重定向跟踪失败: {e}")
            return [500, 'text/plain', f'Redirect error: {str(e)}']

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass
