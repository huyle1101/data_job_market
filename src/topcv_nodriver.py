import nodriver as uc
import asyncio
import json
import os
import random
import time
import logging
import math
import numpy as np
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
script_start_time = time.time()

OUTPUT_DIR = os.path.join("f:/data_job_market_repo/test", "topcv/raw_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"topcv_test_data_{timestamp}.jsonl")

LOG_DIR = os.path.join("f:/data_job_market_repo/test", "topcv/logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"topcv_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
log = logging.getLogger()

KEYWORDS = [
    # Data Core
    "data-analyst", "data", "data-engineer", "data-scientist",
    "data-science", "data-analytics", "data-architect", "data-modeler",
    "data-warehouse", "data-governance", "data-quality", "big-data",
    # BI
    "business-intelligence", "analytics-engineer", "bi-developer",
    "power-bi", "tableau",
    # Engineering / Database
    "etl", "database-administrator", "sql",
    # ML / AI Classic
    "machine-learning", "deep-learning", "mlops", "ai-engineer",
    "ai-developer", "ai-researcher", "artificial-intelligence",
    "computer-vision", "nlp",
    # GenAI / Modern AI
    "generative-ai", "gen-ai", "llm", "prompt-engineer", "chatbot",
    # intern versions
    "intern-data", "intern-data-analyst", "intern-data-engineer",
    "intern-data-scientist", "intern-data-science", "intern-data-analytics",
    "intern-data-architect", "intern-data-modeler", "intern-data-warehouse",
    "intern-data-governance", "intern-data-quality", "intern-big-data",
    "intern-business-intelligence", "intern-analytics-engineer",
    "intern-bi-developer", "intern-power-bi", "intern-tableau",
    "intern-etl", "intern-database-administrator", "intern-sql",
    "intern-machine-learning", "intern-deep-learning", "intern-mlops",
    "intern-ai-engineer", "intern-ai-developer", "intern-ai-researcher",
    "intern-artificial-intelligence", "intern-computer-vision", "intern-nlp",
    "intern-generative-ai", "intern-gen-ai", "intern-llm",
    "intern-prompt-engineer", "intern-chatbot",
]

# --- seen URLs để tránh scrape trùng ---
# seen_urls = set()


def clean_url(url: str) -> str:
    """
    Bỏ toàn bộ tracking query params (ta_source, sr_id, ...) khỏi URL TopCV.
    Chỉ giữ lại path, tránh lỗi CDP -32602 khi các params có ký tự đặc biệt.
    """
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    # TopCV job detail URL chứa đủ thông tin trong path, không cần query string
    return urlunparse(parsed._replace(query="", fragment=""))


async def human_sleep(min_s=1.0, max_s=4.0):
    mean = (min_s + max_s) / 2
    std  = (max_s - min_s) / 6
    secs = float(np.clip(np.random.normal(mean, std), min_s, max_s))
    await asyncio.sleep(secs)


async def wait_for_cloudflare(tab, timeout=30):
    log.info("Waiting for Cloudflare to clear...")
    for _ in range(timeout):
        content = await tab.get_content()
        if "Just a moment" not in content and "Verify you are human" not in content:
            log.info("Cloudflare cleared!")
            return True
        await asyncio.sleep(1)
    log.warning("Cloudflare challenge timed out.")
    return False


async def dismiss_popup(tab):
    """
    Dismiss tất cả các loại popup của TopCV:
      1. Rating popup    – "Bạn thấy TopCV thế nào?" → bấm "Bỏ qua"
      2. CV upload popup – "Nhắc tôi sau" / "Bỏ qua"
      3. Cookie/consent  – nút "Đồng ý"
      4. Upsell          – "Không, cảm ơn" / "Đóng"
      5. Fallback        – bất kỳ nút × (close) nào còn lại trong overlay
    Chạy tối đa 2 lần để bắt các popup xuất hiện theo tầng.
    """
    # (text_to_find, log_label)
    DISMISS_TEXTS = [
        ("Bỏ qua",        "rating/skip popup"),
        ("Nhắc tôi sau",  "CV upload popup"),
        ("Đồng ý",        "cookie/consent popup"),
        ("Không, cảm ơn", "upsell popup"),
        ("Đóng",          "generic close popup"),
    ]

    for attempt in range(2):
        dismissed_any = False

        # --- 1. Text-based buttons ---
        for text, label in DISMISS_TEXTS:
            try:
                btn = await tab.find(text, timeout=3)
                if btn:
                    await btn.click()
                    log.info(f"Dismissed [{label}] (attempt {attempt+1})")
                    await asyncio.sleep(0.8)
                    dismissed_any = True
                    break   # sau mỗi click, restart vòng lặp attempt
            except Exception:
                continue

        # --- 2. Fallback: nút × / close-button trong modal/overlay ---
        if not dismissed_any:
            try:
                closed = await tab.evaluate("""
                    (() => {
                        const selectors = [
                            // TopCV "Lời mời cơ hội nghề nghiệp" popup (SVG × góc trên phải)
                            '.job-invitation-modal .close',
                            '.job-invitation-modal button.close',
                            '.modal-job-invitation .close',
                            '[class*="invitation"] .close',
                            '[class*="invitation"] button[class*="close"]',
                            // Generic Bootstrap / custom modal close
                            '.modal .btn-close',
                            '.modal button[aria-label="Close"]',
                            '.modal .close',
                            '.popup .btn-close',
                            '.popup button[aria-label="Close"]',
                            '.popup .close',
                            '[class*="modal"] button[class*="close"]',
                            '[class*="popup"] button[class*="close"]',
                            // Last resort: bất kỳ nút × visible nào trong overlay
                            'button.close:not([style*="display:none"])',
                        ];
                        for (const sel of selectors) {
                            const btn = document.querySelector(sel);
                            // chỉ click nếu element thực sự visible
                            if (btn && btn.offsetParent !== null) {
                                btn.click();
                                return sel;
                            }
                        }
                        return null;
                    })()
                """)
                if closed:
                    log.info(f"Dismissed fallback close button [{closed}] (attempt {attempt+1})")
                    await asyncio.sleep(0.8)
                    dismissed_any = True
            except Exception:
                pass

        # Nếu không dismiss được gì thêm, không cần thử lần 2
        if not dismissed_any:
            break


async def get_text(tab, selector):
    """Lấy text của một element, trả về None nếu không tìm thấy."""
    try:
        el = await tab.select(selector)
        if el is None:
            return None
        return el.text.strip() if el.text else None
    except Exception:
        return None


async def get_texts(tab, selector):
    """Lấy list text của nhiều elements."""
    try:
        els = await tab.select_all(selector)
        if not els:
            return []
        return [e.text.strip() for e in els if e.text and e.text.strip()]
    except Exception:
        return []


async def get_innertext(tab, js_selector):
    """Dùng JS evaluate để lấy innerText của element (cho nội dung có HTML phức tạp)."""
    try:
        result = await tab.evaluate(f"""
            (() => {{
                const el = document.querySelector('{js_selector}');
                if (!el) return null;
                return el.innerText.trim();
            }})()
        """)
        return result if result else None
    except Exception:
        return None


async def scrape_job_page(tab, url):
    """
    Scrape thông tin từ trang job detail của TopCV.

    Chiến lược (theo độ bền vững giảm dần):
      1. JSON-LD  – <script type="application/ld+json"> — không bao giờ thay đổi vì là
                    chuẩn SEO schema.org. Dùng cho: title, salary, location, YOE,
                    position, description, requirements, benefits, due_date, tags.
      2. Label-based DOM — tìm theo text label tiếng Việt (ít thay đổi hơn class).
                    Dùng cho: position, degree (không có trong JSON-LD).
      3. CSS selector fallback — chỉ dùng khi cả 2 trên miss.
    """
    from html.parser import HTMLParser

    # =========================================================================
    # Helper: strip HTML tags → plain text
    # =========================================================================
    class _StripHTML(HTMLParser):
        def __init__(self):
            super().__init__()
            self._parts = []
        def handle_data(self, data):
            self._parts.append(data)
        def get_text(self):
            return " ".join(p.strip() for p in self._parts if p.strip())

    def strip_html(html_str: str) -> str:
        if not html_str:
            return ""
        p = _StripHTML()
        p.feed(html_str)
        return p.get_text()

    # =========================================================================
    # 1. Đọc JSON-LD
    # =========================================================================
    ld_raw = await tab.evaluate("""
        (() => {
            const el = document.querySelector('script[type="application/ld+json"]');
            return el ? el.textContent : null;
        })()
    """)

    ld = {}
    if ld_raw:
        try:
            ld = json.loads(ld_raw)
        except Exception:
            log.warning(f"Failed to parse JSON-LD at {url}")

    # ---- job_title ----
    job_title = ld.get("title") or None

    # ---- salary_range ----
    try:
        salary_range = ld["baseSalary"]["value"]["value"]
    except (KeyError, TypeError):
        salary_range = None

    # ---- location ----
    try:
        addr = ld["jobLocation"]["address"]
        parts = [
            addr.get("streetAddress", ""),
            addr.get("addressLocality", ""),
            addr.get("addressRegion", ""),
        ]
        location = ", ".join(p for p in parts if p) or None
    except (KeyError, TypeError):
        location = None

    # ---- years_of_experience ----
    # JSON-LD lưu monthsOfExperience → chuyển sang năm (làm tròn lên)
    try:
        months = ld["experienceRequirements"]["monthsOfExperience"]
        years_of_experience = str(math.ceil(months / 12)) if months else None
    except (KeyError, TypeError):
        years_of_experience = None

    # ---- position (occupationalCategory) ----
    position = ld.get("occupationalCategory") or None

    # ---- description field trong JSON-LD chứa cả mô tả + yêu cầu + quyền lợi
    #      được wrap trong <h2> sections → tách ra
    # =========================================================================
    ld_description_html = ld.get("description", "")

    def extract_section(html: str, heading: str) -> str:
        """Lấy nội dung sau <h2>heading</h2> đến <h2> kế tiếp."""
        import re
        pattern = rf'<h2[^>]*>{re.escape(heading)}<\/h2>(.*?)(?=<h2|$)'
        m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        return strip_html(m.group(1)) if m else ""

    job_description  = extract_section(ld_description_html, "Mô tả công việc") or None
    job_requirements = extract_section(ld_description_html, "Yêu cầu ứng viên") or None

    # ---- benefits ----
    benefits_html = ld.get("jobBenefits", "")
    if not benefits_html:
        # một số layout nhét benefits vào description
        benefits_html = extract_section(ld_description_html, "Quyền lợi được hưởng")

    # parse từng <li> thành list
    import re as _re
    li_items = _re.findall(r'<li[^>]*>(.*?)<\/li>', benefits_html, _re.DOTALL)
    if li_items:
        benefits = [strip_html(li).strip() for li in li_items if strip_html(li).strip()]
    else:
        benefits = [strip_html(benefits_html)] if benefits_html else []

    # ---- general_information (skills tags) ----
    skills_str = ld.get("skills", "")
    general_information = [s.strip() for s in skills_str.split(",") if s.strip()] if skills_str else []
    # Fallback sang DOM tags nếu JSON-LD không có
    if not general_information:
        general_information = await get_texts(tab, '.job-tags__group-list-tag-scroll .item')

    # ---- due_date ----
    # validThrough: "2026-06-20T23:59:59+07:00" → "20/06/2026"
    valid_through = ld.get("validThrough", "")
    if valid_through:
        try:
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(valid_through)
            due_date = dt.strftime("%d/%m/%Y")
        except Exception:
            due_date = valid_through[:10]  # fallback: lấy YYYY-MM-DD
    else:
        due_date = None

    # =========================================================================
    # 2. Label-based DOM fallback cho những gì JSON-LD không có
    # =========================================================================
    async def get_by_label(label_text: str) -> str | None:
        """
        Tìm element chứa đúng label_text rồi trả về giá trị kề cạnh.
        Hoạt động với mọi layout vì dựa vào text, không phải class.
        """
        return await tab.evaluate(f"""
            (() => {{
                // Tìm tất cả text nodes khớp label
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_ELEMENT,
                    null
                );
                while (walker.nextNode()) {{
                    const el = walker.currentNode;
                    // chỉ lấy leaf-like nodes (ít children, text ngắn)
                    if (el.children.length <= 1 &&
                        el.innerText &&
                        el.innerText.trim() === '{label_text}') {{
                        // thử nextElementSibling
                        const sib = el.nextElementSibling;
                        if (sib) return sib.innerText.replace(/\\s+/g, ' ').trim();
                        // thử parent rồi tìm sibling của parent
                        const parentSib = el.parentElement?.nextElementSibling;
                        if (parentSib) return parentSib.innerText.replace(/\\s+/g, ' ').trim();
                    }}
                }}
                return null;
            }})()
        """)

    # position: ưu tiên JSON-LD, fallback label DOM
    if not position:
        position = await get_by_label("Cấp bậc")

    # degree: chỉ có trong DOM
    degree = await get_by_label("Học vấn")

    # Các field bị miss ở JSON-LD (trang cũ không có full LD) → fallback DOM
    if not job_title:
        job_title = await tab.evaluate("""
            (() => {
                const el = document.querySelector('h1, h2.job-detail__info--title');
                return el ? el.innerText.replace(/\\s+/g, ' ').trim() : null;
            })()
        """)

    if not salary_range:
        salary_range = await get_by_label("Mức lương") or \
                       await get_text(tab, '.section-salary .job-detail__info--section-content-value')

    if not location:
        loc_short = await get_by_label("Địa điểm") or \
                    await get_by_label("Địa điểm làm việc")
        location = loc_short

    if not years_of_experience:
        yoe_raw = await get_by_label("Kinh nghiệm")
        years_of_experience = yoe_raw.split()[0] if yoe_raw else None

    if not due_date:
        due_raw = await get_text(tab, '.job-detail__information-detail--actions-label')
        if due_raw:
            due_date = due_raw.strip().split()[-1]
        else:
            due_date = await tab.evaluate("""
                (() => {
                    const el = document.querySelector('.job-detail__info--deadline-date');
                    return el ? el.innerText.replace(/\\s+/g, ' ').trim() : null;
                })()
            """)

    return {
        "url": url,
        "job_title": job_title,
        "salary_range": salary_range,
        "location": location,
        "years_of_experience": years_of_experience,
        "position": position,
        "degree": degree,
        "general_information": general_information,
        "job_description": job_description,
        "job_requirements": job_requirements,
        "benefits": benefits,
        "due_date": due_date,
        "platform": "TopCV",
    }
async def scrape_listing_page(tab, keyword):
    """
    Scrape tất cả job URL từ một trang listing, trả về list URL.
    TopCV listing page: div.job-item-search-result h3.title a[href]

    NOTE: tab.evaluate() đôi khi trả về CDP object thay vì plain value.
    Dùng JSON.stringify để ép về string rồi json.loads() bên Python.
    """
    # Scroll xuống cuối để trigger lazy-load toàn bộ job cards
    await tab.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
    await asyncio.sleep(1.5)
    await tab.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
    await asyncio.sleep(0.5)

    raw = await tab.evaluate("""
        (() => {
            const links = document.querySelectorAll('.job-item-search-result h3.title a[href]');
            const urls = Array.from(links).map(a => a.href).filter(Boolean);
            return JSON.stringify(urls);
        })()
    """)
    try:
        job_urls = json.loads(raw) if raw else []
    except Exception:
        job_urls = []
    # Đảm bảo mỗi phần tử là string thuần (tránh CDP object lọt qua)
    job_urls = [u for u in job_urls if isinstance(u, str) and u.startswith("http")]
    log.info(f"[{keyword}] Found {len(job_urls)} job links on {tab.url}")
    return job_urls


async def get_next_page_url(tab):
    """Lấy URL trang tiếp theo từ pagination."""
    try:
        raw = await tab.evaluate("""
            (() => {
                const next = document.querySelector('ul.pagination li a[rel="next"]');
                if (!next) return null;
                // Ưu tiên href thật, fallback sang data-href
                return next.href || next.getAttribute('data-href') || null;
            })()
        """)
        if not raw or not isinstance(raw, str):
            return None
        # Strip tracking query params, chỉ giữ lại URL sạch
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
        parsed = urlparse(raw)
        # Chỉ giữ param 'page' nếu có, bỏ toàn bộ tracking params
        qs = parse_qs(parsed.query, keep_blank_values=False)
        clean_qs = {k: v for k, v in qs.items() if k == "page"}
        clean_url = urlunparse(parsed._replace(query=urlencode(clean_qs, doseq=True)))
        return clean_url if clean_url.startswith("http") else None
    except Exception:
        return None


async def main():
    browser = await uc.start(
        headless=False,
        browser_args=[
            "--disable-blink-features=AutomationControlled",
            "--password-store=basic",
            "--disable-save-password-bubble",
            "--disable-features=PasswordManagerOnboarding,AutofillServerCommunication",
            "--disable-features=PasswordLeakDetection,PasswordManagerOnboarding,AutofillEnableAccountWalletStorage",
        ],
        lang="vi-VN",
    )

    tab = browser.main_tab

    for i, keyword in enumerate(KEYWORDS):
        keyword_start_time = time.time()

        # long break every 10 keywords
        if i > 0 and i % 10 == 0:
            wait = random.uniform(30, 90)
            log.info(f"Long break: {wait:.0f}s after {i} keywords")
            await asyncio.sleep(wait)

        log.info(f"[{keyword}] Searching...")
        current_url = f"https://www.topcv.vn/tim-viec-lam-{keyword}"

        while current_url:
            await tab.get(current_url)
            await wait_for_cloudflare(tab)
            await human_sleep(2, 4)
            await dismiss_popup(tab)

            job_urls = await scrape_listing_page(tab, keyword)

            if not job_urls:
                log.info(f"[{keyword}] No jobs found at {current_url}")
                break

            for idx, job_url in enumerate(job_urls):
                # Loại bỏ tracking params để tránh lỗi CDP -32602
                job_url = clean_url(job_url)

                # bỏ qua URL đã scrape
                # if job_url in seen_urls:
                #     log.info(f"[{keyword}] Skipping duplicate: {job_url}")
                #     continue
                # seen_urls.add(job_url)

                log.info(f"[{keyword}] Scraping job {idx+1}/{len(job_urls)}: {job_url}")

                try:
                    await tab.get(job_url)
                    await wait_for_cloudflare(tab)
                    await human_sleep(1.5, 3.5)
                    await dismiss_popup(tab)

                    # scroll xuống để lazy load content
                    await tab.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
                    await asyncio.sleep(1.5)
                    await tab.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
                    await asyncio.sleep(0.5)

                    job_data = await scrape_job_page(tab, job_url)

                    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                        f.write(json.dumps(job_data, ensure_ascii=False) + "\n")
                        f.flush()
                    log.info(f"[{keyword}] Saved: {job_data['job_title']}")

                except Exception as e:
                    log.warning(f"[{keyword}] Error scraping {job_url}: {e}")

                await human_sleep(1.0, 2.5)

            # --- next page ---
            # Cần quay lại listing page để lấy next page URL
            await tab.get(current_url)
            await wait_for_cloudflare(tab)
            await human_sleep(1.5, 3.0)

            next_url = await get_next_page_url(tab)
            if next_url:
                log.info(f"[{keyword}] Going to next page: {next_url}")
                current_url = next_url
            else:
                log.info(f"[{keyword}] No more pages.")
                break

        log.info(f"[{keyword}] Done in {time.time() - keyword_start_time:.1f}s")

    log.info(f"Script finished in {time.time() - script_start_time:.1f}s")
    browser.stop()


uc.loop().run_until_complete(main())