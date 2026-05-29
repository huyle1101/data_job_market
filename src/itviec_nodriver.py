import nodriver as uc
import asyncio
import json
import os
# os.chdir("playwright")
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta
import random
import numpy as np
import time
script_start_time = time.time()
import logging
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

ITVIEC_EMAIL = os.getenv('ITVIEC_EMAIL')
ITVIEC_PASSWORD = os.getenv('ITVIEC_PASSWORD')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # get project root dir

OUTPUT_DIR = os.path.join(BASE_DIR, "test/itviec/raw_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "itviec_test_data.jsonl")

LOG_DIR = os.path.join(BASE_DIR, "test/itviec/logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"itviec_{timestamp}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)
log = logging.getLogger()


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

'''
async --> function A can be paused
await --> tells function B (dependent on function A) to wait till function A is finished to start running
gather --> runs multiple async functions in parrallel
'''


async def human_sleep(min_s=1.0, max_s=4.0):
    mean = (min_s + max_s) / 2
    std  = (max_s - min_s) / 6
    secs = float(np.clip(np.random.normal(mean, std), min_s, max_s))
    await asyncio.sleep(secs)

# wait for clouflare verification to pass and do nothing else since nodriver looks like a real human
async def wait_for_cloudflare(tab, timeout=30):
    log.info("Waiting for Cloudflare to clear")
    for _ in range(timeout):
        title = await tab.get_content()
        if "Just a moment" not in title and "Verify you are human" not in title:
            log.info("Cloudflare cleared!")
            return True
        await asyncio.sleep(1)
    log.info("Cloudflare challenge timed out.")
    return False

async def dismiss_popup(tab): # dismiss cv popup
    try:
        remind_later = await tab.find("Remind me later", timeout=5)
        if remind_later:
            await remind_later.click()
            log.info("Dismissed popup")
            await asyncio.sleep(1)
    except Exception:
        pass  # no popup, continue normally


async def wait_for_preview(tab, timeout=10): # wait for the job data panel to fully show up before scraping
    for _ in range(timeout):
        title = await tab.select('.preview-job-wrapper h2') # wait here till tab.select('.preview-job-wrapper h2') done then store in title
        if title and title.text and title.text.strip():
            return True
        await asyncio.sleep(1) # sleep for 1 sec, other async functions can run during this time 
    return False


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

    # click on the right submit button
    submit_btn = await tab.find("Sign In with Email")
    await submit_btn.click()

    await tab.wait()
    # await dismiss_password_popup(tab)
    await dismiss_popup(tab)
    log.info("Logged in. Currently at: " + tab.url)


async def scrape_job(tab):
    # help function to return a list of scraped data
    async def texts(selector):
        try:
            els = await tab.select_all(selector)
            if not els:
                return []
            return [e.text for e in els]
        except Exception:
            return []

    # help function to return a single string of scraped data
    async def text(selector):
        try:
            el = await tab.select(selector)
            if el is None:
                return None
            return el.text.strip() if el.text else None
        except Exception:
            return None

    time_els = await tab.select_all('.preview-job-overview .d-flex.flex-column > div span')
    try:
        time_text = time_els[-1].text.strip() if time_els else "0 days ago"
        amount = int(time_text.split()[0])
        if "hour" in time_text:
            posted_date = (current_date - timedelta(hours=amount)).strftime("%d/%m/%Y")
        else:
            posted_date = (current_date - timedelta(days=amount)).strftime("%d/%m/%Y")
    except Exception:
        posted_date = current_date.strftime("%d/%m/%Y")

    benefits_1 = await texts('.reasons-join-us + ul li')
    benefits_2 = await texts('section.job-why-love-working div.paragraph li')

    job_url = await tab.evaluate(
        "document.querySelector('.preview-job-wrapper a[href*=\"/it-jobs/\"]')?.href || window.location.href"
    )

    job_description = await tab.evaluate("""
    (() => {
        const el = document.querySelector('section.job-description div.paragraph');
        if (!el) return null;
        return el.innerText.trim();
    })()
""")

    job_requirements = await tab.evaluate("""
        (() => {
            const el = document.querySelector('section.job-experiences div.paragraph');
            if (!el) return null;
            return el.innerText.trim();
        })()
    """)

    return {
        "url":              job_url,
        "title":            await text('.preview-job-wrapper h2'),
        "company_name":     await text('.preview-job-wrapper a[href*="/companies/"]'),
        "locations":        await texts('.preview-job-overview div:has(a[href*="google.com/maps"]) span'),
        "posted_date":      posted_date, # fix
        "due_date":         None,
        "salary":           await text('.salary span'),
        "experience":       None,
        "work_type":        await text('.preview-header-item span.ms-1'),
        "skill_list":       await texts('.preview-job-wrapper a.itag'),
        "job_category":     await texts('xpath=//div[text()="Job Domain:"]/..//div[contains(@class,"itag")]'),
        "benefits":         benefits_1 + benefits_2,
        "job_description":  job_description, # fix
        "job_requirements": job_requirements, # fix
    }


async def main():
    browser = await uc.start(
        headless=False,
        browser_args=[
            "--disable-blink-features=AutomationControlled", # hide bot properties
            "--password-store=basic", 
            "--disable-save-password-bubble", # disable password store popup
            "--disable-features=PasswordManagerOnboarding,AutofillServerCommunication",
            "--disable-features=PasswordLeakDetection,PasswordManagerOnboarding,AutofillEnableAccountWalletStorage",
            "--disable-features=PasswordManagerOnboarding,AutofillEnableAccountWalletStorage,PasswordImport",
        ],
        lang="en-US",
    )

    await login(browser)
    tab = browser.main_tab

    for i, keyword in enumerate(KEYWORDS):
        keyword_start_time = time.time()
        # long break every 10 keywords
        if i > 0 and i % 10 == 0:
            wait = random.uniform(30, 90)
            log.info(f"Long break: {wait:.0f}s")
            await asyncio.sleep(wait)

        log.info(f"Searching: {keyword}")
        await tab.get(f"https://itviec.com/it-jobs/{keyword}")
        await wait_for_cloudflare(tab)
        await human_sleep(2, 4)

        while True:
            num_job_cards = await tab.select_all('.job-card[data-action*="job-selection#select"]')
            page_start_time = time.time()
            log.info(f"Found {len(num_job_cards)} jobs")

            for idx, card in enumerate(num_job_cards):
                log.info(f"Scraping job {idx + 1}/{len(num_job_cards)}...")


                await card.scroll_into_view()
                await asyncio.sleep(0.5)
                # click card — loads detail in right panel
                await card.click()
                await human_sleep(1.5, 3.0)
                await dismiss_popup(tab)

                # wait for preview panel to fully load
                loaded = await wait_for_preview(tab)
                if not loaded:
                    log.info("Preview panel did not load, skipping...")
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
                    log.info(f"Saved: {job_data['title']} @ {job_data['company_name']}")
                except Exception as e:
                    log.info(f"Error scraping job: {e}")

                await human_sleep(1.0, 2.5)

            log.info(f"One page done for keyword: {keyword} in {time.time()-page_start_time:.1f}s")
            # check for next page
            next_btn = await tab.select('a[rel="next"]')
            if next_btn:
                log.info("Going to next page...")
                await next_btn.click()
                await human_sleep(2, 5)
                await wait_for_cloudflare(tab)
            else:
                log.info("No more pages for this keyword.")
                break
        log.info(f"Keyword '{keyword}' done in {time.time() - keyword_start_time:.1f}s")
        
    log.info(f"Script finished in {time.time() - script_start_time:.1f}s")
    browser.stop()

# use uc.loop() to run async functions since Python doesn't support async
uc.loop().run_until_complete(main())