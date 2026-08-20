import requests
import json
import time
import os
import sys
import uuid
# Ensure stdout and stderr handle utf-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Import database module
import src.database as database
database.init_db()

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"

# ========= CONFIG (FILL THESE) =========
GROUP_ID = "363757814515154"  # group id
GROUP_NAME = None  # Will be extracted automatically
DOC_ID = "25716860671307636"  # GroupsCometFeedRegularStoriesPaginationQuery

HEADERS = {
    "user-agent": "Mozilla/5.0",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.facebook.com",
    "referer": f"https://www.facebook.com/groups/{GROUP_ID}/",
}

# Get proxy configuration
PROXY = os.getenv('PROXY')
PROXIES = {'http': PROXY, 'https': PROXY} if PROXY else None

# Cookies (set by UI when provided)
COOKIES = {}

# FB_DTSG token (set by UI when provided)
FB_DTSG = ""

if PROXY:
    print(f"Using proxy: {PROXY}")


def extract_group_name(node):
    """Extract group name from post node"""
    if not node or not isinstance(node, dict):
        return None
    try:
        # Try from context_layout > story > comet_sections > title > story > to
        context_layout = node.get('comet_sections', {}).get('context_layout', {})
        story = context_layout.get('story', {})
        title_section = story.get('comet_sections', {}).get('title', {})
        title_story = title_section.get('story', {})
        to_obj = title_story.get('to', {})
        if isinstance(to_obj, dict) and to_obj.get('__typename') == 'Group' and to_obj.get('name'):
            return str(to_obj.get('name')).strip()

        # Try from content > story > target_group (if available)
        content = node.get('comet_sections', {}).get('content', {})
        content_story = content.get('story', {})
        target_group = content_story.get('target_group', {})
        if isinstance(target_group, dict) and target_group.get('name'):
            return str(target_group.get('name')).strip()

        # Try from feedback > associated_group
        feedback = node.get('feedback', {})
        associated_group = feedback.get('associated_group', {})
        if isinstance(associated_group, dict) and associated_group.get('name'):
            return str(associated_group.get('name')).strip()

        return None
    except Exception:
        return None


def extract_creation_time(node):
    """Extract post creation time (Unix timestamp) from node"""
    try:
        # node.comet_sections.timestamp.story.creation_time
        t = node.get('comet_sections', {}).get('timestamp', {}).get('story', {}).get('creation_time')
        if t:
            return t

        return None
    except Exception:
        return None

