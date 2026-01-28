from fastapi import FastAPI
import asyncio
import aiohttp
import hashlib
import time
from urllib.parse import urlparse, parse_qs

class advPlaylistExtractor:
    def __init__(self):
        self.yt_key = "AIzaSyA9duSdozs7H8mPd1UI8plqq73BxKkpI1g"
        self.cloud_name = "dnssyb7hu"
        self.cloud_key = "546611568773363"
        self.cloud_secret = "VIwYmkPKwCMrqIBI18ickdChUK4"
        # Demo playlist ID
        self.demo_playlist_id = "PLGjplNEQ1it_oTvuLRNqXfz_v_0pq6unW"

    def human_duration(self, iso):
        h = m = s = 0
        num = ""
        for c in iso.replace("PT", ""):
            if c.isdigit():
                num += c
            else:
                if c == "H":
                    h = int(num)
                elif c == "M":
                    m = int(num)
                elif c == "S":
                    s = int(num)
                num = ""
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        if m:
            return f"{m}:{s:02d}"
        return f"{s}s"

    def extract_playlist_id(self, url: str):
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        return qs.get("list", [""])[0]

    async def _fetch(self, session, url, params):
        params = {k: v for k, v in params.items() if v is not None}
        async with session.get(url, params=params) as r:
            return await r.json()

    async def _upload_thumbnail(self, session, video_id):
        # Dummy Cloudinary upload
        timestamp = int(time.time())
        public_id = f"yt/{video_id}"
        source = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        sign = f"public_id={public_id}&timestamp={timestamp}{self.cloud_secret}"
        signature = hashlib.sha1(sign.encode()).hexdigest()

        data = {
            "file": source,
            "api_key": self.cloud_key,
            "timestamp": timestamp,
            "public_id": public_id,
            "signature": signature
        }

        url = f"https://api.cloudinary.com/v1_1/{self.cloud_name}/image/upload"
        async with session.post(url, data=data):
            pass

    async def extract(self, playlist_url: str):
        playlist_id = self.extract_playlist_id(playlist_url)
        if not playlist_id:
            return {"status": "false", "data": []}

        async with aiohttp.ClientSession() as session:
            playlist_info = await self._fetch(
                session,
                "https://www.googleapis.com/youtube/v3/playlists",
                {"part": "snippet,contentDetails", "id": playlist_id, "key": self.yt_key}
            )

            if not playlist_info.get("items"):
                return {"status": "false", "data": []}

            p_info = playlist_info["items"][0]["snippet"]
            p_stats = playlist_info["items"][0]["contentDetails"]

            playlist_meta = {
                "playlist_name": p_info["title"],
                "playlist_description": p_info.get("description", ""),
                "video_count": p_stats.get("itemCount", 0),
                "created_by": p_info.get("channelTitle", ""),
                "created_by_link": f"https://www.youtube.com/channel/{p_info.get('channelId','')}",
                "created_on": p_info.get("publishedAt", ""),
                "last_updated": ""
            }

            video_ids = []
            video_dates = []
            token = None
            while True:
                resp = await self._fetch(
                    session,
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    {"part": "contentDetails,snippet",
                     "playlistId": playlist_id,
                     "maxResults": 50,
                     "pageToken": token,
                     "key": self.yt_key}
                )
                for item in resp.get("items", []):
                    video_ids.append(item["contentDetails"]["videoId"])
                    video_dates.append(item["contentDetails"].get("videoPublishedAt", ""))
                token = resp.get("nextPageToken")
                if not token:
                    break

            if video_dates:
                playlist_meta["last_updated"] = max([d for d in video_dates if d])

            result = {"status": "true", "playlist_info": playlist_meta, "data": []}

            for i in range(0, len(video_ids), 50):
                chunk = video_ids[i:i + 50]
                videos = await self._fetch(
                    session,
                    "https://www.googleapis.com/youtube/v3/videos",
                    {"part": "snippet,contentDetails,statistics",
                     "id": ",".join(chunk),
                     "key": self.yt_key}
                )

                await asyncio.gather(*[self._upload_thumbnail(session, v["id"]) for v in videos.get("items", [])])

                for v in videos.get("items", []):
                    vid = v["id"]
                    duration = self.human_duration(v["contentDetails"]["duration"])
                    channel_id = v["snippet"].get("channelId", "")
                    channel_title = v["snippet"].get("channelTitle", "")

                    result["data"].append({
                        "index": len(result["data"]) + 1,
                        "playlist_name": playlist_meta["playlist_name"],
                        "playlist_description": playlist_meta["playlist_description"],
                        "video_count": playlist_meta["video_count"],
                        "created_by": playlist_meta["created_by"],
                        "created_by_link": playlist_meta["created_by_link"],
                        "created_on": playlist_meta["created_on"],
                        "last_updated": playlist_meta["last_updated"],
                        "video": {
                            "video_id": vid,
                            "video_title": v["snippet"]["title"],
                            "video_duration": duration,
                            "video_likes": v["statistics"].get("likeCount"),
                            "views": v["statistics"].get("viewCount"),
                            "description": v["snippet"]["description"],
                            "number_of_comments": v["statistics"].get("commentCount"),
                            "video_url": f"https://www.youtube.com/watch?v={vid}",
                            "video_thumbnail": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                            "channel_name": channel_title,
                            "channel_link": f"https://www.youtube.com/channel/{channel_id}"
                        }
                    })

            return result

    def get_demo_url(self):
        # Return full local demo URL
        return {
            "demo_url": f"http://127.0.0.1:8000/adv?url=https://www.youtube.com/playlist?list={self.demo_playlist_id}",
            "status": "alive"
        }


