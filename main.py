import base64
import json
import os
import time
import requests
import re
import sys
from html import unescape

# Ensure stdout and stderr handle utf-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import src.utils.compat

# Import database module
import src.database as database
database.init_db()

# Import scraper modules
from src.core.comment_scraper import fetch_comments, fetch_replies, fb_json, GRAPHQL, PROXIES
from src.core.page_scraper import fetch_posts as fetch_page_posts, extract_media as extract_page_media, parse_fb_response as parse_page_response
from src.core.group_scraper import fetch_posts as fetch_group_posts
from src.core.media_scraper import fetch_all_images
from src.core.proxy_utils import select_proxy


def extract_user_id_from_url(url, cookies=None):
    """Extract Facebook User ID from a profile URL"""
    # First, try to extract ID directly from URL
    url_patterns = [
        r'profile\.php\?id=(\d+)',
        r'/profile/(\d+)',
        r'id=(\d+)'
    ]
    
    for pattern in url_patterns:
        match = re.search(pattern, url)
        if match:
            user_id = match.group(1)
            print(f"  ✅ Found User ID in URL: {user_id}")
            return user_id
    
    # If no ID in URL, fetch the page and search in HTML
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        print(f"  No ID in URL, fetching page: {url}")
        response = requests.get(url, headers=headers, cookies=cookies, proxies=PROXIES, timeout=20)
        html = response.text
        
        # Try multiple patterns to find user ID in HTML
        patterns = [
            r'fb://profile/(\d+)',           # BEST signal
            r'"profile_owner":"(\d+)"',
            r'"userID":"(\d+)"',
            r'owner_id=(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                user_id = match.group(1)
                print(f"  ✅ Found User ID: {user_id}")
                return user_id
        
        print("  ❌ User ID not found (profile may be private or login wall)")
        return None
    
    except Exception as e:
        print(f"  ❌ Error fetching URL: {e}")
        return None


def extract_clean_group_url(url: str) -> str:
    """
    Trích xuất URL gốc của group từ URL group hoặc URL bài viết trong group.
    Ví dụ:
    - https://www.facebook.com/groups/123456/posts/789 -> https://www.facebook.com/groups/123456/
    - https://www.facebook.com/groups/mygroup/permalink/789 -> https://www.facebook.com/groups/mygroup/
    """
    if not url:
        return ""
    url = url.strip()
    match = re.search(r'(https?://(?:www\.|m\.|web\.)?facebook\.com/groups/[^/?#]+)', url)
    if match:
        return match.group(1).rstrip('/') + '/'
    match_slug = re.search(r'/groups/([^/?#]+)', url)
    if match_slug:
        return f"https://www.facebook.com/groups/{match_slug.group(1)}/"
    return url


def extract_group_id_from_url(url, cookies=None):
    """Extract Facebook Group ID from a group URL or a group post URL (supports numeric ID and vanity/slug names)"""
    from src.utils.helpers import resolve_group_details
    details = resolve_group_details(url, cookies=cookies)
    gid = details.get("group_id")
    if gid:
        print(f"  ✅ Resolved Group ID: {gid}")
        return gid
    print("  ❌ Group ID not found (group may be private or login wall)")
    return None


def extract_post_id_from_url(url, cookies=None):
    """Extract Facebook Post ID from a post URL"""
    
    # First, try to extract post ID directly from URL patterns (no fetch needed)
    url_patterns = [
        r'/groups/[^/]+/posts/(\d+)',           # /groups/MemeAddiction/posts/4471339869798423
        r'/posts/(\d+)',                         # /posts/123456
    ]
    
    for pattern in url_patterns:
        match = re.search(pattern, url)
        if match:
            post_id = match.group(1)
            print(f"  ✅ Found Post ID in URL: {post_id}")
            return post_id
    
    # If no direct pattern match, fetch the page and extract from HTML
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        print(f"  No direct ID in URL, fetching post: {url}")
        response = requests.get(url, headers=headers, cookies=cookies, proxies=PROXIES, timeout=20)
        html = response.text
        
        post_id = None
        
        # Method 1: Try storyID (works with authenticated requests)
        if cookies:
            story_id_match = re.search(r'"storyID":"([^"]+)"', html)
            if story_id_match:
                story_id_encoded = story_id_match.group(1)
                try:
                    # Decode base64 storyID
                    story_id_decoded = base64.b64decode(story_id_encoded).decode('utf-8')
                    print(f"  📝 Decoded storyID: {story_id_decoded}")
                    
                    # Extract post ID (last segment after splitting by ':')
                    # Format: S:_USER_ID:POST_ID:POST_ID or similar
                    parts = story_id_decoded.split(':')
                    if len(parts) >= 2:
                        post_id = parts[-1]  # Last part is the post ID
                        print(f"  ✅ Found Post ID from storyID: {post_id}")
                        return post_id
                except Exception as e:
                    print(f"  ⚠️ Could not decode storyID: {e}")
        
        # Method 2: Extract og:url meta tag (fallback for unauthenticated or if storyID fails)
        og_url_match = re.search(
            r'<meta property="og:url" content="([^"]+)"',
            html
        )
        
        if og_url_match:
            og_url = unescape(og_url_match.group(1))
            
            # Case 1: /posts/POST_ID/ (group posts) or /posts/.../POST_ID/ (user posts)
            m = re.search(r'/posts/(?:[^/]+/)?(\d+)', og_url)
            
            # Case 2: permalink.php?story_fbid=POST_ID
            if not m:
                m = re.search(r'story_fbid=(\d+)', og_url)
            
            if m:
                post_id = m.group(1)
        
        if post_id:
            print(f"  ✅ Found Post ID from og:url: {post_id}")
            return post_id
        
        print("  ❌ Post ID not found in URL")
        return None
    
    except Exception as e:
        print(f"  ❌ Error fetching URL: {e}")
        return None


def convert_post_id_to_feedback_id(post_id):
    """Convert post_id to feedback_id using base64 encoding"""
    feedback_id = base64.b64encode(f"feedback:{post_id}".encode()).decode()
    return feedback_id


def fetch_comments_for_post(post_id, cookies=None):
    """Fetch all comments and replies for a given post_id"""
    feedback_id = convert_post_id_to_feedback_id(post_id)
    print(f"  Fetching comments for post {post_id}...")
    print(f"  Using feedback_id: {feedback_id}")
    
    all_data = []
    comments, post_info = fetch_comments(feedback_id, cookies=cookies)
    
    for c in comments:
        print(f"    🗨️ {c.get('text', '')[:50]}...")
        c["replies"] = fetch_replies(c, cookies=cookies)
        
        for r in c["replies"]:
            print(f"       ↳ {r.get('text', '')[:50]}...")
        
        # Remove internal fields before appending
        c_clean = {k: v for k, v in c.items() if not k.startswith('_')}
        all_data.append(c_clean)
    
    print(f"  ✓ Found {len(all_data)} comments")
    return all_data, post_info


def save_post_data(post_type, post_id, post_data, comments_data):
    """Save post and comments data directly to SQLite database (no disk files)"""
    if not post_id:
        return None
    try:
        db_stats = database.save_or_update_post(post_type, post_id, post_data, comments_data)
        if db_stats and db_stats.get("post_created"):
            print(f"  🗄️ SQLite: Inserted new post {post_id} (+{db_stats['comments_added']} comments, +{db_stats['replies_added']} replies, +{db_stats['media_added']} media)")
        elif db_stats:
            print(f"  🗄️ SQLite: Updated post {post_id} (+{db_stats['comments_added']} new comments, +{db_stats['replies_added']} new replies)")
        return db_stats
    except Exception as e:
        print(f"  ⚠️ SQLite save error: {e}")
        return None


def display_menu():
    """Display the main menu"""
    print("\n" + "="*60)
    print("   📘 FACEBOOK SCRAPER")
    print("="*60)
    print("\nChoose what to scrape:")
    print("  1. Simple Post (just comments from a single post)")
    print("  2. Page Posts (posts + comments from a page)")
    print("  3. Group Posts (posts + comments from a group)")
    print("  4. Exit")
    print("="*60)


def scrape_simple_post():
    """Scrape comments from a single post"""
    print("\n--- SIMPLE POST SCRAPER ---")
    print("\nChoose input method:")
    print("  1. Enter Post URL (auto-extract ID)")
    print("  2. Enter Post ID directly")
    
    input_choice = input("Your choice (1 or 2): ").strip()
    
    post_id = None
    
    if input_choice == "1":
        post_url = input("Enter Post URL: ").strip()
        if not post_url:
            print("❌ Invalid URL")
            return
        
        # Extract post ID from URL
        post_id = extract_post_id_from_url(post_url)
        if not post_id:
            print("❌ Could not extract Post ID from URL")
            return
    
    elif input_choice == "2":
        post_id = input("Enter Post ID: ").strip()
        if not post_id:
            print("❌ Invalid post ID")
            return
    
    else:
        print("❌ Invalid choice")
        return
    
    print(f"\nFetching comments for post {post_id}...")
    comments, post_info = fetch_comments_for_post(post_id)
    
    # Save data
    post_data = {
        "post_id": post_id,
        "type": "simple_post",
        "post_info": post_info
    }
    
    save_post_data("simple_post", post_id, post_data, comments)
    
    # Fetch images metadata if media_id is available
    if post_info and post_info.get("media_id"):
        media_id = post_info["media_id"]
        print(f"\n📸 Processing images for media_id: {media_id}")
    else:
        print("  ℹ️ No media_id found, skipping image processing")
    
    print(f"\n✅ Done! Saved to SQLite database.")


def scrape_page_posts():
    """Scrape posts and comments from a page"""
    print("\n--- PAGE POST SCRAPER ---")
    print("\nChoose input method:")
    print("  1. Enter Page URL (auto-extract ID)")
    print("  2. Enter Page/User ID directly")
    
    input_choice = input("Your choice (1 or 2): ").strip()
    
    page_id = None
    
    if input_choice == "1":
        page_url = input("Enter Page URL: ").strip()
        if not page_url:
            print("❌ Invalid URL")
            return
        
        # Extract user ID from URL
        page_id = extract_user_id_from_url(page_url)
        if not page_id:
            print("❌ Could not extract User ID from URL")
            return
    
    elif input_choice == "2":
        page_id = input("Enter Page/User ID: ").strip()
        if not page_id:
            print("❌ Invalid page ID")
            return
    
    else:
        print("❌ Invalid choice")
        return
    
    try:
        count = int(input("How many posts to fetch? ").strip())
    except ValueError:
        print("❌ Invalid number")
        return
    
    # Update the USER_ID in post_scraper
    import post_scraper
    post_scraper.USER_ID = page_id
    post_scraper.BASE_HEADERS["referer"] = f"https://www.facebook.com/profile.php?id={page_id}"
    
    print(f"\nFetching {count} posts from page {page_id}...")
    posts = fetch_page_posts(count)
    
    print(f"\n✓ Found {len(posts)} posts. Now fetching comments...")
    
    # Fetch comments for each post
    for i, post in enumerate(posts, 1):
        post_id = post.get("post_id")
        if not post_id:
            print(f"\n[{i}/{len(posts)}] ⚠️ Skipping post with no ID")
            continue
        
        print(f"\n[{i}/{len(posts)}] Processing post {post_id}...")
        
        try:
            comments, _ = fetch_comments_for_post(post_id)
            save_post_data("page_post", post_id, post, comments)
            time.sleep(1)  # Be nice to the server
        except Exception as e:
            print(f"  ❌ Error fetching comments: {e}")
            # Save post data even if comments fail
            save_post_data("page_post", post_id, post, [])
    
    print(f"\n✅ Done! Saved {len(posts)} posts to page_post/")


def scrape_group_posts():
    """Scrape posts and comments from a group"""
    print("\n--- GROUP POST SCRAPER ---")
    print("\nChoose input method:")
    print("  1. Enter Group URL (auto-extract ID)")
    print("  2. Enter Group ID directly")
    
    input_choice = input("Your choice (1 or 2): ").strip()
    
    group_id = None
    
    if input_choice == "1":
        group_url = input("Enter Group URL: ").strip()
        if not group_url:
            print("❌ Invalid URL")
            return
        
        # Extract group ID from URL
        group_id = extract_group_id_from_url(group_url)
        if not group_id:
            print("❌ Could not extract Group ID from URL")
            return
    
    elif input_choice == "2":
        group_id = input("Enter Group ID: ").strip()
        if not group_id:
            print("❌ Invalid group ID")
            return
    
    else:
        print("❌ Invalid choice")
        return
    
    try:
        count = int(input("How many posts to fetch? ").strip())
    except ValueError:
        print("❌ Invalid number")
        return
    
    # Update the GROUP_ID in group_post_scraper_v2
    import group_post_scraper_v2
    group_post_scraper_v2.GROUP_ID = group_id
    group_post_scraper_v2.HEADERS["referer"] = f"https://www.facebook.com/groups/{group_id}/"
    
    print(f"\nFetching {count} posts from group {group_id}...")
    posts = fetch_group_posts(count)
    
    print(f"\n✓ Found {len(posts)} posts. Now fetching comments...")
    
    # Fetch comments for each post
    for i, post in enumerate(posts, 1):
        post_id = post.get("post_id")
        if not post_id:
            print(f"\n[{i}/{len(posts)}] ⚠️ Skipping post with no ID")
            continue
        
        print(f"\n[{i}/{len(posts)}] Processing post {post_id}...")
        
        try:
            comments, _ = fetch_comments_for_post(post_id)
            save_post_data("group_post", post_id, post, comments)
            time.sleep(1)  # Be nice to the server
        except Exception as e:
            print(f"  ❌ Error fetching comments: {e}")
            # Save post data even if comments fail
            save_post_data("group_post", post_id, post, [])
    
    print(f"\n✅ Done! Saved {len(posts)} posts to group_post/")


def main():
    """Main function - GUI-like menu"""
    while True:
        display_menu()
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            scrape_simple_post()
        elif choice == "2":
            scrape_page_posts()
        elif choice == "3":
            scrape_group_posts()
        elif choice == "4":
            print("\n👋 Goodbye!")
            break
        else:
            print("\n❌ Invalid choice. Please enter 1, 2, 3, or 4.")
        
        # Ask if user wants to continue
        if choice in ["1", "2", "3"]:
            continue_choice = input("\nPress Enter to return to menu (or 'q' to quit): ").strip().lower()
            if continue_choice == 'q':
                print("\n👋 Goodbye!")
                break


if __name__ == "__main__":
    main()
1