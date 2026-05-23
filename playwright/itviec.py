import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import json


async def login():
    
    async with async_playwright() as p:
        # open browser, headless=True = don't turn bring up the browser
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=r"C:/Users/ADMIN/AppData/playright_profile",
            channel="chrome",  # use real Chrome to prevent being prevented
            headless=False,
            args=["--disable-blink-features=AutomationControlled"], # hide bot properties
        ) 
        page = await browser.new_page()
        
        
        # go to login page
        await page.goto("https://itviec.com/sign_in")
        await page.wait_for_selector("#user_email", timeout=30000)
        
        # fill login information
        await page.fill("#user_email", "wtester312@gmail.com")
        await page.fill("#user_password", "Iamtester123@")
        
        
        # click login button
        await page.click("button[type='submit']")
        
        # wait for login to be complete
        await page.wait_for_load_state("networkidle")
        
        print("Currently at:", page.url)
        
        # get cookies so don't have to login next time - just run this first time
        cookies = await page.context.cookies()
        with open("./itviec_cookies.json", "w") as f:
            json.dump(cookies, f)
        print("Cookies saved")
        
        await browser.close()

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        # context = environment
        context = await browser.new_context()
        
        with open("cookies.json", "r") as f:
            cookies = json.load(f)
        
        await context.add_cookies(cookies)

        page = await browser.new_page()

        await Stealth().apply_stealth_async(page)

        await page.goto("https://itviec.com/it-jobs/data-analysis")
        await page.wait_for_timeout(100000)
        
        print(await page.title())
        
        await browser.close()

# asyncio.run(test())
# asyncio.run(login())

'''
def run(playwright):
    browser = playwright.chromium.launch()
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.topcv.vn/")
    scraped_urls = set()

    # lấy số trang
    l = page.locator(".slick-pagination").inner_text().split()
    num_pages = int(l[2])
    # res = []
    for count in range(10,num_pages):
        # try:
        page.wait_for_selector(".col-title.cvo-flex-grow a")
        job_urls = page.locator("div.col-title h3 > a.title").evaluate_all("list => list.map(element => element.href)")
        for i in range(len(job_urls)): # duyệt qua 12 job trong 1 trang
            try:
                job_data = {}
                url = job_urls[i]
                # check job đó đã được cào hay chưa
                if url in scraped_urls:
                    continue
                scraped_urls.add(url)
                # đi vào từng job
                new_tab = context.new_page()
                new_tab.goto(job_urls[i])
                new_tab.wait_for_load_state()

                texts = new_tab.locator('.job-description__item--content').all_inner_texts()
                job_data = {
                    'url':url,
                    'Công việc': new_tab.locator("h1").inner_text(),
                    'Công ty': new_tab.locator(".company-name-label a.name").inner_text(),
                    'Mức lương': new_tab.locator(".section-salary").locator(".job-detail__info--section-content-value").inner_text(),
                    'Địa điểm làm việc (đã được cập nhật theo Danh mục Hành chính mới)' : new_tab.locator(".job-description__item", has_text="Địa điểm làm việc").all_inner_texts(),
                    'Kinh nghiệm': new_tab.locator("#job-detail-info-experience").locator(".job-detail__info--section-content-value").inner_text(),
                    'Mô tả công việc': texts[0],
                    'Yêu cầu ứng viên': texts[1],
                    'Quyền lợi': texts[2],
                    'Thời gian làm việc':new_tab.locator(".job-description__item", has_text="Thời gian làm việc").all_inner_texts(),
                    'Hạn nộp hồ sơ':new_tab.locator(".job-detail__information-detail--actions-label").inner_text(),
                    'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                # res.append(job_data) 
                # lưu data khi cào xong 1 trang - 12 job
                with open("result.json", "a", encoding="utf-8") as f:
                    line = json.dumps(job_data, ensure_ascii=False)
                    f.write(line + "\n")
                    f.flush()
                new_tab.close()

                # đi sang trang mới
                try:
                    page.click("span.btn-feature-jobs-next.btn-slick-arrow")
                except:
                    break
            except:
                continue
        # except:
        #     continue
    context.close()
    browser.close()

with sync_playwright() as playwright:
    run(playwright)




'''