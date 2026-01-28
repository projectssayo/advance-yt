from fastapi import FastAPI
import asyncio
import aiohttp
import hashlib
import time
from urllib.parse import urlparse, parse_qs

app = FastAPI()

class YouTubeExtractor:
    def __init__(self):
        self.yt_key = "AIzaSyA9duSdozs7H8mPd1UI8plqq73BxKkpI1g"
        self.cloud_name = "dnssyb7hu"
        self.cloud_key = "546611568773363"
        self.cloud_secret = "VIwYmkPKwCMrqIBI18ickdChUK4"
        self.demo_playlist_id = "PLGjplNEQ1it_oTvuLRNqXfz_v_0pq6unW"
        self.max_per_page = 50

    def human_time(self, iso):
        if not iso.startswith('PT'):
            return "0:00"
        
        iso = iso[2:]
        h = m = s = 0
        num = ""
        
        for c in iso:
            if c.isdigit():
                num += c
            else:
                if c == 'H':
                    h = int(num)
                elif c == 'M':
                    m = int(num)
                elif c == 'S':
                    s = int(num)
                num = ""
        
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        elif m:
            return f"{m}:{s:02d}"
        return f"0:{s:02d}"

    def get_playlist_id(self, url):
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            return qs.get("list", [""])[0]
        except:
            return ""

    async def fetch(self, session, url, params):
        params = {k: v for k, v in params.items() if v is not None}
        async with session.get(url, params=params) as r:
            return await r.json()

    async def upload_img(self, session, vid):
        try:
            ts = int(time.time())
            pid = f"yt/{vid}"
            src = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
            
            sig_str = f"public_id={pid}&timestamp={ts}{self.cloud_secret}"
            sig = hashlib.sha1(sig_str.encode()).hexdigest()

            data = {
                "file": src,
                "api_key": self.cloud_key,
                "timestamp": ts,
                "public_id": pid,
                "signature": sig
            }

            url = f"https://api.cloudinary.com/v1_1/{self.cloud_name}/image/upload"
            async with session.post(url, data=data):
                pass
        except:
            pass

class BasicExtractor(YouTubeExtractor):
    async def extract(self, url):
        pid = self.get_playlist_id(url)
        if not pid:
            return {"status": "false", "data": []}

        async with aiohttp.ClientSession() as session:
            # Get playlist info
            p_data = await self.fetch(
                session,
                "https://www.googleapis.com/youtube/v3/playlists",
                {"part": "snippet,contentDetails", "id": pid, "key": self.yt_key}
            )

            if not p_data.get("items"):
                return {"status": "false", "data": []}

            info = p_data["items"][0]["snippet"]
            stats = p_data["items"][0]["contentDetails"]

            p_meta = {
                "playlist_name": info["title"],
                "playlist_description": info.get("description", ""),
                "video_count": stats.get("itemCount", 0),
                "created_by": info.get("channelTitle", ""),
                "created_by_link": f"https://www.youtube.com/channel/{info.get('channelId','')}",
                "created_on": info.get("publishedAt", ""),
                "last_updated": ""
            }

            # Get all video IDs
            v_ids = []
            v_dates = []
            token = None
            
            while True:
                resp = await self.fetch(
                    session,
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    {
                        "part": "contentDetails,snippet",
                        "playlistId": pid,
                        "maxResults": self.max_per_page,
                        "pageToken": token,
                        "key": self.yt_key
                    }
                )
                
                for item in resp.get("items", []):
                    v_ids.append(item["contentDetails"]["videoId"])
                    v_dates.append(item["contentDetails"].get("videoPublishedAt", ""))
                
                token = resp.get("nextPageToken")
                if not token or len(v_ids) >= 300:
                    break

            # Get last updated date
            if v_dates:
                dates = [d for d in v_dates if d]
                if dates:
                    p_meta["last_updated"] = max(dates)

            # Limit to 300
            v_ids = v_ids[:300]

            # Get video details in chunks
            all_videos = []
            for i in range(0, len(v_ids), self.max_per_page):
                chunk = v_ids[i:i + self.max_per_page]
                if not chunk:
                    continue
                    
                videos = await self.fetch(
                    session,
                    "https://www.googleapis.com/youtube/v3/videos",
                    {
                        "part": "snippet,contentDetails",
                        "id": ",".join(chunk),
                        "key": self.yt_key
                    }
                )
                
                all_videos.extend(videos.get("items", []))
                
                # Upload thumbnails
                tasks = []
                for v in videos.get("items", []):
                    tasks.append(self.upload_img(session, v["id"]))
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Small delay
                if i + self.max_per_page < len(v_ids):
                    await asyncio.sleep(0.1)

            # Build result - matching exact schema
            result = []
            for idx, v in enumerate(all_videos, 1):
                vid = v["id"]
                result.append({
                    "index": idx,
                    "video_id": vid,
                    "title": v["snippet"]["title"],
                    "duration": self.human_time(v["contentDetails"]["duration"]),
                    "video_link": f"https://www.youtube.com/watch?v={vid}",
                    "original_thumbnail": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                    "thumbnail_247": f"https://res.cloudinary.com/{self.cloud_name}/image/upload/yt/{vid}.jpg"
                })

            return {
                "status": "true",
                "playlist_info": p_meta,
                "data": result
            }

