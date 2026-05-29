import requests
import json
import re
import os
import sys
import logging
from datetime import datetime
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_DIR = os.path.join(BASE_DIR, "")          # fill in output folder
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "")       # fill in .jsonl filename

LOG_DIR = os.path.join(BASE_DIR, "")             # fill in log folder
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(LOG_DIR, f"vnw_{timestamp}.log")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# LOGGING  (mirrors itviec_nodriver.py setup)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),      # also print to terminal
    ]
)
log = logging.getLogger()

# ---------------------------------------------------------------------------
# KEYWORDS  (from image)
# ---------------------------------------------------------------------------

KEYWORDS = [
    # Data Core
    "data", "data analyst", "data engineer", "data scientist",
    "data science", "data analytics", "data architect", "data modeler",
    "data warehouse", "data governance", "data quality", "big data",

    # BI
    "business intelligence", "analytics engineer", "bi developer",
    "power bi", "tableau",

    # Engineering / Database
    "etl", "database administrator", "sql",

    # ML / AI Classic
    "machine learning", "deep learning", "mlops", "ai engineer",
    "ai developer", "ai researcher", "artificial intelligence",
    "computer vision", "nlp",

    # GenAI / Modern AI
    "generative ai", "gen ai", "llm", "prompt engineer", "chatbot",

    # Data Core Intern
    "intern data", "intern data analyst", "intern data engineer",
    "intern data scientist", "intern data science", "intern data analytics",
    "intern data architect", "intern data modeler", "intern data warehouse",
    "intern data governance", "intern data quality", "intern big data",

    # BI Intern
    "intern business intelligence", "intern analytics engineer",
    "intern bi developer", "intern power bi", "intern tableau",

    # Engineering / Database Intern
    "intern etl", "intern database administrator", "intern sql",

    # ML / AI Classic Intern
    "intern machine learning", "intern deep learning", "intern mlops",
    "intern ai engineer", "intern ai developer", "intern ai researcher",
    "intern artificial intelligence", "intern computer vision", "intern nlp",

    # GenAI / Modern AI Intern
    "intern generative ai", "intern gen ai", "intern llm",
    "intern prompt engineer", "intern chatbot",
]

# ---------------------------------------------------------------------------
# SHARED HEADERS  (same as test_playwright.py)
# ---------------------------------------------------------------------------

SEARCH_HEADERS = {
    'accept': '*/*',
    'accept-language': 'vi',
    'content-type': 'application/json',
    'origin': 'https://www.vietnamworks.com',
    'priority': 'u=1, i',
    'referer': 'https://www.vietnamworks.com/',
    'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    'x-source': 'Job-Details',
}

