import requests

class Updater:
    """
    版本检查与下载逻辑。
    """
    def __init__(self, version_url: str, update_url: str):
        self.version_url = version_url
        self.update_url = update_url

    def get_remote_version(self) -> str:
        resp = requests.get(self.version_url, timeout=5)
        resp.raise_for_status()
        return resp.text.strip()

    @staticmethod
    def is_new_version(local_version: str, remote_version: str) -> bool:
        def parse(v): return tuple(int(x) for x in v.split('.'))
        try:
            return parse(remote_version) > parse(local_version)
        except Exception:
            # 容错：非严格语义时，内容不同也算新版本
            return local_version != remote_version

    @staticmethod
    def build_release_asset_url(owner: str, repo: str, version: str, asset_name: str, tag_prefix: str = "v") -> str:
        """
        构建 GitHub Releases 资产直链（公开仓库可匿名下载）。
        version: "1.1.0" 或 "v1.1.0"；会按前缀规范化。
        """
        tag = version if (tag_prefix == "" or version.startswith(tag_prefix)) else f"{tag_prefix}{version}"
        return f"https://github.com/{owner}/{repo}/releases/download/{tag}/{asset_name}"



    def download(self, save_path: str, chunk=8192, progress_cb=None, cancel_flag=None):
        """
        下载更新到 save_path。
        - progress_cb(0-100)
        - cancel_flag(): bool -> True 则中断
        返回 (success: bool, error_msg: str)
        """
        if not self.update_url:
            return False, "未配置下载地址"
        with requests.get(self.update_url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            with open(save_path, 'wb') as f:
                for part in resp.iter_content(chunk_size=chunk):
                    if cancel_flag and cancel_flag():
                        return False, "用户取消"
                    if not part:
                        continue
                    f.write(part)
                    downloaded += len(part)
                    if total and progress_cb:
                        progress_cb(int(downloaded * 100 / total))
        if progress_cb:
            progress_cb(100)
        return True, ""