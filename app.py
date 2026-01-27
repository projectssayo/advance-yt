from fastapi import FastAPI, HTTPException
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time

app = FastAPI(
    title="YouTube Playlist Scraper API",
    description="API to scrape YouTube playlist data",
    version="1.0"
)

def get_x(url):
    """Scrape YouTube playlist data"""
    try:
        with sync_playwright() as p:
            # Use headless=True for deployment
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            # Go to URL with timeout
            page.goto(url, timeout=30000)
            
            # Wait for content to load
            page.wait_for_selector("ytd-playlist-video-renderer", state="visible", timeout=30000)
            time.sleep(2)  # Additional wait
            
            all_data = []
            main_length = page.evaluate("""
                document.getElementsByTagName('ytd-playlist-video-renderer').length
            """)
            print(f"Number of videos in playlist: {main_length}")

            for i in range(main_length):
                # Scroll to element
                page.evaluate(f"""
                    window.scrollTo({{
                        top: document.getElementsByTagName("ytd-playlist-video-renderer")[{i}].offsetTop - 300,
                        behavior: 'smooth'
                    }})
                """)
                time.sleep(0.1)  # Small delay

                data = page.evaluate(f"""
                    (() => {{
                        const el = document.getElementsByTagName("ytd-playlist-video-renderer")[{i}];
                        if (!el) return null;

                        // Try multiple selectors for duration
                        let duration = "";
                        const durationSelectors = [
                            'badge-shape',
                            'ytd-thumbnail-overlay-time-status-renderer',
                            'span#text'
                        ];
                        
                        for (const selector of durationSelectors) {{
                            const elem = el.querySelector(selector);
                            if (elem && elem.innerText) {{
                                duration = elem.innerText.trim();
                                break;
                            }}
                        }}

                        const img = el.querySelector('yt-image img, yt-img-shadow img');
                        const index = el.querySelector('yt-formatted-string, span.index');
                        const titleEl = el.querySelector('h3, a#video-title');
                        const linkEl = titleEl ? titleEl.closest('a') : null;

                        return {{
                            index: index?.innerText?.trim() || "",
                            title: titleEl?.innerText?.trim() || "",
                            duration: duration,
                            link: linkEl?.href || "",
                            img: img?.src || img?.getAttribute('src') || "",
                            position: {i + 1}
                        }};
                    }})()
                """)

                if data and data.get('title'):  # Only add if we have a title
                    all_data.append(data)

            # Close browser
            context.close()
            browser.close()
            
            return {
                "success": True,
                "data": all_data,
                "total_videos": len(all_data),
                "url": url
            }
            
    except PlaywrightTimeoutError:
        return {
            "success": False,
            "error": "Timeout loading page. YouTube might be blocking the request.",
            "url": url
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url
        }

@app.get("/")
def home():
    return {
        "message": "YouTube Playlist Scraper API",
        "endpoints": {
            "GET /": "This info",
            "GET /health": "Health check",
            "GET /info": "Usage instructions",
            "GET /scrape?url=YOUTUBE_URL": "Scrape playlist"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "python_version": "3.11.0"
    }

@app.get("/info")
def info():
    """Usage instructions"""
    return {
        "ask": "GET /scrape?url=YOUR_YOUTUBE_PLAYLIST_URL",
        "example": "/scrape?url=https://www.youtube.com/playlist?list=PLGjplNEQ1it_oTvuLRNqXfz_v_0pq6unW",
        "note": "Replace with your actual deployed URL when hosting"
    }

@app.get("/scrape")
def scrape(url: str):
    """Scrape YouTube playlist"""
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    
    if "youtube.com/playlist" not in url:
        raise HTTPException(status_code=400, detail="URL must be a YouTube playlist")
    
    result = get_x(url)
    
    if not result.get("success", False):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Unknown error occurred")
        )
    
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
