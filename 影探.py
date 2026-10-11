import re, sys, json, base64
from Crypto.Cipher import AES
from urllib.parse import urljoin, quote
from Crypto.Util.Padding import unpad
from base.spider import Spider

sys.path.append('..')


class Spider(Spider):
    headers = {'User-Agent': 'okhttp/4.12.0'}
    # 瑙ｆ瀽鎺ュ彛璇锋眰澶�(涓� PHP 绔竴鑷�)
    parse_headers = {'User-Agent': 'okhttp-okgo/jeasonlzy'}

    FIXED_CONFIG = {
        'host': 'http://cms.lyyytv.cn',
        'cmskey': 'wP5bvxoc3yv7FoBQENFZuAF0EUYr4LTy',
        'RawPlayUrl': 0,
        # ldmax 鍐呯疆瑙ｆ瀽鎺ュ彛
        'parse_api': 'http://4kzj.lyyytv.cn/api/index?parsesId=11&appid=10001&videoUrl='
    }

    def init(self, extend=''):
        self.host = self.FIXED_CONFIG['host']
        self.cmskey = self.FIXED_CONFIG.get('cmskey', '')
        self.parse_api = self.FIXED_CONFIG.get('parse_api', '')
        raw_play_url = self.FIXED_CONFIG.get('RawPlayUrl', 0)
        if raw_play_url == 1:
            self.raw_play_url = 1
        else:
            self.raw_play_url = 0

    def ldmax_decrypt(self, encrypted_base64, depth=0):
        # 瀵瑰簲 PHP 鐨� LdmaxDecryptor::decrypt,閫掑綊瑙ｅ瘑 ldmax.cooom 鍔犲瘑閾炬帴
        if depth > 5:
            return None
        # 涓ユ牸 base64 瑙ｇ爜(瀵瑰簲 PHP base64_decode 绗簩鍙� true),
        # 闈炴硶 base64(濡傛槑鏂嘦RL)鐩存帴鍘熸牱杩斿洖
        cleaned = re.sub(r'\s+', '', encrypted_base64)
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
        except Exception:
            return None
        try:
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
        # 瀵瑰簲 PHP 涓绘祦绋�:瑙ｅ瘑 -> 璋冪敤瑙ｆ瀽鎺ュ彛 -> 浜屾瑙ｅ瘑
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
        # 鏋勫缓URL鏌ヨ鍙傛暟
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
        # 绉婚櫎URL涓殑鐧惧垎鍙风紪鐮侊紙濡� %26 %20 绛夛級锛岀洿鎺ュ垹闄よ€岄潪瑙ｇ爜
        # 渚�: 04.鍥�%26绮�.mp4 鈫� 04.鍥界菠.mp4
        video_id = re.sub(r'%[0-9A-Fa-f]{2}', '', video_id)
        # 闇€瑕佸唴缃В鏋愮殑鎯呭喌:
        # 1. 闈炴槑鏂嘦RL(base64瀵嗘枃绛�)
        # 2. 鏈珯鍩熷悕URL(lyyytv.cn 浼洿閾�,闇€缁� parse_api 浜屾瑙ｆ瀽鎵嶈兘鎷垮埌鐪熷疄鎾斁鍦板潃)
        is_plain_url = video_id.startswith(('http://', 'https://'))
        if (not is_plain_url) or (is_plain_url and 'lyyytv.cn' in video_id):
            parsed = self.ldmax_parse(video_id)
            if parsed:
                return {'jx': 0, 'parse': 0, 'playUrl': '', 'url': parsed['url'], 'header': self.headers}
        # 鐪熸鐨勭洿閾�(mp4/m3u8 绛�)鐩存帴鎾斁
        if self.check_paly_url(video_id):
            return {'jx': 0, 'parse': 0, 'playUrl': '', 'url': video_id, 'header': self.headers}
        # 鍏朵粬鎯呭喌浜ょ粰 tvbox 澶栫疆瑙ｆ瀽
        return {'jx': 1, 'playUrl': '', 'parse': 0, 'url': video_id, 'header': self.headers}

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
        pass

    def localProxy(self, param):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass
