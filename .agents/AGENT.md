# AGENT.md — Quy tắc dự án Facebook Post & Comment Scraper

## Bối cảnh & Tech Spec Dự án

- **Mục tiêu:** Cào bài viết, comment, reply, ảnh từ Facebook (page, group, single post) qua GraphQL API không chính thức, xuất JSON.
- **Repo GitLab:** `git@gitlab.com:phuongdev89/facebook_group_post_scraper.git`. **Nhánh chính: `main`**
- **Nhánh làm việc theo quy ước:** `feature/issue-<id>` tạo từ nhánh `main`.
- **Tech Stack:**
  - **Language:** Python 3.8+
  - **HTTP:** `requests` thuần — **không dùng Playwright, Selenium, hay browser automation**.
  - **API:** Facebook GraphQL (`https://www.facebook.com/api/graphql/`) với `doc_id` trích từ browser.
  - **GUI:** PyQt6 desktop (`facebook_ui.py`).
  - **Config:** `.env` file (`PROXY=...`). Session token/cookie paste thủ công vào UI hoặc hardcode tạm trong script.
  - **Output:** JSON files trong thư mục `simple_post/`, `page_post/`, `group_post/`.
  - **Deduplication:** Kiểm tra file JSON đã tồn tại trong thư mục output (không dùng SQLite).
  - **Rate limiting:** Delay thủ công giữa request, retry 3 lần với backoff 2s.

## Cấu trúc file

```
main.py                   # Utilities chung (extract ID, fetch comment, save)
facebook_ui.py            # PyQt6 GUI — entry point chính
post_scraper.py           # Cào bài viết từ Page/Profile
group_post_scraper_v2.py  # Cào bài viết từ Group
comment_scraper.py        # Cào comment + reply
single_post_image.py      # Cào ảnh từ single post
proxy_utils.py            # Proxy helper
requirements.txt          # requests, PyQt6, python-dotenv, seleniumbase
```

## Điều phối (mặc định tự làm)

- **Mặc định:** Tự làm toàn bộ. KHÔNG tự ý gọi subagent.
- **Chỉ gọi team** khi người dùng yêu cầu rõ: "gọi team", "phân việc subagent", "chạy full workflow".
- **Chỉ chạy quy trình GitHub đầy đủ** (Issue → branch → PR) khi người dùng yêu cầu rõ.

## Thông tin cấu hình & kiểm thử

- **`.env`:** Chỉ có `PROXY=...` (tùy chọn). Không có token/cookie trong env.
- **Session token/cookie:** Người dùng paste thủ công vào UI hoặc hardcode vào script để test.
- **`doc_id`:** Thay đổi thường xuyên theo version FB. Cần cập nhật từ browser DevTools khi bị lỗi "failed after 5 attempts".
- **Chạy GUI:** `python facebook_ui.py`
- **Chạy CLI:** import trực tiếp từ `main.py`.

## Cấm tuyệt đối

- **KHÔNG push trực tiếp lên `main`.** Mọi thay đổi qua nhánh riêng + PR.
- **KHÔNG tự merge PR.**
- **KHÔNG commit file nhạy cảm:** cookie, session token, file `.env` có secret thật, output JSON dữ liệu người dùng.
- **KHÔNG thêm browser automation** (Playwright, Selenium) — dự án chủ đích dùng pure requests.

## Bằng chứng trước khi báo hoàn thành

Không báo PASS nếu chưa chạy thật:

- **Scraper module:** Log JSON output thực tế (post_id, content, timestamp).
- **Comment module:** Log comment/reply parse được từ GraphQL response.
- **Image module:** URL ảnh thực tế trích xuất được.
- **Deduplication:** Chứng minh skip khi file JSON đã tồn tại.

Nếu thiếu credentials/session để chạy — nói rõ "chưa verify", không suy đoán.

## Dọn dẹp trước khi commit

Xóa file test/log/JSON tạm. Chạy `git status` trước khi push.

## Giao tiếp

- Trả lời tiếng Việt, cực ngắn gọn, dạng gạch đầu dòng.
- Không chào hỏi, không xã giao.
- Khi tạo PR → gửi kèm URL.
