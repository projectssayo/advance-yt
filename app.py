from fastapi import FastAPI, Query
from playwright.sync_api import sync_playwright

app = FastAPI(title="YouTube Playlist Scraper")

def scrape_video(browser, link):
    page = browser.new_page()
    page.goto(link)
    page.wait_for_timeout(1000)

    data = page.evaluate("""
    (() => {
        const likes =
            document.getElementsByTagName("like-button-view-model")[1]?.innerText || "";
        const channel_name =
            document.getElementsByTagName("ytd-channel-name")[0]?.innerText || "";
        const channel_link =
            document.getElementsByTagName("ytd-channel-name")[0]
                ?.getElementsByTagName("a")[0]?.href || "";
        const channel_subs =
            document.getElementsByTagName("ytd-channel-name")[0]
                ?.nextSibling?.innerText || "";

        const btn = document.getElementsByTagName("tp-yt-paper-button")[0];
        if (btn) btn.click();

        const description =
            document.getElementsByTagName("ytd-text-inline-expander")[0]
                ?.querySelector("yt-attributed-string")?.innerText || "";

        window.scrollTo(0, document.documentElement.scrollHeight);

        const comments =
            document.getElementsByTagName("ytd-comments-header-renderer")[0]
                ?.getElementsByTagName("h2")[0]?.innerText || "";

        return {
            likes,
            channel_name,
            channel_link,
            channel_subs,
            description,
            comments
        };
    })()
    """)

    page.close()
    return data

def scrape_playlist(browser, url):
    page = browser.new_page()
    page.goto(url)
    page.wait_for_selector("ytd-playlist-video-renderer")

    playlist_data = []
    main_length = page.evaluate("""
        document.getElementsByTagName('ytd-playlist-video-renderer').length
    """)

    for i in range(main_length):
        data = page.evaluate(f"""
        (() => {{
            const el = document.getElementsByTagName("ytd-playlist-video-renderer")[{i}];
            if (!el) return null;
            const duration = el.getElementsByTagName("badge-shape")[0];
            const img = el.querySelector("yt-image img");
            const titleEl = el.getElementsByTagName("h3")[0];
            const linkEl = titleEl?.getElementsByTagName("a")[0];
            const indexEl = el.getElementsByTagName("yt-formatted-string")[0];

            return {{
                index: indexEl?.innerText || "",
                title: titleEl?.innerText || "",
                duration: duration?.innerText || "",
                link: linkEl?.href || "",
                img: img?.src || ""
            }};
        }})()
        """)
        if data and data["link"]:
            video_info = scrape_video(browser, data["link"])
            data.update(video_info)
            playlist_data.append(data)

    page.close()
    return playlist_data

@app.get("/scrape/")
def scrape(url: str = Query(..., description="YouTube playlist URL")):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            result = scrape_playlist(browser, url)
        finally:
            browser.close()
    return {"playlist_data": result}



if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
