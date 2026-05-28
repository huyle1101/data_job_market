import nodriver as uc
import asyncio
import json
import os
os.chdir("playwright")
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta
import random
import numpy as np

ITVIEC_EMAIL = os.getenv('ITVIEC_EMAIL')
ITVIEC_PASSWORD = os.getenv('ITVIEC_PASSWORD')
OUTPUT_FILE = "itviec_test_data.jsonl"

KEYWORDS = [
    "data", "data-analyst", "data-engineer", "data-scientist",
    "data-science", "data-analytics", "data-architect", "data-modeler",
    "data-warehouse", "data-governance", "data-quality", "big-data",
    "business-intelligence", "analytics-engineer", "bi-developer",
    "power-bi", "tableau", "etl", "database-administrator", "sql",
    "machine-learning", "deep-learning", "mlops", "ai-engineer",
    "ai-developer", "ai-researcher", "artificial-intelligence",
    "computer-vision", "nlp", "generative-ai", "gen-ai", "llm",
    "prompt-engineer", "chatbot",
    # intern versions
    "intern-data", "intern-data-analyst", "intern-data-engineer",
    "intern-data-scientist", "intern-machine-learning", "intern-deep-learning",
    "intern-ai-engineer", "intern-nlp", "intern-generative-ai", "intern-llm",
]

current_date = datetime.now()

# ── helpers ──────────────────────────────────────────────────────────────────

async def human_sleep(min_s=1.0, max_s=4.0):
    mean = (min_s + max_s) / 2
    std  = (max_s - min_s) / 6
    secs = float(np.clip(np.random.normal(mean, std), min_s, max_s))
    await asyncio.sleep(secs)

async def wait_for_cloudflare(tab, timeout=30):
    """Wait until Cloudflare challenge disappears."""
    print("  Waiting for Cloudflare to clear...")
    for _ in range(timeout):
        title = await tab.get_content()
        if "Just a moment" not in title and "Verify you are human" not in title:
            print("  Cloudflare cleared!")
            return True
        await asyncio.sleep(1)
    print("  Cloudflare challenge timed out.")
    return False

async def dismiss_popup(tab):
    try:
        remind_later = await tab.find("Remind me later", timeout=5)
        if remind_later:
            await remind_later.click()
            print("  Dismissed CV popup")
            await asyncio.sleep(1)
    except Exception:
        pass  # no popup, continue normally

async def wait_for_preview(tab, timeout=10):
    for _ in range(timeout):
        title = await tab.select('.preview-job-wrapper h2')
        if title and title.text and title.text.strip():
            return True
        await asyncio.sleep(1)
    return False

# ── login ─────────────────────────────────────────────────────────────────────

async def login(browser):
    tab = await browser.get("https://itviec.com/sign_in")
    await wait_for_cloudflare(tab)
    await human_sleep(2, 4)

    email_input = await tab.find("#user_email")
    await email_input.clear_input()
    await email_input.send_keys(ITVIEC_EMAIL)

    password_input = await tab.find("#user_password")
    await password_input.clear_input()
    await password_input.send_keys(ITVIEC_PASSWORD)

    await human_sleep(1, 3)

    # ✅ target the exact button by its visible text
    submit_btn = await tab.find("Sign In with Email")
    await submit_btn.click()

    await tab.wait()
    await dismiss_popup(tab)
    print("Logged in. Currently at:", tab.url)



# ── scrape a single job page ──────────────────────────────────────────────────