import asyncio
import aiohttp
import hashlib
import time
from fastapi import FastAPI
from urllib.parse import urlparse, parse_qs

class basicPlaylistExtractor:
    def __init__(self):
        self.yt_key = "AIzaSyA9duSdozs7H8mPd1UI8plqq73BxKkpI1g"
        self.cloud_name = "dnssyb7hu"
        self.cloud_key = "546611568773363"
        self.cloud_secret = "VIwYmkPKwCMrqIBI18ickdChUK4"
        # Demo playlist ID
        self.demo_playlist_id = "PLGjplNEQ1it_oTvuLRNqXfz_v_0pq6unW"

    def human_duration(self, iso):
        h = m = s = 0
        num = ""
        for c in iso.replace("PT", ""):
            if c.isdigit():
                num += c
            else:
                if c == "H":
                    h = int(num)
                elif c == "M":
                    m = int(num)
                elif c == "S":
                    s = int(num)
                num = ""
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        if m:
            return f"{m}:{s:02d}"
        return f"{s}s"

    def extract_playlist_id(self, url: str):
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        return qs.get("list", [""])[0]

    async def _fetch(self, session, url, params):
        params = {k: v for k, v in params.items() if v is not None}
        async with session.get(url, params=params) as r:
            return await r.json()

    async def _upload_thumbnail(self, session, video_id):
        # Dummy Cloudinary upload
        timestamp = int(time.time())
        public_id = f"yt/{video_id}"
        source = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        sign = f"public_id={public_id}&timestamp={timestamp}{self.cloud_secret}"
        signature = hashlib.sha1(sign.encode()).hexdigest()

        data = {
            "file": source,
            "api_key": self.cloud_key,
            "timestamp": timestamp,
            "public_id": public_id,
            "signature": signature
        }

        url = f"https://api.cloudinary.com/v1_1/{self.cloud_name}/image/upload"
        async with session.post(url, data=data):
            pass

    async def extract(self, playlist_url: str):
        playlist_id = self.extract_playlist_id(playlist_url)
        if not playlist_id:
            return {"status": "false", "data": []}

        async with aiohttp.ClientSession() as session:
            # Get playlist info
            playlist_info = await self._fetch(
                session,
                "https://www.googleapis.com/youtube/v3/playlists",
                {"part": "snippet,contentDetails", "id": playlist_id, "key": self.yt_key}
            )

            if not playlist_info.get("items"):
                return {"status": "false", "data": []}

            p_info = playlist_info["items"][0]["snippet"]
            p_stats = playlist_info["items"][0]["contentDetails"]

            playlist_meta = {
                "playlist_name": p_info["title"],
                "playlist_description": p_info.get("description", ""),
                "video_count": p_stats.get("itemCount", 0),
                "created_by": p_info.get("channelTitle", ""),
                "created_by_link": f"https://www.youtube.com/channel/{p_info.get('channelId','')}",
                "created_on": p_info.get("publishedAt", ""),
                "last_updated": ""
            }

            # Fetch videos
            video_ids = []
            video_dates = []
            token = None
            while True:
                resp = await self._fetch(
                    session,
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    {"part": "contentDetails",
                     "playlistId": playlist_id,
                     "maxResults": 50,
                     "pageToken": token,
                     "key": self.yt_key}
                )
                for item in resp.get("items", []):
                    video_ids.append(item["contentDetails"]["videoId"])
                    video_dates.append(item["contentDetails"].get("videoPublishedAt", ""))
                token = resp.get("nextPageToken")
                if not token:
                    break

            if video_dates:
                playlist_meta["last_updated"] = max([d for d in video_dates if d])

            result = {"status": "true", "playlist_info": playlist_meta, "data": []}

            for i in range(0, len(video_ids), 50):
                chunk = video_ids[i:i + 50]
                videos = await self._fetch(
                    session,
                    "https://www.googleapis.com/youtube/v3/videos",
                    {"part": "snippet,contentDetails",
                     "id": ",".join(chunk),
                     "key": self.yt_key}
                )

                await asyncio.gather(*[self._upload_thumbnail(session, v["id"]) for v in videos.get("items", [])])

                for v in videos.get("items", []):
                    vid = v["id"]
                    result["data"].append({
                        "index": len(result["data"]) + 1,
                        "video_id": vid,
                        "title": v["snippet"]["title"],
                        "duration": self.human_duration(v["contentDetails"]["duration"]),
                        "video_link": f"https://www.youtube.com/watch?v={vid}",
                        "original_thumbnail": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                        "thumbnail_247": f"https://res.cloudinary.com/{self.cloud_name}/image/upload/yt/{vid}.jpg"
                    })

            return result

    def get_demo_url(self):
        return {
            "demo_url": f"http://127.0.0.1:8000/basic?url=https://www.youtube.com/playlist?list={self.demo_playlist_id}",
            "status": "alive"
        }


# -------------------------
# FastAPI app
# -------------------------
app = FastAPI()
extractor = basicPlaylistExtractor()

@app.get("/basic")
async def basic(url: str):
    return await extractor.extract(url)

extractor2 = advPlaylistExtractor()

@app.get("/adv")
async def adv(url: str):
    return await extractor2.extract(url)

@app.get("/info")
def info():
    return extractor.get_demo_url()

