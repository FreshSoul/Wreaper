import requests
import os

BING_API_KEY = 'YOUR_BING_API_KEY'  # 替换为你的Bing API Key
SEARCH_URL = "https://api.bing.microsoft.com/v7.0/search"
DOWNLOAD_DIR = "downloaded_audios"

def search_audio_files(query, count=10):
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    params = {
        "q": query + " filetype:mp3 OR filetype:wav OR filetype:flac",
        "count": count
    }
    response = requests.get(SEARCH_URL, headers=headers, params=params)
    response.raise_for_status()
    results = response.json()
    audio_links = []
    for v in results.get("webPages", {}).get("value", []):
        url = v.get("url", "")
        if url.endswith(('.mp3', '.wav', '.flac')):
            audio_links.append(url)
    return audio_links

def download_audio(url, save_dir=DOWNLOAD_DIR):
    os.makedirs(save_dir, exist_ok=True)
    local_filename = os.path.join(save_dir, url.split("/")[-1].split("?")[0])
    try:
        with requests.get(url, stream=True, timeout=10) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"已下载: {local_filename}")
    except Exception as e:
        print(f"下载失败: {url}，原因: {e}")

if __name__ == "__main__":
    keyword = input("请输入你想要搜索的音频关键词：")
    links = search_audio_files(keyword)
    print("找到的音频链接：")
    for link in links:
        print(link)
    for link in links:
        download_audio(link)