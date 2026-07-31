import os
import re
import time
import requests
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# ==========================================
# 1. NẠP CẤU HÌNH TỪ FILE .env
# ==========================================
load_dotenv()

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "").strip()
USER_ACCESS_TOKEN = os.getenv("USER_ACCESS_TOKEN", "").strip()
PAGE_ID = os.getenv("PAGE_ID", "").strip()
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v20.0").strip()

# ==========================================
# 2. ĐỌC DỮ LIỆU TỪ CÁC FILE TXT
# ==========================================
def load_list_from_file(file_path: str) -> list:
    """Hàm đọc dữ liệu từ file txt, trả về danh sách các dòng (bỏ qua dòng trống và khoảng trắng)"""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    print(f"[WARNING] Không tìm thấy file {file_path}.")
    return []

# Đọc danh sách từ khóa spam & danh sách ID bài viết
SPAM_KEYWORDS = load_list_from_file("spam_word.txt")
POST_IDS = load_list_from_file("post_ids.txt")


# ==========================================
# 3. CÁC HÀM XỬ LÝ GRAPH API
# ==========================================

def get_page_access_token(user_token: str, page_id: str, version: str = "v20.0") -> str:
    """Tự động chuyển đổi User Access Token thành Page Access Token.
    Dùng graph_get_with_retry để tự retry khi bị rate-limit tạm thời - trước đây gọi 1 lần
    duy nhất, nếu trúng lúc app bị rate-limit thì âm thầm rơi vào fallback trả về User Token
    thô (không dùng được cho các API theo ngữ cảnh Page), gây lỗi "Invalid OAuth 2.0 Access Token"
    ở các bước sau dù User Token vẫn hợp lệ."""
    url = f"https://graph.facebook.com/{version}/{page_id}"
    params = {
        "fields": "access_token,name",
        "access_token": user_token
    }
    data = graph_get_with_retry(url, params)
    if "access_token" in data:
        print(f"[AUTH] Lấy Page Access Token thành công cho Trang: {data.get('name')}")
        return data["access_token"]
    else:
        print(f"[AUTH WARNING] Không lấy được Page Access Token riêng. Chi tiết: {data}")
        return user_token


def delete_comment(comment_id: str, access_token: str, version: str = "v20.0", max_retries: int = 5) -> bool:
    """Gửi request DELETE xóa comment theo ID, tự động retry (exponential backoff) khi bị
    Facebook rate-limit hoặc lỗi mạng tạm thời - trước đây không có retry nên hay bị coi là
    xóa thất bại ngay khi app chạm giới hạn tần suất gọi API (đặc biệt sau khi quét nhiều comment)."""
    url = f"https://graph.facebook.com/{version}/{comment_id}"
    params = {"access_token": access_token}
    delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.delete(url, params=params, timeout=30)
            data = response.json()
            if response.status_code == 200 and data.get("success") is True:
                print(f"  [SUCCESS] Đã xóa thành công comment ID: {comment_id}")
                return True

            err = data.get("error", {})
            err_code = err.get("code")
            if err_code == 190:
                raise TokenExpiredError(err.get("message", "Access token không hợp lệ"))
            if is_transient_error(err) and attempt < max_retries:
                print(f"  [RATE LIMIT] Xóa comment {comment_id} bị giới hạn tốc độ, thử lại sau {delay}s (lần {attempt}/{max_retries})...")
                time.sleep(delay)
                delay *= 2
                continue

            print(f"  [ERROR] Không thể xóa comment ID {comment_id}: {data}")
            return False
        except TokenExpiredError:
            raise
        except Exception as e:
            if attempt < max_retries:
                print(f"  [RETRY] Lỗi kết nối khi xóa comment {comment_id} ({e}), thử lại sau {delay}s (lần {attempt}/{max_retries})...")
                time.sleep(delay)
                delay *= 2
                continue
            print(f"  [EXCEPTION] Lỗi khi kết nối tới API: {e}")
            return False
    return False


