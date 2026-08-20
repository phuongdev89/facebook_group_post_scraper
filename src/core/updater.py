import re
import os
import requests
from src.config.constants import APP_VERSION

DEFAULT_GITHUB_REPO = "phuongdev89/facebook_post_comment_scraper"


def parse_version(version_str: str) -> tuple:
    """
    Chuyển đổi chuỗi phiên bản dạng 'v1.0.2', '1.0.3', '1.2.0-beta' thành tuple các số nguyên để so sánh.
    Ví dụ: 'v1.2.3' -> (1, 2, 3)
    """
    if not version_str:
        return (0, 0, 0)
    cleaned = version_str.strip().lstrip("vV")
    numbers = re.findall(r'\d+', cleaned)
    if not numbers:
        return (0, 0, 0)
    return tuple(int(n) for n in numbers[:3])


def is_newer_version(latest_version: str, current_version: str) -> bool:
    """
    Kiểm tra xem latest_version có mới hơn current_version hay không.
    """
    latest_tuple = parse_version(latest_version)
    current_tuple = parse_version(current_version)
    return latest_tuple > current_tuple


def check_github_update(
    current_version: str = None,
    repo: str = DEFAULT_GITHUB_REPO,
    timeout: int = 10
) -> tuple[bool, dict, str]:
    """
    Kiểm tra phiên bản mới nhất từ GitHub Releases API hoặc fallback qua file version.json trên nhánh main.
    Không cần máy chủ riêng!
    Trả về: (has_update: bool, update_info: dict, message: str)
    """
    cur_ver = current_version or APP_VERSION
    clean_repo = repo.strip().strip("/")
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "FacebookNotification-App"
    }

    update_info = {
        "latest_version": cur_ver,
        "current_version": cur_ver,
        "release_name": "",
        "changelog": "",
        "download_url": "",
        "release_url": f"https://github.com/{clean_repo}/releases",
        "published_at": "",
        "source": ""
    }

    # 1. Thử gọi GitHub Releases API
    api_url = f"https://api.github.com/repos/{clean_repo}/releases/latest"
    try:
        resp = requests.get(api_url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            raw_tag = data.get("tag_name", "")
            latest_ver = raw_tag.lstrip("vV").strip() or cur_ver
            release_name = data.get("name") or f"Phiên bản v{latest_ver}"
            body_changelog = data.get("body") or "Không có ghi chú phát hành."
            release_url = data.get("html_url") or f"https://github.com/{clean_repo}/releases/latest"
            published_at = data.get("published_at", "")[:10]

            # Tìm file asset tải về (ưu tiên .zip patch hoặc portable hoặc .exe installer)
            assets = data.get("assets", [])
            download_url = ""
            for asset in assets:
                asset_name = asset.get("name", "").lower()
                if "patch" in asset_name and asset_name.endswith(".zip"):
                    download_url = asset.get("browser_download_url", "")
                    break
            if not download_url:
                for asset in assets:
                    asset_name = asset.get("name", "").lower()
                    if asset_name.endswith(".zip") or asset_name.endswith(".exe"):
                        download_url = asset.get("browser_download_url", "")
                        break
            if not download_url:
                download_url = data.get("zipball_url") or release_url

            has_update = is_newer_version(latest_ver, cur_ver)
            update_info.update({
                "latest_version": latest_ver,
                "release_name": release_name,
                "changelog": body_changelog,
                "download_url": download_url,
                "release_url": release_url,
                "published_at": published_at,
                "source": "github_release"
            })

            if has_update:
                msg = f"Đã có phiên bản mới v{latest_ver} (Hiện tại: v{cur_ver})"
            else:
                msg = f"Bạn đang sử dụng phiên bản mới nhất (v{cur_ver})"
            return has_update, update_info, msg

    except Exception:
        pass

    # 2. Fallback qua raw version.json trên nhánh main
    raw_json_url = f"https://raw.githubusercontent.com/{clean_repo}/main/version.json"
    try:
        resp = requests.get(raw_json_url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            latest_ver = str(data.get("version", "")).lstrip("vV").strip() or cur_ver
            changelog = data.get("changelog") or data.get("release_notes") or "Không có ghi chú."
            download_url = data.get("download_url") or f"https://github.com/{clean_repo}/releases/latest"
            release_url = data.get("release_url") or f"https://github.com/{clean_repo}/releases"
            published_at = data.get("published_at") or data.get("release_date") or ""

            has_update = is_newer_version(latest_ver, cur_ver)
            update_info.update({
                "latest_version": latest_ver,
                "release_name": f"Phiên bản v{latest_ver}",
                "changelog": changelog,
                "download_url": download_url,
                "release_url": release_url,
                "published_at": published_at,
                "source": "version_json"
            })

            if has_update:
                msg = f"Đã có phiên bản mới v{latest_ver} (Hiện tại: v{cur_ver})"
            else:
                msg = f"Bạn đang sử dụng phiên bản mới nhất (v{cur_ver})"
            return has_update, update_info, msg

    except Exception as e:
        return False, update_info, f"Lỗi kiểm tra cập nhật: {str(e)}"

    return False, update_info, f"Không thể kiểm tra bản cập nhật từ GitHub ({clean_repo})"


def download_update_file(
    download_url: str,
    dest_path: str,
    progress_callback=None,
    timeout: int = 60
) -> tuple[bool, str]:
    """
    Tải file cập nhật (zip/exe) với luồng stream và báo tiến trình qua progress_callback(percent: int).
    Trả về: (thành_công: bool, thông_điệp_hoặc_đường_dẫn: str)
    """
    if not download_url:
        return False, "Đường dẫn tải file cập nhật trống"

    try:
        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        resp = requests.get(download_url, stream=True, timeout=timeout)
        if resp.status_code != 200:
            return False, f"Lỗi tải file: HTTP {resp.status_code}"

        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and progress_callback:
                    percent = int((downloaded / total_size) * 100)
                    progress_callback(percent)

        if progress_callback:
            progress_callback(100)

        return True, dest_path

    except Exception as e:
        return False, f"Lỗi trong quá trình tải cập nhật: {str(e)}"
