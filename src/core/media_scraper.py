import requests
import json
import os
import uuid
import time
from src.core.proxy_utils import select_proxy

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"

# FB_DTSG token (set by UI when provided)
FB_DTSG = ""

# ======================================
# 🔥 FILL THESE FROM BROWSER SESSION
# ======================================
DOC_ID = "26168653472729001"

HEADERS = {
    "user-agent": "Mozilla/5.0",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.facebook.com",
    "x-fb-friendly-name": "CometPhotoRootContentQuery"}


# ======================================
# BUILD PAYLOAD
# ======================================

def build_payload(node_id, post_id, cookies=None):
    # Extract user ID from cookies if available
    user_id = "0"
    if cookies and "c_user" in cookies:
        user_id = cookies["c_user"]
    
    variables = {
        "isMediaset": True,
        "renderLocation": "comet_media_viewer",
        "nodeID": node_id,
        "mediasetToken": f"pcb.{post_id}",
        "scale": 2,
        "feedLocation": "COMET_MEDIA_VIEWER",
        "feedbackSource": 65,
        "focusCommentID": None,
        "privacySelectorRenderLocation": "COMET_MEDIA_VIEWER",
        "useDefaultActor": False,
        "shouldShowComments": True
    }

    return {
        "av": user_id,
        "__user": user_id,
        "__a": "1",
        "fb_dtsg": FB_DTSG if FB_DTSG else "",
         "doc_id": DOC_ID,
        "variables": json.dumps(variables)
    }


# ======================================
# RAW CLEANING FUNCTIONS (MERGED)
# ======================================

def extract_data_blocks(raw_text):
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
                    except:
                        pass
                    i = j + 1
                    break
        else:
            break

    return blocks


def clean_data_blocks(blocks):
    cleaned = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block.pop("errors", None)
        block.pop("extensions", None)
        cleaned.append(block)
    return cleaned


def process_raw_graphql(raw_text):

    extracted = extract_data_blocks(raw_text)
    cleaned = clean_data_blocks(extracted)
    return cleaned


# ======================================
# DOWNLOAD IMAGE WITH RETRY
# ======================================

def download_image(url, folder=None, post_id=None, image_index=1, max_retries=3):
    """Placeholder - Images are stored as URLs in SQLite without downloading to disk"""
    return None


# ======================================
# FETCH ALL IMAGES LOOP
# ======================================

def fetch_all_images(start_node_id, post_id):
    current_node = start_node_id
    visited = set()
    extracted_images = []

    while current_node and current_node not in visited:
        print(f"\n➡ Fetching node: {current_node}")
        visited.add(current_node)

        payload = build_payload(current_node, post_id)
        r = requests.post(GRAPHQL_URL, headers=HEADERS, data=payload, proxies=PROXIES)

        cleaned_blocks = process_raw_graphql(r.text)
        if not cleaned_blocks:
            print("❌ No cleaned data found")
            break

        image_url = None
        for block in cleaned_blocks:
            if "currMedia" in block:
                image_url = block["currMedia"].get("image", {}).get("uri")
                break

        if image_url:
            print(f"✅ Found image URI: {image_url[:60]}...")
            extracted_images.append({
                "id": current_node,
                "url": image_url
            })
        else:
            print("❌ No image found")

        next_node = None
        for block in cleaned_blocks:
            if "nextMediaAfterNodeId" in block and block["nextMediaAfterNodeId"]:
                node_id = block["nextMediaAfterNodeId"].get("id")
                if node_id:
                    next_node = node_id
                    break

        if next_node:
            current_node = next_node
        else:
            print("✅ No more images.")
            break

    return extracted_images


# ======================================
# RUN
# ======================================

if __name__ == "__main__":
    start_node = input("Enter first photo nodeID: ").strip()
    post_id = input("Enter post_id: ").strip()

    fetch_all_images(start_node, post_id)