def hide_comment(comment_id: str, access_token: str, version: str = "v20.0", max_retries: int = 5) -> bool:
    """Ẩn comment (is_hidden=true) thay vì xóa hẳn - comment chỉ còn hiển thị với người đăng
    và bạn bè của họ, có thể hiện lại được nếu quét nhầm. Cùng cơ chế retry như delete_comment."""
    url = f"https://graph.facebook.com/{version}/{comment_id}"
    params = {"access_token": access_token, "is_hidden": "true"}
    delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, params=params, timeout=30)
            data = response.json()
            if response.status_code == 200 and data.get("success") is True:
                print(f"  [SUCCESS] Đã ẩn thành công comment ID: {comment_id}")
                return True

            err = data.get("error", {})
            err_code = err.get("code")
            if err_code == 190:
                raise TokenExpiredError(err.get("message", "Access token không hợp lệ"))
            if is_transient_error(err) and attempt < max_retries:
                print(f"  [RATE LIMIT] Ẩn comment {comment_id} bị giới hạn tốc độ, thử lại sau {delay}s (lần {attempt}/{max_retries})...")
                time.sleep(delay)
                delay *= 2
                continue

            print(f"  [ERROR] Không thể ẩn comment ID {comment_id}: {data}")
            return False
        except TokenExpiredError:
            raise
        except Exception as e:
            if attempt < max_retries:
                print(f"  [RETRY] Lỗi kết nối khi ẩn comment {comment_id} ({e}), thử lại sau {delay}s (lần {attempt}/{max_retries})...")
                time.sleep(delay)
                delay *= 2
                continue
            print(f"  [EXCEPTION] Lỗi khi kết nối tới API: {e}")
            return False
    return False


class TokenExpiredError(Exception):
    """Access token không còn hợp lệ (hết hạn/bị thu hồi) - cần cấp token mới, retry không giúp được"""
    pass


def is_transient_error(err: dict) -> bool:
    """Nhận diện lỗi tạm thời của Graph API nên thử lại: rate-limit (4/17/32/613) hoặc
    lỗi "Please reduce the amount of data..." (code 1) - lỗi này cũng tự hết sau vài giây
    khi gọi API dồn dập (vd: xóa/ẩn liên tiếp nhiều comment), trước đây không được retry
    nên vài spam comment bị bỏ sót dù đã quét ra."""
    err_code = err.get("code")
    if err_code in (4, 17, 32, 613):
        return True
    if err_code == 1 and "reduce the amount of data" in err.get("message", "").lower():
        return True
    return False


def graph_get_with_retry(url: str, params: dict, max_retries: int = 5) -> dict:
    """Gọi GET tới Graph API, tự động retry (exponential backoff) khi gặp lỗi mạng
    hoặc bị Facebook rate-limit (error code 4/17/32/613), thay vì bỏ cuộc ngay lập tức.
    Đây là nguyên nhân chính khiến trước đây quét bị đứt giữa chừng và bỏ sót comment."""
    delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            res = requests.get(url, params=params, timeout=30)
            data = res.json()
            err = data.get("error", {})
            err_code = err.get("code")
            if res.status_code == 200 and "error" not in data:
                return data
            if err_code == 190:
                # Token hết hạn/không hợp lệ: retry vô ích, phải dừng và báo ngay
                raise TokenExpiredError(err.get("message", "Access token không hợp lệ"))
            if is_transient_error(err) and attempt < max_retries:
                print(f"    [RATE LIMIT] Bị giới hạn tốc độ, thử lại sau {delay}s (lần {attempt}/{max_retries})...")
                time.sleep(delay)
                delay *= 2
                continue
            return data
        except TokenExpiredError:
            raise
        except Exception as e:
            if attempt < max_retries:
                print(f"    [RETRY] Lỗi kết nối ({e}), thử lại sau {delay}s (lần {attempt}/{max_retries})...")
                time.sleep(delay)
                delay *= 2
                continue
            return {"error": {"message": str(e)}}
    return {"error": {"message": "max retries exceeded"}}


