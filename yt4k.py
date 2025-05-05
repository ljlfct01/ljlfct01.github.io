# -*- coding: utf-8 -*-
# by @嗷呜
import re
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from binascii import Error as BinasciiError
import sys
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):

    def init(self, extend=""):
        '''
        example:
        {
            "key": "py_appV2",
            "name": "xxx",
            "type": 3,
            "searchable": 1,
            "quickSearch": 1,
            "filterable": 1,
            "api": "./py/影探.py",
            "ext": "http://cmsyt.lyyytv.cn"
        }
        
        '''

        self.host=extend
        pass

    def getName(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    headers = {
        'User-Agent': 'okhttp/4.12.0',
    }

    def homeContent(self, filter):
        data = self.fetch(f"{self.host}/api.php/app/nav?token=",headers=self.headers).json()
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
                    value_array = [{"n": value.strip(), "v": value.strip()} for value in values if
                                   value.strip() != ""]
                    filters[str(item["type_id"])].append({"key": dkey, "name": dkey, "value": value_array})
        result = {}
        result["class"] = classes
        result["filters"] = filters
        return result

    def check_paly_url(self,content):
        pattern = r"https?://.*(?:\.(?:avi|wmv|wmp|wm|asf|mpg|mpeg|mpe|m1v|m2v|mpv2|mp2v|ts|tp|tpr|trp|vob|ifo|ogm|ogv|mp4|m4v|m4p|m4b|3gp|3gpp|3g2|3gp2|mkv|rm|ram|rmvb|rpm|flv|mov|qt|nsv|dpg|m2ts|m2t|mts|dvr-ms|k3g|skm|evo|nsr|amv|divx|webm|wtv|f4v|mxf)|[\w\-_]+\.lyyytv\.cn\/.)"
        regex = re.compile(pattern, re.IGNORECASE | re.VERBOSE)
        return regex.search(content) is not None

    def homeVideoContent(self):
        data=self.fetch(f"{self.host}/api.php/app/index_video?token=",headers=self.headers).json()
        videos=[]
        for item in data['list']:videos.extend(item['vlist'])
        return {'list':videos}

    def categoryContent(self, tid, pg, filter, extend):
        params = {'tid':tid,'class':extend.get('class',''),'area':extend.get('area',''),'lang':extend.get('lang',''),'year':extend.get('year',''),'limit':'18','pg':pg}
        data=self.fetch(f"{self.host}/api.php/app/video",params=params,headers=self.headers).json()
        return data

    def ui6_lvdou(self, text ,cmskey = 'z0afJ9wfCMDuLwDMJqFHwFGmaxCzC5zM'):
        key = cmskey[:16].encode("utf-8")
        iv = cmskey[-16:].encode("utf-8")

        original_text = text
        url_prefix = "lvdou+"
        if original_text.startswith(url_prefix):
            ciphertext_b64 = original_text[len(url_prefix):]
            try:
                cipher = AES.new(key, AES.MODE_CBC, iv)
                ct_bytes = base64.b64decode(ciphertext_b64)
                pt_bytes = cipher.decrypt(ct_bytes)
                pt = unpad(pt_bytes, AES.block_size)
                decrypted_text = pt.decode('utf-8')
                return decrypted_text
            except (BinasciiError, ValueError, UnicodeDecodeError):
                # 捕获Base64解码错误、填充错误或解码失败异常
                return original_text
        else:
            return original_text

    def detailContent(self, ids):
        data=self.fetch(f"{self.host}/api.php/app/video_detail?id={ids[0]}",headers=self.headers).json()
        new_vod_play_url = self.process_playlist(data['data']['vod_play_url'])
        data['data']['vod_play_url'] = new_vod_play_url
        #print(self.ui6_lvdou('lvdou++n8/tmDZnKQlM6vQDsFYfufbDlNRktSi6ze5FQENoDj0IMBDOeo5j7VjZimZmOWxCvk1eRlIGqC+ppyHm8QkOQ=='))

        return  {'list':[data['data']]}

    def searchContent(self, key, quick, pg="1"):
        data=self.fetch(f"{self.host}/api.php/app/search?text={key}&pg={pg}",headers=self.headers).json()
        videos=data['list']
        for item in data['list']:
            item.pop('type', None)
        return {'list':videos,'page':pg}

    def playerContent(self, flag, id, vipFlags):
        jx = 1; parse = 1
        if self.check_paly_url(id):
            jx = 0; parse = 0
        return {'jx': jx, 'playUrl': '', 'parse': parse, 'url': id, 'header': self.headers}

    def localProxy(self, param):
        pass

    def process_playlist(self,original_str):
        # 分割播放列表（无需异常处理，split不抛异常）
        playlists = original_str.split('$$$')
        processed_playlists = []

        for playlist in playlists:
            # 分割剧集（无需异常处理）
            episodes = playlist.split('#')
            processed_episodes = []

            for episode in episodes:
                # 分割名称和URL（最多一次分割）
                parts = episode.split('$', 1)
                if len(parts) < 2:
                    # 格式错误则保留原内容
                    processed_episodes.append(episode)
                    continue

                name, url = parts[0], parts[1]
                # 尝试解码URL
                try:
                    decoded_url = self.ui6_lvdou(url)
                except Exception:
                    decoded_url = url  # 解码失败则保留原URL

                # 重组剧集信息
                processed_episode = f"{name}${decoded_url}"
                processed_episodes.append(processed_episode)

            # 重组播放列表
            processed_playlist = '#'.join(processed_episodes)
            processed_playlists.append(processed_playlist)

        # 重组最终结果
        return '$$$'.join(processed_playlists)
