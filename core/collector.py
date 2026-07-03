"""
抖音收藏夹采集模块
通过 Chrome CDP 连接本地浏览器，采集收藏夹视频列表
"""
import re
import time
import json
import requests
from typing import List, Dict, Optional, Callable
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext

from .config import AppConfig


class DouyinCollector:
    """抖音收藏夹采集器"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.pw = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def connect(self) -> bool:
        """连接到 Chrome CDP"""
        try:
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.connect_over_cdp(
                f"http://localhost:{self.config.douyin.chrome_debug_port}"
            )
            self.context = self.browser.contexts[0]
            self.page = self.context.pages[0]
            return True
        except Exception as e:
            print(f"[ERROR] 连接 Chrome 失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        try:
            if self.pw:
                self.pw.stop()
        except Exception:
            pass

    def check_login(self) -> bool:
        """检查是否已登录抖音"""
        try:
            # 先确保页面已加载
            self.page.wait_for_load_state('domcontentloaded', timeout=10000)
            time.sleep(3)
            return self.page.evaluate("""() => {
                const t = document.body.innerText || '';
                // 兼容新旧版UI: 旧版有"私信", 新版有"消息"
                return t.includes('通知') && (t.includes('私信') || t.includes('消息'));
            }""")
        except Exception:
            return False

    def navigate(self, url: str, wait: int = 5):
        """导航到页面"""
        try:
            self.page.goto(url, timeout=30000, wait_until='domcontentloaded')
        except Exception:
            pass
        time.sleep(wait)

    def fetch_api(self, url: str) -> Dict:
        """在浏览器中执行 fetch 请求"""
        try:
            return self.page.evaluate(f"""async () => {{
                try {{
                    const res = await fetch('{url}', {{credentials: 'include'}});
                    const t = await res.text();
                    try {{ return JSON.parse(t); }} catch(e) {{ return {{error: 'json', raw: t.substring(0,300)}}; }}
                }} catch(e) {{ return {{error: e.message}}; }}
            }}""")
        except Exception as e:
            return {'error': str(e)}

    def fetch_bytes(self, url: str) -> Optional[bytes]:
        """下载二进制内容（视频、封面等）"""
        cookies = {}
        for c in self.context.cookies('https://www.douyin.com'):
            cookies[c['name']] = c['value']
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.douyin.com/',
        }
        try:
            resp = requests.get(url, headers=headers, cookies=cookies, timeout=60)
            if resp.status_code == 200 and len(resp.content) > 10000:
                return resp.content
        except Exception:
            pass
        return None

    def extract_video_info(self, item: Dict) -> Dict:
        """从抖音 API 返回的 item 中提取视频信息"""
        video = {}

        # 基础信息
        video['aweme_id'] = str(item.get('aweme_id', ''))
        desc = item.get('desc', '')
        video['title'] = desc.replace('\n', ' ').strip()[:100]
        video['description'] = desc

        # 作者信息
        author_info = item.get('author', {})
        video['author'] = author_info.get('nickname', '')
        video['author_id'] = author_info.get('sec_uid', '')
        video['author_avatar'] = author_info.get('avatar_larger', {}).get('url_list', [''])[0]

        # 封面
        video_data = item.get('video', {})
        cover = video_data.get('cover', {}).get('url_list', [''])
        video['cover_url'] = cover[0] if cover else ''

        # 视频地址
        play_addr = video_data.get('play_addr', {})
        urls = play_addr.get('url_list', [])
        video['video_url'] = urls[0] if urls else ''

        # 时长
        video['duration'] = video_data.get('duration', 0)

        # 时间
        video['create_time'] = item.get('create_time', 0)

        # 互动数据
        statistics = item.get('statistics', {})
        video['like_count'] = statistics.get('digg_count', 0)
        video['comment_count'] = statistics.get('comment_count', 0)
        video['share_count'] = statistics.get('share_count', 0)
        video['collect_count'] = statistics.get('collect_count', 0)
        video['play_count'] = statistics.get('play_count', 0)

        # 音乐
        music = item.get('music', {})
        video['music_title'] = music.get('title', '')
        video['music_author'] = music.get('author', '')

        # 标签（从 description 中提取 # 标签）
        tags = re.findall(r'#(\S+?)(?:\s|$)', desc)
        video['tags'] = tags

        return video

    def collect_collection(self, progress_callback: Callable = None) -> List[Dict]:
        """
        采集收藏夹视频列表
        通过拦截 listcollection API 响应获取数据
        """
        collected = {}
        response_videos = {}

        def on_collection_response(resp):
            """拦截收藏接口响应"""
            try:
                if '/aweme/v1/web/aweme/listcollection/' not in resp.url:
                    return
                data = resp.json()
                aweme_list = data.get('aweme_list') or []
                for item in aweme_list:
                    aid = str(item.get('aweme_id', ''))
                    if aid and aid not in response_videos:
                        video = self.extract_video_info(item)
                        video['source_mode'] = 'collection'
                        response_videos[aid] = video
            except Exception:
                return

        # 注册响应拦截器
        self.page.on('response', on_collection_response)

        # 导航到收藏页面
        self.navigate('https://www.douyin.com/user/self?showTab=favorite_collection', wait=8)

        # 点击"收藏"标签
        self.page.evaluate("""() => {
            const tabs = document.querySelectorAll('span, div, a, button');
            for (const t of tabs) {
                if (t.textContent.trim() === '收藏' && t.children.length <= 1) {
                    t.click();
                    return 'collection';
                }
            }
            return 'not found';
        }""")
        time.sleep(2)

        # 点击"视频"子标签
        self.page.evaluate("""() => {
            const tabs = document.querySelectorAll('span, div, a, button');
            for (const t of tabs) {
                if (t.textContent.trim() === '视频' && t.children.length <= 1) {
                    t.click();
                    return 'video';
                }
            }
            return 'not found';
        }""")
        time.sleep(3)

        # 滚动加载更多
        stable_rounds = 0
        last_count = 0
        for scroll_round in range(18):
            if progress_callback:
                progress_callback(f'收藏接口视频: {len(response_videos)}个', min(45, 8 + scroll_round * 3))

            self.page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.2)

            if len(response_videos) == last_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
                last_count = len(response_videos)

            if stable_rounds >= 3:
                break

        # 移除拦截器
        try:
            self.page.remove_listener('response', on_collection_response)
        except Exception:
            pass

        collected = response_videos
        return list(collected.values())

    def collect_liked(self, progress_callback: Callable = None) -> List[Dict]:
        """采集喜欢列表"""
        collected = {}
        max_cursor = "0"
        page_num = 0

        self.navigate('https://www.douyin.com/user/self', wait=6)

        while True:
            page_num += 1
            api_url = (
                f'https://www.douyin.com/aweme/v1/web/aweme/favorite/?device_platform=webapp&aid=6383'
                f'&channel=channel_pc_web&sec_user_id=self&max_cursor={max_cursor}'
                f'&locate_query=false&count=20&pc_client_type=1&version_code=170400'
                f'&version_name=17.4.0&cookie_enabled=true&screen_width=1920&screen_height=1080'
                f'&browser_language=zh-CN&browser_platform=Win32&browser_name=Chrome'
                f'&browser_version=126.0.0.0&browser_online=true&platform=PC'
            )
            result = self.fetch_api(api_url)
            if not result or result.get('error') or not result.get('aweme_list'):
                break

            for item in result['aweme_list']:
                aid = str(item.get('aweme_id', ''))
                if aid and aid not in collected:
                    collected[aid] = self.extract_video_info(item)

            has_more = result.get('has_more', False)
            max_cursor = str(result.get('max_cursor', ''))

            if progress_callback:
                progress_callback(f'第{page_num}页: 总计{len(collected)}个', min(50, page_num * 10))

            if not has_more or not max_cursor:
                break
            time.sleep(0.5)

        return list(collected.values())

    def collect_user_videos(self, user_url: str, progress_callback: Callable = None) -> List[Dict]:
        """采集指定用户的视频列表"""
        m = re.search(r'/user/([^\s?]+)', user_url)
        sec_user_id = m.group(1) if m else ''

        if not sec_user_id:
            return []

        collected = {}
        max_cursor = "0"
        page_num = 0

        self.navigate(user_url, wait=6)

        while True:
            page_num += 1
            api_url = (
                f'https://www.douyin.com/aweme/v1/web/aweme/post/?device_platform=webapp&aid=6383'
                f'&channel=channel_pc_web&sec_user_id={sec_user_id}&max_cursor={max_cursor}'
                f'&locate_query=false&publish_video_strategy_type=2&pc_client_type=1'
                f'&version_code=170400&version_name=17.4.0&cookie_enabled=true'
                f'&screen_width=1920&screen_height=1080&browser_language=zh-CN'
                f'&browser_platform=Win32&browser_name=Chrome&browser_version=126.0.0.0'
                f'&browser_online=true&platform=PC'
            )
            result = self.fetch_api(api_url)
            if not result or result.get('error') or not result.get('aweme_list'):
                break

            for item in result['aweme_list']:
                aid = str(item.get('aweme_id', ''))
                if aid and aid not in collected:
                    collected[aid] = self.extract_video_info(item)

            has_more = result.get('has_more', False)
            max_cursor = str(result.get('max_cursor', ''))

            if progress_callback:
                progress_callback(f'第{page_num}页: 总计{len(collected)}个', min(50, page_num * 10))

            if not has_more or not max_cursor:
                break
            time.sleep(0.5)

        return list(collected.values())

    def download_video(self, video: Dict, save_dir: str) -> Optional[str]:
        """下载单个视频文件"""
        video_url = video.get('video_url', '')
        if not video_url:
            return None

        aweme_id = video['aweme_id']
        save_path = f"{save_dir}/{aweme_id}.mp4"

        content = self.fetch_bytes(video_url)
        if content:
            with open(save_path, 'wb') as f:
                f.write(content)
            return save_path

        return None

    def download_cover(self, video: Dict, save_dir: str) -> Optional[str]:
        """下载视频封面"""
        cover_url = video.get('cover_url', '')
        if not cover_url:
            return None

        aweme_id = video['aweme_id']
        save_path = f"{save_dir}/{aweme_id}_cover.jpg"

        content = self.fetch_bytes(cover_url)
        if content:
            with open(save_path, 'wb') as f:
                f.write(content)
            return save_path

        return None