def get_sub_comments(comment_id: str, access_token: str, version: str = "v20.0") -> list:
    """Lấy toàn bộ các bình luận trả lời (sub-comments/replies) bên dưới 1 comment gốc"""
    url = f"https://graph.facebook.com/{version}/{comment_id}/comments"
    params = {
        "access_token": access_token,
        "fields": "id,message,from,created_time",
        "limit": 100
    }
    sub_comments = []
    while url:
        res = graph_get_with_retry(url, params)
        if "data" in res:
            sub_comments.extend(res["data"])
        else:
            print(f"    [WARNING] Không lấy được sub-comment của {comment_id}: {res.get('error')}")
        url = res.get("paging", {}).get("next")
        params = None
    return sub_comments


def fetch_all_post_comments(post_id: str, access_token: str, version: str = "v20.0") -> list:
    """
    Lấy 100% TẤT CẢ bình luận (bao gồm cả bình luận gốc và toàn bộ các câu trả lời/sub-comments)
    bằng cách dùng order=chronological kết hợp quét đệ quy các sub-comments.
    """
    url = f"https://graph.facebook.com/{version}/{post_id}/comments"
    params = {
        "access_token": access_token,
        "fields": "id,message,from,created_time,comment_count",
        "order": "chronological",
        "limit": 100
    }
    
    all_comments = []
    while url:
        data = graph_get_with_retry(url, params if params else None)

        if "data" in data:
            items = data["data"]
            for c in items:
                all_comments.append(c)
                # Lấy toàn bộ phản hồi bên dưới comment gốc nếu có
                # (kiểm tra cả trường hợp comment_count bị thiếu trong response)
                if c.get("comment_count", 1) > 0:
                    replies = get_sub_comments(c["id"], access_token, version)
                    all_comments.extend(replies)

            url = data.get("paging", {}).get("next")
            params = None
        else:
            print(f"  [ERROR] Lỗi khi lấy comment bài viết {post_id}: {data.get('error', data)}")
            break

    print(f"  [INFO] Lấy FULL thành công {len(all_comments)} bình luận (bao gồm cả bình luận gốc & trả lời) từ Bài viết ID: {post_id}")
    return all_comments


import unicodedata

# Các ký tự vô hình / khoảng trắng đặc biệt hay bị spam chèn vào để né lọc từ khóa
_INVISIBLE_CHARS_RE = re.compile(r"[​‌‍⁠﻿]")
# Dấu phân cách bị chèn xen kẽ giữa từng ký tự để né lọc, vd: "s.p.a.m", "l i n k", "b-a-n"
_SEPARATOR_BETWEEN_LETTERS_RE = re.compile(
    r"(?<=[^\W\d_])[\s\.\-_,*]+(?=[^\W\d_])", re.UNICODE
)


def strip_diacritics(text: str) -> str:
    """Bỏ dấu tiếng Việt/dấu thanh để so khớp không phân biệt có dấu hay không dấu"""
    normalized = unicodedata.normalize('NFD', text)
    without_marks = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
    # Chữ "đ" không tách dấu qua NFD nên cần thay riêng
    return without_marks.replace('đ', 'd').replace('Đ', 'D')


def normalize_text(text: str) -> str:
    """Chuẩn hóa Unicode (NFC), bỏ ký tự vô hình và chuyển về chữ thường để so sánh"""
    if not text:
        return ""
    text = unicodedata.normalize('NFC', text)
    text = _INVISIBLE_CHARS_RE.sub("", text)
    return text.lower().strip()


def build_match_variants(text: str) -> dict:
    """Tạo các biến thể của văn bản để so khớp linh hoạt hơn, giúp bắt được các
    chiêu né từ khóa thường gặp (chèn dấu cách/dấu chấm giữa chữ, gõ không dấu).
    Trả về dict theo từng "loại" biến thể để so khớp đúng cặp (keyword loại nào
    thì so với message cùng loại đó, tránh so lệch làm mất kết quả)."""
    base = normalize_text(text)
    collapsed = _SEPARATOR_BETWEEN_LETTERS_RE.sub("", base)
    return {
        "base": base,
        "collapsed": collapsed,
        "base_no_diacritics": strip_diacritics(base),
        "collapsed_no_diacritics": strip_diacritics(collapsed),
    }