PAGE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def parse_date(iso_str):
    # convert ISO 8601 string (e.g. "2026-05-27T17:12:58+07:00") to dd/mm/yyyy
    # return None if the string is missing or unparseable
    if not iso_str:
        return None
    try:
        # strip timezone offset so strptime can handle it without %z quirks
        date_part = iso_str[:10]                          # "2026-05-27"
        dt = datetime.strptime(date_part, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None


def clean_html(raw_html):
    # strip HTML tags and unescape entities, return plain text
    # mirrors the clean_html_data logic in other.py
    if not raw_html:
        return None
    try:
        decoded = re.sub(
            r'\\u([0-9a-fA-F]{4})',
            lambda m: chr(int(m.group(1), 16)),
            raw_html
        )
        decoded = decoded.replace('\\"', '"').replace('\\n', '\n').replace('\\/', '/')
        soup = BeautifulSoup(decoded, 'html.parser')
        return soup.get_text(separator='\n', strip=True)
    except Exception as e:
        log.info(f"clean_html error: {e}")
        return None

# ---------------------------------------------------------------------------
# STEP 1 - search request for one keyword, one page
# ---------------------------------------------------------------------------

def search_jobs(keyword, page=0, hits_per_page=100):
    # send POST to VietnamWorks search API and return raw JSON or None on error
    payload = {
        'query': keyword,
        'filter': [],
        'ranges': [],
        'order': [{'field': 'approvedOn', 'value': 'desc'}],
        'hitsPerPage': hits_per_page,
        'page': page,
        'retrieveFields': [
            'jobId',
            'jobUrl',
            'jobTitle',
            'approvedOn',
            'companyName',
            'workingLocations',
            'expiredOn',
            'jobFunction',
            'yearsOfExperience',
            'jobLevelVI',
            'benefits',
            'prettySalary',
        ],
        'exclude': [],
        'userId': None,
    }

    try:
        response = requests.post(
            'https://ms.vietnamworks.com/job-search/v1.0/search',
            headers=SEARCH_HEADERS,
            json=payload,
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()
        else:
            log.info(f"Search failed [{response.status_code}] keyword='{keyword}' page={page}")
            return None
    except Exception as e:
        log.info(f"Search request error: {e}")
        return None

# ---------------------------------------------------------------------------
# STEP 2 - parse one job entry from the search result data array
# ---------------------------------------------------------------------------

def parse_job_entry(job):
    # extract all required flat fields from a single job dict

    # working locations: build a list of dicts with address + cityNameVI
    raw_locations = job.get('workingLocations') or []
    working_locations = [
        {
            'address': loc.get('address'),
            'cityNameVI': loc.get('cityNameVI'),
        }
        for loc in raw_locations
    ]

    # benefits: collect every benefitValue string into a list
    raw_benefits = job.get('benefits') or []
    benefits = [b.get('benefitValue') for b in raw_benefits if b.get('benefitValue')]

    # jobFunction: only need parentNameVI at top level
    job_function = job.get('jobFunction') or {}
    job_function_parent = job_function.get('parentNameVI')

    return {
        'jobId':              job.get('jobId'),
        'jobUrl':             job.get('jobUrl'),
        'jobTitle':           job.get('jobTitle'),
        'posted_date':        parse_date(job.get('approvedOn')),
        'companyName':        job.get('companyName'),
        'workingLocations':   working_locations,
        'due_date':           parse_date(job.get('expiredOn')),
        'jobFunction':        job_function_parent,
        'yearsOfExperience':  job.get('yearsOfExperience'),
        'jobLevelVI':         job.get('jobLevelVI'),
        'benefits':           benefits,
        'prettySalary':       job.get('prettySalary'),
        # placeholders filled by fetch_job_detail below
        'jobDescription':     None,
        'jobRequirement':     None,
    }

# ---------------------------------------------------------------------------
# STEP 3 - fetch individual job page and extract description + requirement
# ---------------------------------------------------------------------------

def fetch_job_detail(job_url):
    # GET the job page HTML and use regex to extract jobDescription and jobRequirement
    # mirrors the extraction logic in other.py
    if not job_url:
        return None, None

    try:
        response = requests.get(job_url, headers=PAGE_HEADERS, timeout=30)
        if response.status_code != 200:
            log.info(f"Detail page failed [{response.status_code}] url={job_url}")
            return None, None
        html_text = response.text
    except Exception as e:
        log.info(f"Detail page request error: {e}")
        return None, None

    # follow redirect hint embedded in Next.js HTML if the slug changed
    redirect_match = re.search(r'NEXT_REDIRECT;replace;(https://[^;]+);', html_text)
    if redirect_match:
        correct_url = redirect_match.group(1)
        log.info(f"Redirect detected, following: {correct_url}")
        return fetch_job_detail(correct_url)

    # stitch Next.js chunked script tags back into one continuous string
    stitched = re.sub(
        r'"\]\)\s*</script>\s*<script[^>]*>\s*self\.__next_f\.push\(\[1,"',
        '',
        html_text
    )

    def extract_field(field_name, text):
        # locate the field key, resolve any $ref variable, return raw HTML string
        match = re.search(rf'\\"{field_name}\\"\s*:\s*\\"(.*?)\\"', text)
        if not match:
            return None

        value = match.group(1)

        # check if value is a reference variable like $2a or $abc
        ref_match = re.match(r'^\$([a-zA-Z0-9]+)$', value)
        if ref_match:
            var_id = ref_match.group(1)
            # find the actual content stored under that variable id
            content_match = re.search(rf'{var_id}:[^,]+,(.*?)"\]\)', text)
            if content_match:
                return content_match.group(1).lstrip('"')
            return None

        return value

    raw_jd = extract_field('jobDescription', stitched)
    raw_jr = extract_field('jobRequirement', stitched)

    return clean_html(raw_jd), clean_html(raw_jr)

# ---------------------------------------------------------------------------
# STEP 4 - append one job record to the JSONL output file
# ---------------------------------------------------------------------------

def save_job(job_data):
    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(job_data, ensure_ascii=False) + '\n')
        f.flush()

# ---------------------------------------------------------------------------
# MAIN - loop keywords, paginate, deduplicate, fetch details, save
# ---------------------------------------------------------------------------

def main():
    seen_job_ids = set()        # track already-processed jobIds across all keywords
    total_saved = 0

    log.info(f"Starting VietnamWorks scraper. Keywords: {len(KEYWORDS)}")

    for kw_idx, keyword in enumerate(KEYWORDS):
        log.info(f"[{kw_idx + 1}/{len(KEYWORDS)}] Keyword: '{keyword}'")
        page = 0

        while True:
            log.info(f"  Fetching page {page} for '{keyword}'...")
            result = search_jobs(keyword, page=page)

            if not result:
                log.info(f"  No result returned, skipping keyword.")
                break

            meta = result.get('meta', {})
            jobs = result.get('data', [])
            total_pages = meta.get('nbPages', 1)

            log.info(f"  Page {page}/{total_pages - 1}, jobs on page: {len(jobs)}")

            if not jobs:
                break

            for job in jobs:
                job_id = job.get('jobId')

                # skip if we have already saved this job from a previous keyword
                if job_id in seen_job_ids:
                    log.info(f"  Duplicate jobId={job_id}, skipping.")
                    continue
                seen_job_ids.add(job_id)

                # parse flat fields from search result
                record = parse_job_entry(job)

                # fetch full description and requirement from detail page
                job_url = record.get('jobUrl')
                log.info(f"  Fetching detail for jobId={job_id} ...")
                jd, jr = fetch_job_detail(job_url)
                record['jobDescription'] = jd
                record['jobRequirement'] = jr

                # write to JSONL
                save_job(record)
                total_saved += 1
                log.info(f"  Saved: [{total_saved}] {record['jobTitle']} @ {record['companyName']}")

            # move to next page if there are more
            page += 1
            if page >= total_pages:
                log.info(f"  All pages done for '{keyword}'.")
                break

    log.info(f"Scraper finished. Total jobs saved: {total_saved}")


if __name__ == '__main__':
    main()