async def scrape_job(tab):
    async def texts(selector):
        try:
            els = await tab.select_all(selector)
            if not els:
                return []
            return [e.text for e in els]          # ✅ .text not get_text()
        except Exception:
            return []

    async def text(selector):
        try:
            el = await tab.select(selector)
            if el is None:
                return None
            return el.text.strip() if el.text else None  # ✅ .text not get_text()
        except Exception:
            return None

    time_els = await tab.select_all('.preview-job-overview .d-flex.flex-column > div span')
    try:
        day_past = int(time_els[-1].text.split()[0]) if time_els else 0  # ✅
    except Exception:
        day_past = 0

    benefits_1 = await texts('.reasons-join-us + ul li')
    benefits_2 = await texts('section.job-why-love-working div.paragraph li')

    job_url = await tab.evaluate(
        "document.querySelector('.preview-job-wrapper a[href*=\"/it-jobs/\"]')?.href || window.location.href"
    )

    return {
        "url":              job_url,
        "title":            await text('.preview-job-wrapper h2'),
        "company_name":     await text('.preview-job-wrapper a[href*="/companies/"]'),
        "locations":        await texts('.preview-job-overview div:has(a[href*="google.com/maps"]) span'),
        "posted_date":      (current_date - timedelta(days=day_past)).strftime("%d/%m/%Y"),
        "due_date":         None,
        "salary":           await text('.salary span'),
        "experience":       None,
        "work_type":        await text('.preview-header-item span.ms-1'),
        "skill_list":       await texts('.preview-job-wrapper a.itag'),
        "job_category":     await texts('xpath=//div[text()="Job Domain:"]/..//div[contains(@class,"itag")]'),
        "benefits":         benefits_1 + benefits_2,
        "job_description":  await text('section.job-description div.paragraph'),
        "job_requirements": await text('section.job-experiences div.paragraph'),
    }


async def main():
    browser = await uc.start(
        headless=False,
        browser_args=[
            "--disable-blink-features=AutomationControlled",
            "--password-store=basic",
            "--disable-save-password-bubble",
        ],
        lang="en-US",
    )

    await login(browser)
    tab = browser.main_tab

    for i, keyword in enumerate(KEYWORDS):
        # long break every 10 keywords
        if i > 0 and i % 10 == 0:
            wait = random.uniform(30, 90)
            print(f"  Long break: {wait:.0f}s")
            await asyncio.sleep(wait)

        print(f"\nSearching: {keyword}")
        await tab.get(f"https://itviec.com/it-jobs/{keyword}")
        await wait_for_cloudflare(tab)
        await human_sleep(2, 4)

        while True:
            # collect all job cards on current page
            job_cards = await tab.select_all('.job-card[data-action*="job-selection#select"]')
            print(f"  Found {len(job_cards)} jobs")

            for idx, card in enumerate(job_cards):
                print(f"  Scraping job {idx + 1}/{len(job_cards)}...")

                # click card — loads detail in right panel
                await card.click()
                await human_sleep(1.5, 3.0)
                await dismiss_popup(tab)

                # wait for preview panel to fully load
                loaded = await wait_for_preview(tab)
                if not loaded:
                    print("  Preview panel did not load, skipping...")
                    continue

                # scroll the preview panel to bottom (human-like + loads lazy content)
                await tab.evaluate("""
                    const panel = document.querySelector('.preview-job-wrapper');
                    if (panel) panel.scrollTo({ top: panel.scrollHeight, behavior: 'smooth' });
                """)
                await asyncio.sleep(2)
                await tab.evaluate("""
                    const panel = document.querySelector('.preview-job-wrapper');
                    if (panel) panel.scrollTo({ top: 0, behavior: 'smooth' });
                """)

                try:
                    job_data = await scrape_job(tab)
                    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                        f.write(json.dumps(job_data, ensure_ascii=False) + "\n")
                        f.flush()
                    print(f"  Saved: {job_data['title']} @ {job_data['company_name']}")
                except Exception as e:
                    print(f"  Error scraping job: {e}")

                await human_sleep(1.0, 2.5)

            # check for next page
            next_btn = await tab.select('a[rel="next"]')
            if next_btn:
                print("  Going to next page...")
                await next_btn.click()
                await human_sleep(2, 5)
                await wait_for_cloudflare(tab)
            else:
                print("  No more pages for this keyword.")
                break

    browser.stop()


# uc.loop().run_until_complete(main())

# ── entry point ───────────────────────────────────────────────────────────────

uc.loop().run_until_complete(main())