class AdvExtractor(YouTubeExtractor):
    async def extract(self, url):
        pid = self.get_playlist_id(url)
        if not pid:
            return {"status": "false", "data": []}

        async with aiohttp.ClientSession() as session:
            # Get playlist info
            p_data = await self.fetch(
                session,
                "https://www.googleapis.com/youtube/v3/playlists",
                {"part": "snippet,contentDetails", "id": pid, "key": self.yt_key}
            )

            if not p_data.get("items"):
                return {"status": "false", "data": []}

            info = p_data["items"][0]["snippet"]
            stats = p_data["items"][0]["contentDetails"]

            p_meta = {
                "playlist_name": info["title"],
                "playlist_description": info.get("description", ""),
                "video_count": stats.get("itemCount", 0),
                "created_by": info.get("channelTitle", ""),
                "created_by_link": f"https://www.youtube.com/channel/{info.get('channelId','')}",
                "created_on": info.get("publishedAt", ""),
                "last_updated": ""
            }

            # Get all video IDs
            v_ids = []
            v_dates = []
            token = None
            
            while True:
                resp = await self.fetch(
                    session,
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    {
                        "part": "contentDetails,snippet",
                        "playlistId": pid,
                        "maxResults": self.max_per_page,
                        "pageToken": token,
                        "key": self.yt_key
                    }
                )
                
                for item in resp.get("items", []):
                    v_ids.append(item["contentDetails"]["videoId"])
                    v_dates.append(item["contentDetails"].get("videoPublishedAt", ""))
                
                token = resp.get("nextPageToken")
                if not token or len(v_ids) >= 300:
                    break

            # Get last updated date
            if v_dates:
                dates = [d for d in v_dates if d]
                if dates:
                    p_meta["last_updated"] = max(dates)

            # Limit to 300
            v_ids = v_ids[:300]

            # Get video details in chunks
            all_videos = []
            for i in range(0, len(v_ids), self.max_per_page):
                chunk = v_ids[i:i + self.max_per_page]
                if not chunk:
                    continue
                    
                videos = await self.fetch(
                    session,
                    "https://www.googleapis.com/youtube/v3/videos",
                    {
                        "part": "snippet,contentDetails,statistics",
                        "id": ",".join(chunk),
                        "key": self.yt_key
                    }
                )
                
                all_videos.extend(videos.get("items", []))
                
                # Upload thumbnails
                tasks = []
                for v in videos.get("items", []):
                    tasks.append(self.upload_img(session, v["id"]))
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Small delay
                if i + self.max_per_page < len(v_ids):
                    await asyncio.sleep(0.1)

            # Build result - matching exact schema
            result = []
            for idx, v in enumerate(all_videos, 1):
                vid = v["id"]
                chan_id = v["snippet"].get("channelId", "")
                chan_name = v["snippet"].get("channelTitle", "")
                
                result.append({
                    "index": idx,
                    "playlist_name": p_meta["playlist_name"],
                    "playlist_description": p_meta["playlist_description"],
                    "video_count": p_meta["video_count"],
                    "created_by": p_meta["created_by"],
                    "created_by_link": p_meta["created_by_link"],
                    "created_on": p_meta["created_on"],
                    "last_updated": p_meta["last_updated"],
                    "video": {
                        "video_id": vid,
                        "video_title": v["snippet"]["title"],
                        "video_duration": self.human_time(v["contentDetails"]["duration"]),
                        "video_likes": v["statistics"].get("likeCount", "0"),
                        "views": v["statistics"].get("viewCount", "0"),
                        "description": v["snippet"].get("description", ""),
                        "number_of_comments": v["statistics"].get("commentCount", "0"),
                        "video_url": f"https://www.youtube.com/watch?v={vid}",
                        "video_thumbnail": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                        "channel_name": chan_name,
                        "channel_link": f"https://www.youtube.com/channel/{chan_id}" if chan_id else ""
                    }
                })

            return {
                "status": "true",
                "playlist_info": p_meta,
                "data": result
            }

# Create instances
basic = BasicExtractor()
adv = AdvExtractor()

@app.get("/")
async def home():
    return {
        "msg": "YouTube Playlist Extractor",
        "basic": "/basic?url=YOUR_PLAYLIST_URL",
        "adv": "/adv?url=YOUR_PLAYLIST_URL",
        "demo": "/info",
        "limit": "300 videos max, 50 per API call"
    }

@app.get("/basic")
async def basic_extract(url: str):
    return await basic.extract(url)

@app.get("/adv")
async def adv_extract(url: str):
    return await adv.extract(url)

@app.get("/info")
async def info():
    return {
        "basic_demo": f"/basic?url=https://youtube.com/playlist?list={basic.demo_playlist_id}",
        "adv_demo": f"/adv?url=https://youtube.com/playlist?list={adv.demo_playlist_id}",
        "status": "ok"
    }
