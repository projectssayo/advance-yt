from fastapi import FastAPI, HTTPException
import asyncio
import aiohttp
import hashlib
import time
from urllib.parse import urlparse, parse_qs

app = FastAPI(title="YouTube Playlist API")

class YouTubeAPI:
    def __init__(self):
        self.yt_key = "AIzaSyA9duSdozs7H8mPd1UI8plqq73BxKkpI1g"
        self.cloud_name = "dnssyb7hu"
        self.cloud_key = "546611568773363"
        self.cloud_secret = "VIwYmkPKwCMrqIBI18ickdChUK4"
        self.demo_id = "PLGjplNEQ1it_oTvuLRNqXfz_v_0pq6unW"
        self.page_limit = 50
    
    def get_time_str(self, iso):
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
    
    def get_id_from_url(self, url):
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            return qs.get("list", [""])[0]
        except:
            return ""
    
    async def get_json(self, session, url, params):
        clean = {k: v for k, v in params.items() if v}
        async with session.get(url, params=clean) as r:
            return await r.json()
    
    async def upload_img(self, session, vid):
        try:
            ts = int(time.time())
            pid = f"yt/{vid}"
            src = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
            
            sig = hashlib.sha1(f"public_id={pid}&timestamp={ts}{self.cloud_secret}".encode()).hexdigest()

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

class BasicAPI(YouTubeAPI):
    async def get_data(self, url):
        pid = self.get_id_from_url(url)
        if not pid:
            return {"status": "false", "data": []}

        async with aiohttp.ClientSession() as session:
            # Get playlist
            p_data = await self.get_json(
                session,
                "https://www.googleapis.com/youtube/v3/playlists",
                {"part": "snippet,contentDetails", "id": pid, "key": self.yt_key}
            )

            if not p_data.get("items"):
                return {"status": "false", "data": []}

            info = p_data["items"][0]["snippet"]
            stats = p_data["items"][0]["contentDetails"]

            p_info = {
                "name": info["title"],
                "desc": info.get("description", ""),
                "count": stats.get("itemCount", 0),
                "creator": info.get("channelTitle", ""),
                "creator_link": f"https://www.youtube.com/channel/{info.get('channelId','')}",
                "created": info.get("publishedAt", ""),
                "updated": ""
            }

            # Get ALL video IDs
            all_v_ids = []
            all_dates = []
            next_token = None
            
            while True:
                resp = await self.get_json(
                    session,
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    {
                        "part": "contentDetails,snippet",
                        "playlistId": pid,
                        "maxResults": self.page_limit,
                        "pageToken": next_token,
                        "key": self.yt_key
                    }
                )
                
                for item in resp.get("items", []):
                    all_v_ids.append(item["contentDetails"]["videoId"])
                    all_dates.append(item["contentDetails"].get("videoPublishedAt", ""))
                
                next_token = resp.get("nextPageToken")
                if not next_token:
                    break

            # Get last date
            if all_dates:
                dates = [d for d in all_dates if d]
                if dates:
                    p_info["updated"] = max(dates)

            # Get ALL video details
            all_videos_data = []
            
            for i in range(0, len(all_v_ids), self.page_limit):
                chunk = all_v_ids[i:i + self.page_limit]
                if not chunk:
                    continue
                    
                videos = await self.get_json(
                    session,
                    "https://www.googleapis.com/youtube/v3/videos",
                    {
                        "part": "snippet,contentDetails",
                        "id": ",".join(chunk),
                        "key": self.yt_key
                    }
                )
                
                # Store all videos
                all_videos_data.extend(videos.get("items", []))
                
                # Upload thumbnails
                tasks = []
                for v in videos.get("items", []):
                    tasks.append(self.upload_img(session, v["id"]))
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            # Build ONE single list
            final_list = []
            for idx, v in enumerate(all_videos_data, 1):
                vid = v["id"]
                final_list.append({
                    "index": idx,
                    "video_id": vid,
                    "title": v["snippet"]["title"],
                    "duration": self.get_time_str(v["contentDetails"]["duration"]),
                    "video_link": f"https://www.youtube.com/watch?v={vid}",
                    "thumb": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                    "cloud_thumb": f"https://res.cloudinary.com/{self.cloud_name}/image/upload/yt/{vid}.jpg"
                })

            return {
                "status": "true",
                "playlist_info": p_info,
                "total": len(final_list),
                "data": final_list  # Single array with ALL videos
            }

