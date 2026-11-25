import logging
import re

import requests
from diskcache import Cache
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from agent.custom.utils.bms import parse_song_bms


class BestdoriAPI:
    base = "https://bestdori.com/api"
    _logger = logging.getLogger("BestdoriAPI")
    _cache = Cache("cache")
    _session = requests.Session()
    _adapter = HTTPAdapter(
        max_retries=Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            connect=5,
            read=5,
        )
    )
    _session.mount("http://", _adapter)
    _session.mount("https://", _adapter)

    @staticmethod
    def _fetch_and_cache(url, cache_name, expire=None):
        if cache_ := BestdoriAPI._cache.get(cache_name):
            BestdoriAPI._logger.info(f"Cache hit for {cache_name}")
            return cache_
        else:
            response = BestdoriAPI._session.get(url).json()
            BestdoriAPI._cache.set(cache_name, response, expire=expire)
            BestdoriAPI._logger.info(f"Cache set for {cache_name}")
            return response

    @staticmethod
    def get_song_list():
        url = BestdoriAPI.base + "/songs/all.5.json"
        return BestdoriAPI._fetch_and_cache(url, "allsongs", expire=3600 * 1)

    @staticmethod
    def get_chart(song_id: str, difficulty: str):
        cacheid = f"{song_id}-{difficulty}"
        url = BestdoriAPI.base + f"/charts/{song_id}/{difficulty}.json"
        return BestdoriAPI._fetch_and_cache(url, cacheid)

    @staticmethod
    def get_bms(song_id, difficulty):
        song_id = str(song_id)
        difficulty = difficulty.lower()
        if not re.fullmatch(r"[0-9]+", song_id) or not re.fullmatch(r"[a-z]+", difficulty):
            raise ValueError("曲目 ID 或难度无效")

        cache_key = f"raw-bms:cn:{song_id}-{difficulty}"
        raw = BestdoriAPI._cache.get(cache_key)
        if raw is not None:
            chart = parse_song_bms(raw, song_id, difficulty)
            BestdoriAPI._logger.info("已读取国服 BMS 缓存 %s-%s", song_id, difficulty)
            return raw, chart

        # BMS is optional. Use short timeouts so the JSON fallback can still run.
        timeout = (3, 5)
        response = requests.get(f"{BestdoriAPI.base}/songs/{song_id}.json", timeout=timeout)
        response.raise_for_status()
        song = response.json()
        filename = song.get("bgmFile") if isinstance(song, dict) else None
        if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", filename):
            raise ValueError("曲目信息缺少有效的 BMS 文件名前缀")

        group = (int(song_id) + 9) // 10 * 10
        url = f"https://bestdori.com/assets/cn/musicscore/musicscore{group}_rip/{filename}_{difficulty}.txt"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        raw = response.content
        chart = parse_song_bms(raw, song_id, difficulty)
        BestdoriAPI._cache.set(cache_key, raw, expire=86400)
        BestdoriAPI._logger.info("已下载并解析国服 BMS %s-%s", song_id, difficulty)
        return raw, chart


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    songlist = BestdoriAPI.get_song_list()
    #chart = BestdoriAPI.get_chart(1, "easy")
    pass