# ========= RETRY HELPER =========
def retry_request(url, headers, data, proxies, max_retries=5):
    """Make a POST request with retry logic"""
    global PROXIES
    from src.core.proxy_utils import rotate_static_proxy, is_proxy_infra_error, is_ip_blocked

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, headers=headers, data=data, proxies=proxies, cookies=COOKIES, timeout=30)
            if r.status_code == 200:
                return r
            if is_proxy_infra_error(status_code=r.status_code):
                print(f"  🚫 Attempt {attempt}/{max_retries}: Proxy auth failed (HTTP {r.status_code}) — rotating static proxy...")
                new_p = rotate_static_proxy()
                if new_p:
                    proxies = new_p
                    PROXIES = new_p
            elif is_ip_blocked(status_code=r.status_code, response_text=r.text):
                print(f"  🛽 Attempt {attempt}/{max_retries}: Facebook blocked this IP (HTTP {r.status_code}) — rotating static proxy...")
                new_p = rotate_static_proxy()
                if new_p:
                    proxies = new_p
                    PROXIES = new_p
            else:
                print(f"  ⚠️ Attempt {attempt}/{max_retries}: Status {r.status_code}")
        except requests.exceptions.ProxyError as e:
            print(f"  🚫 Attempt {attempt}/{max_retries}: Proxy unreachable — rotating static proxy...")
            new_p = rotate_static_proxy()
            if new_p:
                proxies = new_p
                PROXIES = new_p
        except Exception as e:
            if is_proxy_infra_error(exc=e):
                print(f"  🚫 Attempt {attempt}/{max_retries}: Proxy connection error — rotating static proxy...")
                new_p = rotate_static_proxy()
                if new_p:
                    proxies = new_p
                    PROXIES = new_p
            else:
                print(f"  ⚠️ Attempt {attempt}/{max_retries}: {str(e)}")

        if attempt < max_retries:
            wait_time = attempt * 2
            print(f"  ⏳ Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    raise Exception(f"Failed after {max_retries} attempts")


def download_image(url, post_id, image_index=1, save_dir=None):
    """Placeholder - Images are now stored as URLs in SQLite without downloading to disk"""
    return None


def fetch_remaining_images(last_media_id, post_id, current_image_count, save_dir=None):
    """Fetch remaining images metadata (for posts with 5+ images) without downloading to disk"""
    if not last_media_id or not post_id:
        return []
    
    DOC_ID_PHOTO = "26168653472729001"  # CometPhotoRootContentQuery
    HEADERS_PHOTO = {
        "user-agent": "Mozilla/5.0",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.facebook.com",
        "x-fb-friendly-name": "CometPhotoRootContentQuery"
    }
    
    remaining_photos = []
    current_node = last_media_id
    visited = set()
    image_index = current_image_count + 1
    
    while current_node and current_node not in visited and image_index <= 50:
        visited.add(current_node)
        
        variables = {
            "isMediaset": True,
            "renderLocation": "comet_media_viewer",
            "nodeID": current_node,
            "mediasetToken": f"pcb.{post_id}",
            "scale": 2,
            "feedLocation": "COMET_MEDIA_VIEWER",
            "feedbackSource": 65,
            "focusCommentID": None,
            "privacySelectorRenderLocation": "COMET_MEDIA_VIEWER",
            "useDefaultActor": False,
            "shouldShowComments": True
        }
        
        payload = {
            "av": COOKIES.get("c_user", "0"),
            "__user": COOKIES.get("c_user", "0"),
            "__a": "1",
            "fb_dtsg": FB_DTSG if FB_DTSG else "",
            "doc_id": DOC_ID_PHOTO,
            "variables": json.dumps(variables)
        }
        
        try:
            r = requests.post(GRAPHQL_URL, headers=HEADERS_PHOTO, data=payload, proxies=PROXIES, cookies=COOKIES, timeout=30)
            if r.status_code != 200:
                break
            
            cleaned_blocks = parse_fb_response(r.text)
            if not cleaned_blocks:
                break
            
            image_url = None
            for block in cleaned_blocks:
                if "currMedia" in block:
                    image_url = block["currMedia"].get("image", {}).get("uri")
                    break
            
            if image_url:
                remaining_photos.append({
                    'id': current_node,
                    'url': image_url,
                    'saved_as': None
                })
                image_index += 1
            
            next_node = None
            for block in cleaned_blocks:
                if "nextMediaAfterNodeId" in block and block["nextMediaAfterNodeId"]:
                    node_id = block["nextMediaAfterNodeId"].get("id")
                    if node_id:
                        next_node = node_id
                        break
            
            if next_node:
                current_node = next_node
                time.sleep(0.5)
            else:
                break
                
        except Exception as e:
            break

    return remaining_photos


def extract_data_blocks(raw_text):
    """Extract all 'data' blocks from raw text"""
    blocks = []
    i = 0
    n = len(raw_text)

    while True:
        idx = raw_text.find('"data"', i)
        if idx == -1:
            break

        brace_start = raw_text.find('{', idx)
        if brace_start == -1:
            break

        depth = 0
        for j in range(brace_start, n):
            if raw_text[j] == '{':
                depth += 1
            elif raw_text[j] == '}':
                depth -= 1
                if depth == 0:
                    block_text = raw_text[brace_start:j+1]
                    try:
                        block = json.loads(block_text)
                        blocks.append(block)
                    except Exception:
                        pass
                    i = j + 1
                    break
        else:
            break

    return blocks


def clean_data_blocks(blocks):
    """Clean unwanted keys from data blocks"""
    cleaned = []

    for block in blocks:
        if not isinstance(block, dict):
            continue

        block.pop("errors", None)
        block.pop("extensions", None)

        cleaned.append(block)

    return cleaned


def parse_fb_response(text):
    """Parse Facebook response using the same logic as post_scraper"""
    text = text.replace("for (;;);", "").strip()
    extracted = extract_data_blocks(text)
    cleaned = clean_data_blocks(extracted)
    return cleaned


def extract_comment_count(node):
    """Extract comment count from post node"""
    try:
        # Path 1: feedback.comment_rendering_instance.comments.total_count
        comment_count = node.get("feedback", {}).get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
        
        # Path 2: comet_sections.feedback.story.story_ufi_container.story.feedback_context.feedback_target_with_context.comment_rendering_instance.comments.total_count
        comet_sections = node.get("comet_sections", {})
        feedback_section = comet_sections.get("feedback", {})
        story = feedback_section.get("story", {})
        story_ufi_container = story.get("story_ufi_container", {})
        ufi_story = story_ufi_container.get("story", {})
        feedback_context = ufi_story.get("feedback_context", {})
        feedback_target = feedback_context.get("feedback_target_with_context", {})
        comment_count = feedback_target.get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
        
        # Path 3: comet_sections.feedback.story.story_ufi_container.story.feedback_context.feedback_target_with_context.comet_ufi_summary_and_actions_renderer.feedback.comment_rendering_instance.comments.total_count
        comet_ufi = feedback_target.get("comet_ufi_summary_and_actions_renderer", {}).get("feedback", {})
        comment_count = comet_ufi.get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
        
        # Path 4: comet_sections.feedback.story.feedback_context.feedback_target_with_context.comment_rendering_instance.comments.total_count (old structure)
        comet_sections = node.get("comet_sections", {})
        feedback_section = comet_sections.get("feedback", {})
        story = feedback_section.get("story", {})
        feedback_context = story.get("feedback_context", {})
        feedback_target = feedback_context.get("feedback_target_with_context", {})
        comment_count = feedback_target.get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
        
        # Path 5: feedback.comments_count_summary_renderer.feedback.comment_rendering_instance.comments.total_count
        comments_renderer = node.get("feedback", {}).get("comments_count_summary_renderer", {}).get("feedback", {})
        comment_count = comments_renderer.get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
        
        # Path 6: comet_sections.feedback.story.story_ufi_container.story.feedback_context.feedback_target_with_context.comet_ufi_summary_and_actions_renderer.feedback.comments_count_summary_renderer.feedback.comment_rendering_instance.comments.total_count
        comet_sections = node.get("comet_sections", {})
        feedback_section = comet_sections.get("feedback", {})
        story = feedback_section.get("story", {})
        story_ufi_container = story.get("story_ufi_container", {})
        ufi_story = story_ufi_container.get("story", {})
        feedback_context = ufi_story.get("feedback_context", {})
        feedback_target = feedback_context.get("feedback_target_with_context", {})
        comet_ufi = feedback_target.get("comet_ufi_summary_and_actions_renderer", {}).get("feedback", {})
        comments_count_renderer = comet_ufi.get("comments_count_summary_renderer", {}).get("feedback", {})
        comment_count = comments_count_renderer.get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
            
        return 0
    except Exception:
        return 0


def is_reel_or_video_post(node):
    """Check if the post is a reel or video post"""
    if not node or node.get('__typename') != 'Story':
        return False
    
    # Check for reel in story type or anywhere in node
    node_typename = node.get('__typename', '')
    if 'reel' in node_typename.lower():
        return True
    
    # Check comet_sections for reel content
    comet_sections = node.get('comet_sections', {})
    content = comet_sections.get('content', {})
    
    content_typename = content.get('__typename', '')
    if 'reel' in content_typename.lower():
        return True
    
    # Check attachments for video/reel content
    attachments = node.get('attachments', [])
    for attachment in attachments:
        # Check for video media type
        if 'media' in attachment and attachment['media'].get('__typename') == 'Video':
            return True
        
        # Check for reel substring in media object
        if 'media' in attachment and 'reel' in str(attachment['media']).lower():
            return True
        
        # Check in styles > attachment > media for video or reel
        styles_media = attachment.get('styles', {}).get('attachment', {}).get('media', {})
        if styles_media.get('__typename') == 'Video':
            return True
        if 'reel' in str(styles_media).lower():
            return True
        
        # Check all_subattachments for videos or reels
        for subattachment in attachment.get('all_subattachments', {}).get('nodes', []):
            if 'media' in subattachment and subattachment['media'].get('__typename') == 'Video':
                return True
            if 'media' in subattachment and 'reel' in str(subattachment['media']).lower():
                return True
    
    return False


def extract_media(node, post_id=None, save_dir=None):
    """Extract photo and video URLs from a post without downloading to disk"""
    media = {
        'photos': [],
        'videos': []
    }
    
    image_index = 0
    last_media_id = None
    
    attachments = node.get('attachments', [])
    
    for attachment in attachments:
        # Handle photo attachments
        if 'media' in attachment and attachment['media'].get('__typename') == 'Photo':
            photo_data = attachment.get('styles', {}).get('attachment', {}).get('media', {})
            if 'photo_image' in photo_data:
                image_index += 1
                media_id = attachment['media'].get('id')
                last_media_id = media_id
                image_url = photo_data['photo_image'].get('uri')
                media['photos'].append({
                    'id': media_id,
                    'url': image_url,
                    'width': photo_data['photo_image'].get('width'),
                    'height': photo_data['photo_image'].get('height'),
                    'saved_as': None
                })
        
        # Handle albums (multiple photos)
        if 'all_subattachments' in attachment:
            for subattachment in attachment.get('all_subattachments', {}).get('nodes', []):
                if 'media' in subattachment and subattachment['media'].get('__typename') == 'Photo':
                    image_index += 1
                    photo_data = subattachment.get('media', {})
                    media_id = photo_data.get('id')
                    last_media_id = media_id
                    if 'image' in photo_data:
                        image_url = photo_data['image'].get('uri')
                        media['photos'].append({
                            'id': media_id,
                            'url': image_url,
                            'width': photo_data['image'].get('width'),
                            'height': photo_data['image'].get('height'),
                            'saved_as': None
                        })
        
        # Handle video attachments
        if 'media' in attachment and attachment['media'].get('__typename') == 'Video':
            video_data = attachment.get('media', {})
            media['videos'].append({
                'id': video_data.get('id'),
                'url': video_data.get('playable_url'),
                'thumbnail': video_data.get('preferred_thumbnail', {}).get('image', {}).get('uri')
            })
    
    # Fetch remaining images if we have exactly 5 photos
    if image_index == 5 and last_media_id:
        remaining_photos = fetch_remaining_images(last_media_id, post_id, image_index, save_dir)
        media['photos'].extend(remaining_photos)
    
    return media


def post_already_exists(post_id, base_folder=None):
    """Check if a post has already been scraped in SQLite"""
    if not post_id:
        return False
    return database.post_exists(str(post_id))


def extract_post_data(node, group_name=None):
    """Extract relevant data from a post node (in-memory only, no disk files)"""
    if not node or node.get('__typename') != 'Story':
        return None
    
    content_story = node.get('comet_sections', {}).get('content', {}).get('story', {})
    
    message = ''
    message_obj = content_story.get('message', {})
    if message_obj:
        message = message_obj.get('text', '')
    
    post_id = node.get('post_id')
    if not post_id:
        return None
    
    comment_count = extract_comment_count(node)
    
    if not group_name:
        group_name = extract_group_name(node)
    
    creation_time = extract_creation_time(node)

    post_data = {
        'id': node.get('id'),
        'post_id': post_id,
        'message': message,
        'comment_count': comment_count,
        'group_name': group_name,
        'permalink': node.get('permalink_url', ''),
        'creation_time': creation_time,
        'photos': extract_media(node, post_id)['photos'],
        'videos': extract_media(node, post_id)['videos']
    }
    
    return post_data


def fetch_posts(limit=10, min_comments=0, batch_size=10, on_batch_complete=None, group_id=None, group_name=None, cookies=None, fb_dtsg=None, logger=None, target_count=None):
    """Fetch posts from Facebook group
    
    Args:
        limit: Maximum number of posts to fetch
        min_comments: Minimum number of comments required for a post to be included (0 = no filter)
        batch_size: Number of posts to fetch before calling on_batch_complete callback
        on_batch_complete: Optional callback function(batch_posts, total_so_far, limit) called after each batch
        group_id: Optional Group ID to override GROUP_ID
        group_name: Optional group name to associate with scraped posts
        cookies: Optional cookies dictionary
        fb_dtsg: Optional fb_dtsg token
        logger: Optional logging callback
        target_count: Alias for limit (for backward compatibility)
    """
    global GROUP_NAME, GROUP_ID, COOKIES, FB_DTSG, HEADERS
    if target_count is not None and (limit == 10 or limit is None):
        limit = target_count
    if group_id:
        GROUP_ID = str(group_id)
        HEADERS["referer"] = f"https://www.facebook.com/groups/{GROUP_ID}/"
    if cookies:
        COOKIES = cookies
    if fb_dtsg:
        FB_DTSG = fb_dtsg

    # Reset GROUP_NAME per fetch to avoid leaking previous group name
    GROUP_NAME = group_name.strip() if (group_name and str(group_name).strip()) else None

    all_posts = []
    batch_posts = []
    cursor = None
    page_num = 1
    
    if min_comments > 0:
        print(f"📊 Filtering posts with at least {min_comments} comments")
    
    if batch_size > 0 and batch_size < limit:
        print(f"📦 Processing in batches of {batch_size} posts")
    
    while len(all_posts) < limit:
        print(f"\nFetching page {page_num}...")
        
        fetch_count = max(3, min(limit - len(all_posts), 10))
        variables = {
            "count": fetch_count,
            "cursor": cursor,
            "feedLocation": "GROUP",
            "feedType": "DISCUSSION",
            "feedbackSource": 0,
            "filterTopicId": None,
            "focusCommentID": None,
            "privacySelectorRenderLocation": "COMET_STREAM",
            "renderLocation": "group",
            "scale": 2,
            #"sortingSetting": "TOP_POSTS",
            "stream_initial_count": 1,
            "useDefaultActor": False,
            "id": GROUP_ID,
        }
        
        payload = {
            "av": COOKIES.get("c_user", "0"),
            "__user": COOKIES.get("c_user", "0"),
            "__a": "1",
            "fb_dtsg": FB_DTSG if FB_DTSG else "",
            "doc_id": DOC_ID,
            "variables": json.dumps(variables),
        }
        
        # Retry loop for empty response handling
        max_empty_retries = 3
        empty_retry_count = 0
        data = []
        
        while empty_retry_count < max_empty_retries:
            try:
                r = retry_request(GRAPHQL_URL, HEADERS, payload, PROXIES)
                r.raise_for_status()
            except requests.RequestException as e:
                print(f"Request failed: {e}")
                break
            
            # Parse the response
            data = parse_fb_response(r.text)
            
            if data and len(data) > 0:
                # Got valid data, break retry loop
                break
            else:
                empty_retry_count += 1
                if empty_retry_count < max_empty_retries:
                    print(f"  ⚠️ Empty response, retrying ({empty_retry_count}/{max_empty_retries})...")
                    time.sleep(2)  # Wait before retry
                else:
                    print(f"  ❌ Empty response after {max_empty_retries} attempts, skipping page")
        
        if not data or len(data) == 0:
            print("❌ No data received after retries, stopping pagination")
            break
        
        # Save raw response for debugging
        # with open(f"scratch/group_raw_page_{page_num}.json", "w", encoding="utf-8") as f:
        #     json.dump(data, f, ensure_ascii=False, indent=2)
        # print(f"Saved scratch/group_raw_page_{page_num}.json")
        
        # Extract posts from the response array
        posts_found = 0
        next_cursor = None
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            node = item.get('node', {})
            node_typename = node.get('__typename')
            
            # Collect Story nodes from multiple sources
            story_nodes = []
            
            # Direct Story node
            if node_typename == 'Story':
                story_nodes.append(node)
            
            # Story nodes inside Group edges
            elif node_typename == 'Group':
                edges = node.get('group_feed', {}).get('edges', [])
                for edge in edges:
                    edge_node = edge.get('node', {})
                    if edge_node.get('__typename') == 'Story':
                        story_nodes.append(edge_node)
            
            # Process all found Story nodes
            for story_node in story_nodes:
                # Skip reels and video posts
                if is_reel_or_video_post(story_node):
                    print(f"  ⏭️  Skipping reel/video post")
                    continue
                
                # Check comment count threshold
                comment_count = extract_comment_count(story_node)
                if min_comments > 0 and comment_count < min_comments:
                    print(f"  ⏭️  Skipping post with only {comment_count} comments (need {min_comments}+)")
                    continue
                
                # Extract group name from first post if not set
                if not GROUP_NAME:
                    GROUP_NAME = extract_group_name(story_node)
                    if GROUP_NAME:
                        print(f"📂 Group name: {GROUP_NAME}")
                
                # Check if post already exists
                temp_post_id = story_node.get('post_id')
                is_existing = post_already_exists(temp_post_id)
                if is_existing:
                    print(f"  ℹ️  Post {temp_post_id} already exists in DB -> will fetch to update comments")
                
                post_data = extract_post_data(story_node, GROUP_NAME)
                if post_data:
                    post_data['is_existing'] = is_existing
                    batch_posts.append(post_data)
                    all_posts.append(post_data)
                    posts_found += 1
                    status_str = "existing -> update comments" if is_existing else "new"
                    print(f"  - Process post: {post_data['post_id']} ({status_str})")
                    
                    # Check if we should process this batch
                    if batch_size > 0 and len(batch_posts) >= batch_size and on_batch_complete:
                        print(f"\n📦 Batch complete: {len(batch_posts)} posts. Total: {len(all_posts)}/{limit}")
                        on_batch_complete(batch_posts, len(all_posts), limit)
                        batch_posts = []  # Reset batch
                    
                    if len(all_posts) >= limit:
                        break
            
            # Break outer loop if limit reached
            if len(all_posts) >= limit:
                break
            
            # Look for pagination info
            if 'page_info' in item:
                page_info = item['page_info']
                if page_info.get('has_next_page'):
                    next_cursor = page_info.get('end_cursor')
        
        print(f"Found {posts_found} posts on this page")
        
        # Check if we should continue
        if not next_cursor or len(all_posts) >= limit:
            print("No more pages or reached limit. Stopping.")
            break
        
        cursor = next_cursor
        page_num += 1
        time.sleep(1)  # Be nice to the server
    
    # Process any remaining posts in the final batch
    if batch_posts and on_batch_complete:
        print(f"\n📦 Final batch: {len(batch_posts)} posts. Total: {len(all_posts)}/{limit}")
        on_batch_complete(batch_posts, len(all_posts), limit)
    
    return all_posts


if __name__ == "__main__":
    count = int(input("How many posts to fetch? "))
    
    print(f"\nFetching {count} posts from group {GROUP_ID}...")
    posts = fetch_posts(count)
    
    # Save posts to file
    with open("group_posts.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Saved {len(posts)} posts to group_posts.json")
    
    # Print summary
    print("\nSummary:")
    for i, post in enumerate(posts, 1):
        photos = len(post['photos'])
        videos = len(post['videos'])
        print(f"{i}. Post ID: {post['post_id']}")
        if photos:
            print(f"   📷 {photos} photo(s)")
        if videos:
            print(f"   🎥 {videos} video(s)")
        if post['message']:
            preview = post['message'][:100] + '...' if len(post['message']) > 100 else post['message']
            print(f"   {preview}")
