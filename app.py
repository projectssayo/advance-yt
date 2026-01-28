from fastapi import FastAPI, HTTPException
import asyncio
import aiohttp
import hashlib
import time
from typing import List, Dict, Any
from urllib.parse import urlparse, parse_qs

app = FastAPI()

class YouTubePlaylistExtractor:
    def __init__(self):
        self.yt_key = "AIzaSyA9duSdozs7H8mPd1UI8plqq73BxKkpI1g"
        self.cloud_name = "dnssyb7hu"
        self.cloud_key = "546611568773363"
        self.cloud_secret = "VIwYmkPKwCMrqIBI18ickdChUK4"
        self.demo_playlist_id = "PLGjplNEQ1it_oTvuLRNqXfz_v_0pq6unW"
        self.max_results_per_page = 50  # YouTube API limit

    def human_duration(self, iso_duration: str) -> str:
        """Convert ISO 8601 duration to human readable format"""
        if not iso_duration.startswith('PT'):
            return "0:00"
        
        iso_duration = iso_duration[2:]
        h = m = s = 0
        num = ""
        
        for c in iso_duration:
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

    def extract_playlist_id(self, url: str) -> str:
        """Extract playlist ID from YouTube URL"""
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            return qs.get("list", [""])[0]
        except:
            return ""

    async def _fetch_with_retry(self, session: aiohttp.ClientSession, 
                               url: str, params: Dict[str, Any], 
                               max_retries: int = 3) -> Dict[str, Any]:
        """Fetch data with retry logic"""
        for attempt in range(max_retries):
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 429:  # Rate limited
                        wait_time = (2 ** attempt) * 2  # Exponential backoff
                        await asyncio.sleep(wait_time)
                        continue
                    
                    response.raise_for_status()
                    return await response.json()
                    
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == max_retries - 1:
                    raise HTTPException(status_code=500, detail=f"Failed to fetch data: {str(e)}")
                await asyncio.sleep(1 * (attempt + 1))
        
        return {}

    async def _upload_thumbnail_to_cloudinary(self, session: aiohttp.ClientSession, video_id: str) -> None:
        """Upload thumbnail to Cloudinary"""
        try:
            timestamp = int(time.time())
            public_id = f"yt/{video_id}"
            source = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
            
            # Generate signature
            sign_string = f"public_id={public_id}&timestamp={timestamp}{self.cloud_secret}"
            signature = hashlib.sha1(sign_string.encode()).hexdigest()

            data = {
                "file": source,
                "api_key": self.cloud_key,
                "timestamp": timestamp,
                "public_id": public_id,
                "signature": signature
            }

            cloudinary_url = f"https://api.cloudinary.com/v1_1/{self.cloud_name}/image/upload"
            
            async with session.post(cloudinary_url, data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    print(f"Warning: Failed to upload thumbnail for video {video_id}")
        except Exception as e:
            print(f"Error uploading thumbnail for {video_id}: {str(e)}")

    async def _fetch_all_playlist_items(self, session: aiohttp.ClientSession, 
                                       playlist_id: str) -> tuple[List[str], List[str]]:
        """Fetch all video IDs from a playlist with pagination"""
        video_ids = []
        video_dates = []
        next_page_token = None
        
        while True:
            params = {
                "part": "contentDetails,snippet",
                "playlistId": playlist_id,
                "maxResults": self.max_results_per_page,
                "key": self.yt_key
            }
            
            if next_page_token:
                params["pageToken"] = next_page_token
            
            response = await self._fetch_with_retry(
                session,
                "https://www.googleapis.com/youtube/v3/playlistItems",
                params
            )
            
            items = response.get("items", [])
            for item in items:
                video_ids.append(item["contentDetails"]["videoId"])
                video_dates.append(item["contentDetails"].get("videoPublishedAt", ""))
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token or len(video_ids) >= 300:  # Limit to 300 videos
                break
        
        return video_ids, video_dates

    async def _fetch_videos_details(self, session: aiohttp.ClientSession, 
                                  video_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch details for videos in chunks of 50"""
        all_videos = []
        
        for i in range(0, len(video_ids), self.max_results_per_page):
            chunk = video_ids[i:i + self.max_results_per_page]
            
            if not chunk:
                continue
                
            params = {
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(chunk),
                "key": self.yt_key
            }
            
            response = await self._fetch_with_retry(
                session,
                "https://www.googleapis.com/youtube/v3/videos",
                params
            )
            
            all_videos.extend(response.get("items", []))
            
            # Small delay to avoid rate limiting
            if i + self.max_results_per_page < len(video_ids):
                await asyncio.sleep(0.1)
        
        return all_videos

class BasicPlaylistExtractor(YouTubePlaylistExtractor):
    async def extract(self, playlist_url: str) -> Dict[str, Any]:
        """Basic playlist extraction"""
        playlist_id = self.extract_playlist_id(playlist_url)
        if not playlist_id:
            return {"status": "false", "error": "Invalid playlist URL", "data": []}
        
        async with aiohttp.ClientSession() as session:
            # Get playlist metadata
            playlist_response = await self._fetch_with_retry(
                session,
                "https://www.googleapis.com/youtube/v3/playlists",
                {
                    "part": "snippet,contentDetails",
                    "id": playlist_id,
                    "key": self.yt_key
                }
            )
            
            if not playlist_response.get("items"):
                return {"status": "false", "error": "Playlist not found", "data": []}
            
            playlist_item = playlist_response["items"][0]
            p_info = playlist_item["snippet"]
            p_stats = playlist_item["contentDetails"]
            
            playlist_meta = {
                "playlist_name": p_info["title"],
                "playlist_description": p_info.get("description", ""),
                "video_count": p_stats.get("itemCount", 0),
                "created_by": p_info.get("channelTitle", ""),
                "created_by_link": f"https://www.youtube.com/channel/{p_info.get('channelId', '')}",
                "created_on": p_info.get("publishedAt", ""),
                "last_updated": ""
            }
            
            # Fetch all video IDs
            video_ids, video_dates = await self._fetch_all_playlist_items(session, playlist_id)
            
            # Update last_updated if we have dates
            if video_dates:
                valid_dates = [d for d in video_dates if d]
                if valid_dates:
                    playlist_meta["last_updated"] = max(valid_dates)
            
            # Limit to 300 videos
            video_ids = video_ids[:300]
            
            # Fetch video details in chunks
            videos_data = await self._fetch_videos_details(session, video_ids)
            
            # Upload thumbnails in parallel (with limited concurrency)
            upload_tasks = []
            for video in videos_data:
                task = self._upload_thumbnail_to_cloudinary(session, video["id"])
                upload_tasks.append(task)
                
                # Limit concurrency to avoid rate limits
                if len(upload_tasks) >= 10:
                    await asyncio.gather(*upload_tasks, return_exceptions=True)
                    upload_tasks = []
                    await asyncio.sleep(0.5)
            
            # Process any remaining uploads
            if upload_tasks:
                await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            # Build result
            result_data = []
            for idx, video in enumerate(videos_data, 1):
                vid = video["id"]
                result_data.append({
                    "index": idx,
                    "video_id": vid,
                    "title": video["snippet"]["title"],
                    "duration": self.human_duration(video["contentDetails"]["duration"]),
                    "video_link": f"https://www.youtube.com/watch?v={vid}",
                    "original_thumbnail": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                    "thumbnail_247": f"https://res.cloudinary.com/{self.cloud_name}/image/upload/yt/{vid}.jpg"
                })
            
            return {
                "status": "true",
                "playlist_info": playlist_meta,
                "total_videos_fetched": len(result_data),
                "data": result_data
            }

class AdvancedPlaylistExtractor(YouTubePlaylistExtractor):
    async def extract(self, playlist_url: str) -> Dict[str, Any]:
        """Advanced playlist extraction with more details"""
        playlist_id = self.extract_playlist_id(playlist_url)
        if not playlist_id:
            return {"status": "false", "error": "Invalid playlist URL", "data": []}
        
        async with aiohttp.ClientSession() as session:
            # Get playlist metadata
            playlist_response = await self._fetch_with_retry(
                session,
                "https://www.googleapis.com/youtube/v3/playlists",
                {
                    "part": "snippet,contentDetails",
                    "id": playlist_id,
                    "key": self.yt_key
                }
            )
            
            if not playlist_response.get("items"):
                return {"status": "false", "error": "Playlist not found", "data": []}
            
            playlist_item = playlist_response["items"][0]
            p_info = playlist_item["snippet"]
            p_stats = playlist_item["contentDetails"]
            
            playlist_meta = {
                "playlist_name": p_info["title"],
                "playlist_description": p_info.get("description", ""),
                "video_count": p_stats.get("itemCount", 0),
                "created_by": p_info.get("channelTitle", ""),
                "created_by_link": f"https://www.youtube.com/channel/{p_info.get('channelId', '')}",
                "created_on": p_info.get("publishedAt", ""),
                "last_updated": ""
            }
            
            # Fetch all video IDs
            video_ids, video_dates = await self._fetch_all_playlist_items(session, playlist_id)
            
            # Update last_updated if we have dates
            if video_dates:
                valid_dates = [d for d in video_dates if d]
                if valid_dates:
                    playlist_meta["last_updated"] = max(valid_dates)
            
            # Limit to 300 videos
            video_ids = video_ids[:300]
            
            # Fetch video details in chunks
            videos_data = await self._fetch_videos_details(session, video_ids)
            
            # Upload thumbnails in parallel (with limited concurrency)
            upload_tasks = []
            for video in videos_data:
                task = self._upload_thumbnail_to_cloudinary(session, video["id"])
                upload_tasks.append(task)
                
                # Limit concurrency to avoid rate limits
                if len(upload_tasks) >= 10:
                    await asyncio.gather(*upload_tasks, return_exceptions=True)
                    upload_tasks = []
                    await asyncio.sleep(0.5)
            
            # Process any remaining uploads
            if upload_tasks:
                await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            # Build result
            result_data = []
            for idx, video in enumerate(videos_data, 1):
                vid = video["id"]
                channel_id = video["snippet"].get("channelId", "")
                channel_title = video["snippet"].get("channelTitle", "")
                
                result_data.append({
                    "index": idx,
                    "playlist_name": playlist_meta["playlist_name"],
                    "playlist_description": playlist_meta["playlist_description"],
                    "video_count": playlist_meta["video_count"],
                    "created_by": playlist_meta["created_by"],
                    "created_by_link": playlist_meta["created_by_link"],
                    "created_on": playlist_meta["created_on"],
                    "last_updated": playlist_meta["last_updated"],
                    "video": {
                        "video_id": vid,
                        "video_title": video["snippet"]["title"],
                        "video_duration": self.human_duration(video["contentDetails"]["duration"]),
                        "video_likes": video["statistics"].get("likeCount", "0"),
                        "views": video["statistics"].get("viewCount", "0"),
                        "description": video["snippet"].get("description", ""),
                        "number_of_comments": video["statistics"].get("commentCount", "0"),
                        "video_url": f"https://www.youtube.com/watch?v={vid}",
                        "video_thumbnail": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                        "channel_name": channel_title,
                        "channel_link": f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""
                    }
                })
            
            return {
                "status": "true",
                "playlist_info": playlist_meta,
                "total_videos_fetched": len(result_data),
                "data": result_data
            }

# Initialize extractors
basic_extractor = BasicPlaylistExtractor()
adv_extractor = AdvancedPlaylistExtractor()

@app.get("/")
async def root():
    return {
        "message": "YouTube Playlist Extractor API",
        "endpoints": {
            "/basic?url={playlist_url}": "Basic playlist extraction",
            "/adv?url={playlist_url}": "Advanced playlist extraction",
            "/info": "Demo information"
        },
        "limits": {
            "max_videos_per_request": 300,
            "youtube_api_page_limit": 50
        }
    }

@app.get("/basic")
async def basic(url: str):
    """Basic playlist extraction endpoint"""
    return await basic_extractor.extract(url)

@app.get("/adv")
async def adv(url: str):
    """Advanced playlist extraction endpoint"""
    return await adv_extractor.extract(url)

@app.get("/info")
async def info():
    """Get demo URL and API status"""
    return {
        "demo_url": f"http://127.0.0.1:8000/basic?url=https://www.youtube.com/playlist?list={basic_extractor.demo_playlist_id}",
        "advanced_demo_url": f"http://127.0.0.1:8000/adv?url=https://www.youtube.com/playlist?list={adv_extractor.demo_playlist_id}",
        "status": "alive",
        "limits": {
            "max_videos": 300,
            "api_page_size": 50
        }
    }