# Từ khóa ngắn hơn ngưỡng này rất dễ trùng vào giữa các từ tiếng Việt thông thường
# (vd: "no" trùng vào "nó", "18" trùng vào ngày/tháng/giá tiền...) nên chỉ so khớp
# nguyên từ (word boundary) trên bản gốc có dấu, không dùng các biến thể bỏ dấu/gộp
# khoảng trắng để tránh xóa oan bình luận hợp lệ.
MIN_FUZZY_KEYWORD_LEN = 4


def text_contains_keyword(text_variants: dict, keyword_variants: dict) -> bool:
    """So khớp keyword với message theo từng cặp biến thể cùng loại.

    3 trường hợp:
    1. Từ khóa 1-từ quá ngắn (vd "no", "18"): CHỈ so khớp nguyên từ trên bản CÓ DẤU gốc
       - tuyệt đối không dùng bản bỏ dấu, vì các âm tiết ngắn tiếng Việt rất dễ trùng
       nhau sau khi bỏ dấu (vd "nó" bỏ dấu thành "no", trùng thẳng với từ khóa "no").
    2. Từ khóa nhiều từ (có khoảng trắng, vd "t me", "pm me"): so khớp nguyên cụm (word
       boundary) trên MỌI biến thể (kể cả bỏ dấu) - an toàn hơn vì cụm dài ít trùng ngẫu
       nhiên hơn 1 âm tiết, nhưng vẫn cần word boundary để tránh trùng ngang qua ranh giới
       2 từ khác (vd "đạt mệt" bỏ dấu thành "dat met" chứa sẵn chuỗi con "t met" -> trùng
       "t me" dù câu không hề nhắc đến Telegram).
    3. Từ khóa dài, không khoảng trắng (vd "cm88"): so khớp chuỗi con bình thường để bắt
       được các biến thể ghép (vd "cm8806")."""
    keyword_base = keyword_variants["base"]
    if not keyword_base:
        return False

    has_space = " " in keyword_base

    if not has_space and len(keyword_base) < MIN_FUZZY_KEYWORD_LEN:
        pattern = r"(?<!\w)" + re.escape(keyword_base) + r"(?!\w)"
        return re.search(pattern, text_variants["base"], re.UNICODE) is not None

    if has_space:
        for kind, text_value in text_variants.items():
            kw = keyword_variants[kind]
            if kw and re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", text_value, re.UNICODE):
                return True
        return False

    return any(
        keyword_variants[kind] and keyword_variants[kind] in text_variants[kind]
        for kind in text_variants
    )


def scan_and_delete_spam(post_id: str, page_token: str, keywords: list, version: str = "v20.0", action: str = "delete"):
    """Quét comment chứa từ khóa spam cho 1 bài viết (không phân biệt chữ hoa/chữ thường).
    action="delete": xóa hẳn. action="hide": chỉ ẩn (an toàn hơn, hiện lại được nếu quét nhầm)."""
    comments = fetch_all_post_comments(post_id, page_token, version)
    processed_count = 0
    action_fn = hide_comment if action == "hide" else delete_comment
    action_label = "ẩn" if action == "hide" else "xóa"

    # Chuẩn hóa danh sách từ khóa thành các biến thể (có dấu/không dấu, gộp khoảng cách)
    normalized_keywords = [(kw, build_match_variants(kw)) for kw in keywords if kw.strip()]

    for item in comments:
        comment_id = item.get("id")
        raw_message = item.get("message", "")
        # "Unknown" chỉ dùng để HIỂN THỊ khi Facebook không trả về tác giả - tuyệt đối
        # không được dùng chuỗi này để so khớp từ khóa (nó chứa sẵn chuỗi con "no",
        # từng khiến MỌI comment thiếu tác giả bị coi nhầm là spam và bị xóa oan).
        author_display = item.get("from", {}).get("name") or "Unknown"
        author_for_matching = item.get("from", {}).get("name") or ""

        # So khớp trên nhiều biến thể của nội dung (và cả tên người bình luận) để
        # bắt được các chiêu né từ khóa: chèn dấu cách/chấm giữa chữ, gõ không dấu...
        message_variants = build_match_variants(raw_message)
        author_variants = build_match_variants(author_for_matching)

        matched_keywords = [
            original_kw for original_kw, kw_variants in normalized_keywords
            if text_contains_keyword(message_variants, kw_variants)
            or text_contains_keyword(author_variants, kw_variants)
        ]

        if matched_keywords:
            # Từ khóa ngắn (vd "tg", "wa", "no") dù chỉ khớp nguyên từ vẫn có thể là chữ viết
            # tắt bình thường trong tiếng Việt (vd "tg" = "thời gian"), không chắc chắn là spam.
            # Chỉ tự động xử lý khi có ít nhất 1 từ khóa "chắc chắn" (dài >= ngưỡng, hoặc là link).
            has_strong_signal = any(
                len(build_match_variants(kw)["base"]) >= MIN_FUZZY_KEYWORD_LEN
                for kw in matched_keywords
            )

            print(f"\n  [SPAM DETECTED] Người dùng: '{author_display}' | ID Comment: {comment_id}")
            print(f"    Nội dung: '{raw_message}'")
            print(f"    Từ khóa vi phạm: {matched_keywords}")

            if not has_strong_signal:
                print(f"  [CẦN KIỂM TRA THỦ CÔNG] Chỉ khớp từ khóa ngắn/mơ hồ, KHÔNG tự động {action_label} - vui lòng kiểm tra tay.")
                continue

            if action_fn(comment_id, page_token, version):
                processed_count += 1

    print(f"  ===> Hoàn tất quét Bài viết ID: {post_id}! Đã {action_label} {processed_count} bình luận spam.")