class AdvAPI(YouTubeAPI):
    async def get_data(self, url):
        pid = self.get_id_from_url(url)
        if not pid:
            return {"status": "false", "data": []}

        async with aiohttp.ClientSession() as session:
            # Get playlist
            p_data = await self.get_json(
                session,
                "https://www.googleapis.com/youtube/v3/playlists",
                {"part": "snippet,contentDetails", "id": pid, "key": self.yt_key}
            )

            if not p_data.get("items"):
                return {"status": "false", "data": []}

            info = p_data["items"][0]["snippet"]
            stats = p_data["items"][0]["contentDetails"]

            p_info = {
                "name": info["title"],
                "desc": info.get("description", ""),
                "count": stats.get("itemCount", 0),
                "creator": info.get("channelTitle", ""),
                "creator_link": f"https://www.youtube.com/channel/{info.get('channelId','')}",
                "created": info.get("publishedAt", ""),
                "updated": ""
            }

            # Get ALL video IDs
            all_v_ids = []
            all_dates = []
            next_token = None
            
            while True:
                resp = await self.get_json(
                    session,
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    {
                        "part": "contentDetails,snippet",
                        "playlistId": pid,
                        "maxResults": self.page_limit,
                        "pageToken": next_token,
                        "key": self.yt_key
                    }
                )
                
                for item in resp.get("items", []):
                    all_v_ids.append(item["contentDetails"]["videoId"])
                    all_dates.append(item["contentDetails"].get("videoPublishedAt", ""))
                
                next_token = resp.get("nextPageToken")
                if not next_token:
                    break

            # Get last date
            if all_dates:
                dates = [d for d in all_dates if d]
                if dates:
                    p_info["updated"] = max(dates)

            # Get ALL video details
            all_videos_data = []
            
            for i in range(0, len(all_v_ids), self.page_limit):
                chunk = all_v_ids[i:i + self.page_limit]
                if not chunk:
                    continue
                    
                videos = await self.get_json(
                    session,
                    "https://www.googleapis.com/youtube/v3/videos",
                    {
                        "part": "snippet,contentDetails,statistics",
                        "id": ",".join(chunk),
                        "key": self.yt_key
                    }
                )
                
                # Store all videos
                all_videos_data.extend(videos.get("items", []))
                
                # Upload thumbnails
                tasks = []
                for v in videos.get("items", []):
                    tasks.append(self.upload_img(session, v["id"]))
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            # Build ONE single list with advanced data
            final_list = []
            for idx, v in enumerate(all_videos_data, 1):
                vid = v["id"]
                chan_id = v["snippet"].get("channelId", "")
                chan_name = v["snippet"].get("channelTitle", "")
                
                final_list.append({
                    "index": idx,
                    "playlist_name": p_info["name"],
                    "playlist_desc": p_info["desc"],
                    "video_count": p_info["count"],
                    "created_by": p_info["creator"],
                    "created_by_link": p_info["creator_link"],
                    "created_on": p_info["created"],
                    "last_updated": p_info["updated"],
                    "video": {
                        "id": vid,
                        "title": v["snippet"]["title"],
                        "duration": self.get_time_str(v["contentDetails"]["duration"]),
                        "likes": v["statistics"].get("likeCount", "0"),
                        "views": v["statistics"].get("viewCount", "0"),
                        "desc": v["snippet"].get("description", ""),
                        "comments": v["statistics"].get("commentCount", "0"),
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "thumb": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                        "channel": chan_name,
                        "channel_url": f"https://www.youtube.com/channel/{chan_id}" if chan_id else ""
                    }
                })

            return {
                "status": "true",
                "playlist_info": p_info,
                "total": len(final_list),
                "data": final_list  # Single array with ALL videos
            }

# Create API instances
basic_api = BasicAPI()
adv_api = AdvAPI()

@app.get("/")
async def home():
    return {
        "msg": "YouTube Playlist API",
        "basic": "/basic?url=YOUR_URL",
        "adv": "/adv?url=YOUR_URL",
        "demo": "/info"
    }

@app.get("/basic")
async def basic_extract(url: str):
    result = await basic_api.get_data(url)
    if result["status"] == "false":
        raise HTTPException(status_code=400, detail="Invalid URL")
    return result

@app.get("/adv")
async def adv_extract(url: str):
    result = await adv_api.get_data(url)
    if result["status"] == "false":
        raise HTTPException(status_code=400, detail="Invalid URL")
    return result

@app.get("/info")
async def info():
    return {
        "basic_demo": f"/basic?url=https://youtube.com/playlist?list={basic_api.demo_id}",
        "adv_demo": f"/adv?url=https://youtube.com/playlist?list={adv_api.demo_id}"
    }
