# Instagram Collector (Playwright)

A Python scraper that uses **Playwright with Chromium** to collect public Instagram profile data. It was built as the data-collection stage of **ROIlytics**, an influencer ROI prediction project.

## What it collects

For each public profile in the username list:

- Username, full name and bio
- Followers, following and post count
- Likes and comments on recent posts (used to calculate average likes, average comments and engagement rate)
- Verified status and profile URL

**Engagement rate** = (average likes + average comments) / followers

## How it works

1. Reads the target usernames from `usernames.txt` (one per line).
2. Launches Chromium through Playwright.
3. Opens each public profile and reads the visible stats.
4. Waits between profiles to avoid sending too many requests.
5. Saves the results as JSON/CSV in the `data/` folder.

## Project structure

```
instagram_collector_scraping/
├── instagram_collector.py   # Main scraper
├── usernames.txt            # List of usernames to scrape
├── requirements.txt         # Python dependencies
├── .gitignore               # Keeps secrets and local data out of Git
└── README.md
```

## Requirements

- Python 3.9 or newer
- Google Chromium (installed by Playwright)

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/drishtimore/instagram_collector_scraping.git
cd instagram_collector_scraping

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install the Chromium browser for Playwright
playwright install chromium
```

## Usage

1. Add the public usernames you want to collect to `usernames.txt`, one per line.
2. Run the collector:

```bash
python instagram_collector.py
```

3. The collected data is saved in the `data/` folder.

## Notes and limitations

- Works only for **public** profiles.
- Instagram may change its page layout or show login checks, which can break the scraper.
- Requests are delayed on purpose to reduce the chance of being blocked.
- Instagram does not provide ad spend or revenue, so ROI labels need other data sources.

## Responsible use

This project is for **educational and academic purposes**. Only collect public data, respect Instagram's Terms of Use and rate limits, and do not share personal data of individuals.

## Part of ROIlytics

This collector supplies real creator data (followers, posts, likes, comments) to the ROIlytics machine learning pipeline, which predicts campaign ROI and ranks influencers using a Fit Score.

## Author

Drishti More
