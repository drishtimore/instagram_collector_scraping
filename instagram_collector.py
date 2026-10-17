
import asyncio
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
PROFILE_DIR = DATA_DIR / "profiles"
POST_DIR = DATA_DIR / "posts"
HTML_DIR = DATA_DIR / "html"
SCREENSHOT_DIR = DATA_DIR / "screenshots"

BROWSER_PROFILE = BASE_DIR / "instagram_chromium_profile"

CSV_FILE = DATA_DIR / "instagram_profiles_raw.csv"
USERNAME_FILE = BASE_DIR / "usernames.txt"

# Default: process up to 100 accounts per run.
MAX_ACCOUNTS = int(os.getenv("MAX_ACCOUNTS", "100"))
MAX_POSTS_PER_ACCOUNT = int(
    os.getenv("MAX_POSTS_PER_ACCOUNT", "15")
)
PAGE_WAIT_SECONDS = float(
    os.getenv("PAGE_WAIT_SECONDS", "3")
)


# ============================================================
# CREATE DIRECTORIES
# ============================================================

for folder in [
    DATA_DIR,
    PROFILE_DIR,
    POST_DIR,
    HTML_DIR,
    SCREENSHOT_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def safe_filename(value: str) -> str:
    """Make a Windows-safe filename."""
    return re.sub(r'[<>:"/\\|?*]', "_", value)


def extract_metric(text: str, patterns):
    """Extract a numeric metric from text using multiple regex patterns."""
    if not text:
        return None

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def timestamp():
    return datetime.now().isoformat(timespec="seconds")


# ============================================================
# SAFETY CHECK
# ============================================================

async def safety_check(page):
    """
    Stop collection if Instagram appears to show:
    - CAPTCHA
    - checkpoint
    - challenge
    - unusual activity
    - account suspension
    - security verification
    """

    url = page.url.lower()

    dangerous_url_patterns = [
        "/challenge/",
        "/checkpoint/",
        "/accounts/suspended/",
        "/accounts/login/",
    ]

    for pattern in dangerous_url_patterns:
        if pattern in url:
            print()
            print("=" * 70)
            print("SAFETY STOP")
            print(f"Instagram security/login page detected: {url}")
            print("Collection has been stopped.")
            print("=" * 70)
            print()
            return False

    try:
        body_text = await page.locator("body").inner_text(
            timeout=5000
        )
        body_text = body_text.lower()
    except Exception:
        body_text = ""

    warning_phrases = [
        "captcha",
        "security check",
        "suspicious activity",
        "confirm it's you",
        "confirm that it's you",
        "automated behavior",
        "try again later",
        "we detected unusual",
        "verify your identity",
        "challenge required",
    ]

    for phrase in warning_phrases:
        if phrase in body_text:
            print()
            print("=" * 70)
            print("SAFETY STOP")
            print(f"Instagram warning detected: {phrase}")
            print("Collection has been stopped.")
            print("Do NOT attempt to bypass the warning.")
            print("=" * 70)
            print()
            return False

    return True


# ============================================================
# SAVE HTML
# ============================================================

async def save_html(page, filename: str):
    path = HTML_DIR / filename

    try:
        html = await page.content()
        path.write_text(html, encoding="utf-8")
        return str(path)

    except Exception as e:
        print(f"Could not save HTML: {e}")
        return ""


# ============================================================
# SAVE SCREENSHOT
# ============================================================

async def save_screenshot(page, filename: str):
    path = SCREENSHOT_DIR / filename

    try:
        await page.screenshot(
            path=str(path),
            full_page=True
        )
        return str(path)

    except Exception as e:
        print(f"Could not save screenshot: {e}")
        return ""


# ============================================================
# MANUAL LOGIN
# ============================================================

async def prepare_session(page):
    print()
    print("=" * 70)
    print("OPENING INSTAGRAM")
    print("=" * 70)

    await page.goto(
        "https://www.instagram.com/",
        wait_until="domcontentloaded",
        timeout=60000
    )

    await page.wait_for_timeout(
        int(PAGE_WAIT_SECONDS * 1000)
    )

    if not await safety_check(page):
        return False

    # Detect login page.
    try:
        login_input = page.locator('input[name="username"]')
        login_visible = await login_input.is_visible(
            timeout=3000
        )
    except Exception:
        login_visible = False

    if login_visible:
        print()
        print("=" * 70)
        print("MANUAL LOGIN REQUIRED")
        print("=" * 70)
        print("Log in manually in the browser.")
        print("Complete 2FA/security verification yourself if requested.")
        print("Do NOT enter your password into this Python script.")
        print()

        input("After login is complete, press ENTER here...")
        print()

        if not await safety_check(page):
            return False

    print("Session ready.")
    print()
    return True


# ============================================================
# COLLECT POST
# ============================================================

async def collect_post(page, username, post_url, post_number):
    safe_user = safe_filename(username)
    filename_base = f"{safe_user}_post_{post_number}"

    print(f"      Post {post_number}: {post_url}")

    try:
        await page.goto(
            post_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        await page.wait_for_timeout(
            int(PAGE_WAIT_SECONDS * 1000)
        )

        if not await safety_check(page):
            return None, False

        html_path = await save_html(
            page,
            filename_base + ".html"
        )

        screenshot_path = await save_screenshot(
            page,
            filename_base + ".png"
        )

        # Meta description.
        meta_description = ""

        try:
            element = page.locator(
                'meta[name="description"]'
            )

            if await element.count() > 0:
                meta_description = (
                    await element.get_attribute("content") or ""
                )
        except Exception:
            pass

        # OpenGraph description.
        og_description = ""

        try:
            element = page.locator(
                'meta[property="og:description"]'
            )

            if await element.count() > 0:
                og_description = (
                    await element.get_attribute("content") or ""
                )
        except Exception:
            pass

        combined_text = meta_description + " " + og_description

        # Likes.
        likes = extract_metric(
            combined_text,
            [
                r"([\d,.]+)\s+likes?",
                r"([\d,.]+)\s+like",
            ]
        )

        # Comments.
        comments = extract_metric(
            combined_text,
            [
                r"([\d,.]+)\s+comments?",
                r"([\d,.]+)\s+comment",
            ]
        )

        post_data = {
            "username": username,
            "post_url": post_url,
            "likes": likes,
            "comments": comments,
            "meta_description": meta_description,
            "og_description": og_description,
            "html_file": html_path,
            "screenshot_file": screenshot_path,
            "collected_at": timestamp(),
        }

        json_path = POST_DIR / f"{filename_base}.json"

        json_path.write_text(
            json.dumps(
                post_data,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return post_data, True

    except Exception as e:
        print(f"      ERROR collecting post: {e}")
        return None, True


# ============================================================
# COLLECT PROFILE
# ============================================================

async def collect_profile(page, username):
    safe_user = safe_filename(username)

    print()
    print("=" * 70)
    print(f"ACCOUNT: @{username}")
    print("=" * 70)

    profile_url = f"https://www.instagram.com/{username}/"

    try:
        await page.goto(
            profile_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        await page.wait_for_timeout(
            int(PAGE_WAIT_SECONDS * 1000)
        )

    except Exception as e:
        print(f"Could not open @{username}: {e}")
        return None, True

    # Safety check.
    if not await safety_check(page):
        return None, False

    # Save profile HTML.
    html_path = await save_html(
        page,
        f"{safe_user}_profile.html"
    )

    # Save screenshot.
    screenshot_path = await save_screenshot(
        page,
        f"{safe_user}_profile.png"
    )

    # Page title.
    try:
        title = await page.title()
    except Exception:
        title = ""

    # Meta description.
    meta_description = ""

    try:
        element = page.locator('meta[name="description"]')

        if await element.count() > 0:
            meta_description = (
                await element.get_attribute("content") or ""
            )
    except Exception:
        pass

    # Profile metrics.
    followers = extract_metric(
        meta_description,
        [
            r"([\d,.]+[KMB]?)\s+Followers",
            r"([\d,.]+)\s+followers",
        ]
    )

    following = extract_metric(
        meta_description,
        [
            r"([\d,.]+[KMB]?)\s+Following",
            r"([\d,.]+)\s+following",
        ]
    )

    posts_count = extract_metric(
        meta_description,
        [
            r"([\d,.]+[KMB]?)\s+Posts",
            r"([\d,.]+[KMB]?)\s+posts",
        ]
    )

    # Find post/reel links.
    post_links = []

    try:
        links = await page.locator(
            'a[href*="/p/"], a[href*="/reel/"]'
        ).evaluate_all(
            """
            elements => elements.map(e => e.href)
            """
        )

        seen = set()

        for link in links:
            if link not in seen:
                seen.add(link)
                post_links.append(link)

    except Exception as e:
        print(f"Could not find post links: {e}")

    post_links = post_links[:MAX_POSTS_PER_ACCOUNT]

    print()
    print(f"Followers: {followers}")
    print(f"Following: {following}")
    print(f"Posts: {posts_count}")
    print(f"Posts/reels selected: {len(post_links)}")

    # Collect posts.
    collected_posts = []

    for index, post_url in enumerate(post_links, start=1):
        post_data, should_continue = await collect_post(
            page,
            username,
            post_url,
            index
        )

        if not should_continue:
            return None, False

        if post_data:
            collected_posts.append(post_data)

        await page.wait_for_timeout(
            int(PAGE_WAIT_SECONDS * 1000)
        )

    # Profile data.
    profile_data = {
        "username": username,
        "profile_url": profile_url,
        "title": title,
        "followers": followers,
        "following": following,
        "posts_count": posts_count,
        "meta_description": meta_description,
        "posts_collected": len(collected_posts),
        "profile_html": html_path,
        "profile_screenshot": screenshot_path,
        "collected_at": timestamp(),
        "posts": collected_posts,
    }

    # Save profile JSON.
    json_path = PROFILE_DIR / f"{safe_user}.json"

    json_path.write_text(
        json.dumps(
            profile_data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(f"Finished @{username}")

    return profile_data, True


# ============================================================
# SAVE CSV
# ============================================================

def save_csv(profiles):
    if not profiles:
        return

    fieldnames = [
        "username",
        "profile_url",
        "followers",
        "following",
        "posts_count",
        "posts_collected",
        "title",
        "collected_at",
    ]

    try:
        with open(
            CSV_FILE,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            writer.writeheader()

            for profile in profiles:
                writer.writerow({
                    "username": profile.get("username", ""),
                    "profile_url": profile.get("profile_url", ""),
                    "followers": profile.get("followers", ""),
                    "following": profile.get("following", ""),
                    "posts_count": profile.get("posts_count", ""),
                    "posts_collected": profile.get("posts_collected", 0),
                    "title": profile.get("title", ""),
                    "collected_at": profile.get("collected_at", ""),
                })

        print(f"CSV saved: {CSV_FILE}")

    except Exception as e:
        print(f"Could not save CSV: {e}")


# ============================================================
# READ USERNAMES
# ============================================================

def read_usernames():
    if not USERNAME_FILE.exists():
        print(f"ERROR: {USERNAME_FILE} does not exist.")
        return []

    usernames = []

    for line in USERNAME_FILE.read_text(
        encoding="utf-8"
    ).splitlines():

        username = line.strip().lstrip("@")

        if not username:
            continue

        if username.startswith("#"):
            continue

        if username not in usernames:
            usernames.append(username)

    return usernames


# ============================================================
# MAIN
# ============================================================

async def main():
    usernames = read_usernames()

    if not usernames:
        print("No usernames found in usernames.txt")
        return

    # Limit this run to MAX_ACCOUNTS usernames.
    usernames = usernames[:MAX_ACCOUNTS]

    print()
    print("=" * 70)
    print("ROIlytics Instagram Collector")
    print("=" * 70)
    print(f"Accounts this run: {len(usernames)}")
    print(f"Maximum posts/account: {MAX_POSTS_PER_ACCOUNT}")
    print(
        "Maximum possible posts this run: "
        f"{len(usernames) * MAX_POSTS_PER_ACCOUNT}"
    )

    print()
    print("Safety mode:")
    print("  - Visible Chromium")
    print("  - Manual login")
    print("  - Persistent local session")
    print("  - No password automation")
    print("  - No CAPTCHA bypass")
    print("  - No stealth/anti-detection")
    print("  - No proxy rotation")
    print("  - Stops on security warnings")
    print()

    profiles = []

    async with async_playwright() as p:
        # Persistent browser.
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE),
            headless=False,
            viewport={
                "width": 1440,
                "height": 900,
            },
            slow_mo=50,
        )

        try:
            page = await context.new_page()

            # Prepare session.
            ready = await prepare_session(page)

            if not ready:
                return

            # Process accounts sequentially.
            for account_number, username in enumerate(
                usernames,
                start=1
            ):
                print()
                print(
                    f"ACCOUNT {account_number}/{len(usernames)}"
                )

                profile, should_continue = await collect_profile(
                    page,
                    username
                )

                if not should_continue:
                    print()
                    print(
                        "Collection stopped because "
                        "a safety condition was detected."
                    )
                    break

                if profile:
                    profiles.append(profile)

                    # FIXED: Correct indentation.
                    # Save the CSV after each successful account.
                    save_csv(profiles)

                # Pause before the next account.
                if account_number < len(usernames):
                    print()
                    print("Waiting before next account...")

                    await page.wait_for_timeout(
                        int(PAGE_WAIT_SECONDS * 2000)
                    )

        finally:
            await context.close()

    # Final CSV save.
    save_csv(profiles)

    # Final summary.
    print()
    print("=" * 70)
    print("COLLECTION FINISHED")
    print("=" * 70)
    print(
        f"Accounts successfully collected: "
        f"{len(profiles)}/{len(usernames)}"
    )
    print(f"Data directory: {DATA_DIR}")
    print(f"CSV: {CSV_FILE}")
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print()
        print("Collection stopped by user.")

    except Exception as e:
        print()
        print("=" * 70)
        print("UNEXPECTED ERROR")
        print("=" * 70)
        print(e)
        print("=" * 70)