# ==========================================
# CHẠY QUÉT DỰA TRÊN DANH SÁCH POST_IDS
# ==========================================
if __name__ == "__main__":
    print("==================================================")
    print(f"[INIT] Đã nạp {len(SPAM_KEYWORDS)} từ khóa từ file spam_word.txt")
    print(f"[INIT] Đã nạp {len(POST_IDS)} bài viết từ file post_ids.txt")
    print("==================================================")

    if not PAGE_ACCESS_TOKEN and not USER_ACCESS_TOKEN:
        print("[CRITICAL ERROR] Không tìm thấy TOKEN trong file .env!")
        exit(1)

    # 1. Lấy Page Access Token - luôn đổi qua get_page_access_token dù token đầu vào là
    # PAGE_ACCESS_TOKEN hay USER_ACCESS_TOKEN. Một số Trang dùng "New Pages Experience"
    # từ chối token Trang dán trực tiếp (lỗi "cần mã truy cập Trang đối với trải nghiệm
    # Trang mới") trừ khi được đổi qua bước này; đổi qua token Trang hợp lệ sẵn có cũng
    # an toàn, không gây hại.
    raw_token = PAGE_ACCESS_TOKEN or USER_ACCESS_TOKEN
    page_access_token = get_page_access_token(raw_token, PAGE_ID, GRAPH_API_VERSION)
    
    # 2. Vòng lặp duyệt qua từng ID bài viết trong post_ids.txt
    for idx, raw_post_id in enumerate(POST_IDS, 1):
        target_post_id = raw_post_id
        
        # Tự động ghép PAGE_ID nếu ID bài viết chưa có tiền tố PAGE_ID_
        if target_post_id and "_" not in target_post_id and PAGE_ID:
            target_post_id = f"{PAGE_ID}_{target_post_id}"

        print(f"\n[{idx}/{len(POST_IDS)}] ---> Bắt đầu quét bài viết ID: {target_post_id}")
        try:
            scan_and_delete_spam(target_post_id, page_access_token, SPAM_KEYWORDS, GRAPH_API_VERSION, action="hide")
        except TokenExpiredError as e:
            print("\n==================================================")
            print(f"[CRITICAL ERROR] Access Token đã hết hạn hoặc không hợp lệ: {e}")
            print("  ==> Vào Graph API Explorer / Business Suite để lấy token mới,")
            print("      cập nhật vào file .env rồi chạy lại script.")
            print("==================================================")
            exit(1)

    print("\n==================================================")
    print("🎉 HOÀN THÀNH TOÀN BỘ QUÁ TRÌNH QUÉT TẤT CẢ BÀI VIẾT!")
    print("==================================================")