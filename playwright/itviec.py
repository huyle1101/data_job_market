import asyncio
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import json
import os
os.chdir("playwright")
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta
current_date = datetime.now()
import random

ITVIEC_EMAIL=os.getenv('ITVIEC_EMAIL')
ITVIEC_PASSWORD=os.getenv('ITVIEC_PASSWORD')
OUTPUT_FILE = "itviec_test_data.json"

# search keywords
KEYWORDS = [
        # Data Core
        "data",
        "data-analyst",
        "data-engineer",
        "data-scientist",
        "data-science",
        "data-analytics",
        "data-architect",
        "data-modeler",
        "data-warehouse",
        "data-governance",
        "data-quality",
        "big-data",

        # BI
        "business-intelligence",
        "analytics-engineer",
        "bi-developer",
        "power-bi",
        "tableau",

        # Engineering / Database
        "etl",
        "database-administrator",
        "sql",

        # ML / AI Classic
        "machine-learning",
        "deep-learning",
        "mlops",
        "ai-engineer",
        "ai-developer",
        "ai-researcher",
        "artificial-intelligence",
        "computer-vision",
        "nlp",

        # GenAI / Modern AI
        "generative-ai",
        "gen-ai",
        "llm",
        "prompt-engineer",
        "chatbot",

        # Data Core
        "intern-data",
        "intern-data-analyst",
        "intern-data-engineer",
        "intern-data-scientist",
        "intern-data-science",
        "intern-data-analytics",
        "intern-data-architect",
        "intern-data-modeler",
        "intern-data-warehouse",
        "intern-data-governance",
        "intern-data-quality",
        "intern-big-data",

        # BI
        "intern-business-intelligence",
        "intern-analytics-engineer",
        "intern-bi-developer",
        "intern-power-bi",
        "intern-tableau",

        # Engineering / Database
        "intern-etl",
        "intern-database-administrator",
        "intern-sql",

        # ML / AI Classic
        "intern-machine-learning",
        "intern-deep-learning",
        "intern-mlops",
        "intern-ai-engineer",
        "intern-ai-developer",
        "intern-ai-researcher",
        "intern-artificial-intelligence",
        "intern-computer-vision",
        "intern-nlp",

        # GenAI / Modern AI
        "intern-generative-ai",
        "intern-gen-ai",
        "intern-llm",
        "intern-prompt-engineer",
        "intern-chatbot",
    ]

# sleep for a random amount of time
def random_sleep(page):
    sleep_time = random.uniform(1.5, 4) * 1000 # ms * 1000 = s
    page.wait_for_timeout(sleep_time)

def login(playwright):
    browser = playwright.chromium.launch_persistent_context(
        user_data_dir=r"C:/Users/ADMIN/AppData/playwright_profile",
        channel="chrome",
        headless=False,
        args=["--disable-blink-features=AutomationControlled"], # hide bot properties
    )
    page = browser.new_page()
 
    page.goto("https://itviec.com/sign_in")
    page.wait_for_selector("#user_email", timeout=30000)
 
    page.fill("#user_email", ITVIEC_EMAIL)
    page.fill("#user_password", ITVIEC_PASSWORD)
    random_sleep(page)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
 
    print("Currently at:", page.url)
 
    # cookies = browser.cookies()
    # with open("./itviec_cookies.json", "w") as f:
    #     json.dump(cookies, f)
    # print("Cookies saved")
 
    browser.close()

# scrape each job
def scrape_job(page):
    location_selector = '.preview-job-overview div:has(a[href*="google.com/maps"]) span'
    time_selector = '.preview-job-overview .d-flex.flex-column > div'
    day_past = int(page.locator(time_selector).last.locator('span').inner_text().split()[0])

    benefits_1 = page.locator('.reasons-join-us + ul li').all_inner_texts()
    benefits_2 = page.locator('section.job-why-love-working div.paragraph li').all_inner_texts()
    return {
        "url": page.url,
        "title": page.locator('.preview-job-wrapper h2').inner_text(),
        "company_name": page.locator('a[href*="/companies/"]').first.inner_text(),
        "locations": page.locator(location_selector).all_inner_texts(),
        "posted_date": (current_date - timedelta(days=day_past)).strftime("%d/%m/%Y"),
        "due_date": None,
        "salary": page.locator('.salary span').inner_text(),
        "experience": None,
        "work_type": page.locator('.preview-header-item span.ms-1').first.inner_text(),
        "skill_list": page.locator('.preview-job-wrapper a.itag').all_inner_texts(),
        "job_category": page.locator('xpath=//div[text()="Job Domain:"]/..//div[contains(@class, "itag")]').all_inner_texts(),
        "benefits": benefits_1 + benefits_2,
        "job_description": page.locator('section.job-description div.paragraph').inner_text(),
        "job_requirements": page.locator('section.job-experiences div.paragraph').inner_text()
    }

def main(playwright):
    browser = playwright.chromium.launch_persistent_context(
        user_data_dir=r"C:/Users/ADMIN/AppData/playwright_profile",
        channel="chrome",
        headless=False,
        args=["--disable-blink-features=AutomationControlled"], # hide bot properties
    )
    context = browser.new_context()
 
    with open("itviec_cookies.json", "r") as f:
        cookies = json.load(f)
    context.add_cookies(cookies)
 
    page = context.new_page()

    for keyword in KEYWORDS:
        print(f"Searching for: {keyword}")
        search_url = f"https://itviec.com/it-jobs/{keyword}"
        page.goto(search_url)
        page.wait_for_load_state("networkidle")
        random_sleep(page)

        # keep looping until there is no more next page
        job_urls = page.locator('h3[data-search--job-selection-target="jobTitle"]').evaluate_all(
    "elements => elements.map(el => el.getAttribute('data-url'))"
)
        # scroll to the end, wait for 5s for the data to load and back to the top again
        page.keyboard.press('End')
        page.wait_for_timeout(5000)
        page.keyboard.press('Home')
        while 1:
            for i in range(len(job_urls)):
                # click on job link
                job_urls[i].click()
                random_sleep(page)
                job_data = scrape_job(page)
                with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(job_data, ensure_ascii=False) + "\n")
                    f.flush()
                
            # go to next page
            next_page = page.locator('a[rel="next"]')
            if next_page.count() > 0: # 
                next_page.click()
                random_sleep(page)
                page.wait_for_load_state("networkidle")
            else:
                break # no more page
 
    context.close()
    browser.close()

# go into stealth mode to avoid human verification
with Stealth().use_sync(sync_playwright()) as playwright:
    login(playwright)
    main(playwright)