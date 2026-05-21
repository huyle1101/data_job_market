from email.mime import text
from urllib import response
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
import re
import scrapy
from scrapy_shell.items import careerviet_item
import logging
logger = logging.getLogger(__name__)


page=1
class CareervietSpiderSpider(scrapy.Spider):
    name = "careerviet_spider"
    allowed_domains = ["careerviet.vn"]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "LOG_FILE":f"f:/data_job_market_repo/test/careerviet/logs/careerviet_{timestamp}.log",
        "LOG_LEVEL":"INFO",
        "FEEDS":{
            f"f:/data_job_market_repo/test/careerviet/raw_data/careerviet_{timestamp}.json":{
                'format':'json',
                "encoding": "utf8"
                # "overwrite": False
            }
    },
        "CONCURRENT_REQUESTS" : 32,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY" : 1,
        "RANDOMIZED_DOWNLOAD_DELAY":True, 

        "RETRY_ENABLED":True,
        "RETRY_TIMES": 10, 
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429, 403],

        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 5, # initial download delay
        "AUTOTHROTTLE_MAX_DELAY": 60, # maximum download delay to be set in case of high latencies
        "AUTOTHROTTLE_TARGET_CONCURRENCY"  : 1.0, # average number of requests Scrapy should be sending in parallel to each remote server
        
        "FEED_EXPORT_FIELDS": [ 
            "url",
            "title",
            "company_name",
            "location",
            "posted_date",
            "due_date",
            "salary",
            "job_category",
            "experience",
            "employment_type",
            "position",
            "benefits",
            "job_description",
            "job_requirements",
            "other_information"
        ]
    }

    # url = f'https://careerviet.vn/viec-lam/{search_keyword}-k-vi.html'
    # https://careerviet.vn/viec-lam/data-k-vi.html
    # https://careerviet.vn/viec-lam/data-analyst-k-vi.html
    # https://careerviet.vn/viec-lam/data-engineer-k-vi.html

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
        "etl-developer",
        "database-administrator",
        "sql",
        "python-developer",

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
        "statistician",

        # GenAI / Modern AI
        "generative-ai",
        "gen-ai",
        "llm",
        "prompt-engineer",
        "chatbot",
    ]
    tmp = []
    for i in KEYWORDS:
        tmp.append(f"https://careerviet.vn/viec-lam/{i}-k-vi.html")


    start_urls = tmp

    def parse(self, response):
        job_links = response.xpath('//a[contains(@class, "job_link")]/@href').getall()
        if job_links is not None:
            for job_link in job_links:
                yield response.follow(
                    f'https://careerviet.vn/{job_link}',
                    callback=self.parse_job                
                )
        
        # build next page url
        current_url = response.url
        match = re.search(r'/viec-lam/(.+?)-k(?:-trang-(\d+))?-vi\.html', current_url)
        if match:
            keyword = match.group(1) 
            page = int(match.group(2) or 1) # None = first page
            next_page = page + 1
            
            next_page_url = f"https://careerviet.vn/viec-lam/{keyword}-k-trang-{next_page}-vi.html"
            yield response.follow(next_page_url, callback=self.parse)
        # page+=1


    def remove_html_tags(self, html_text):
        return re.sub(r'[\n\t]+', '', html_text)
    
    def parse_job(self, response):
        item = careerviet_item()
        item['url'] = response.url
        item['title'] = response.xpath('//h1[@class="title"]/text()').get()
        item['company_name'] = response.css('a.job-company-name::text').get()

        explicit_location = response.xpath('//div[@class="place-name"]/span/text()').getall()
        if explicit_location:
            item['location'] = explicit_location
        else:
            item['location'] = response.xpath('//strong[re:test(., "địa điểm", "i")]/following-sibling::p/a/text()').get()
        
        # re:test to ignore case
        item['posted_date'] = response.xpath('//strong[re:test(., "ngày cập nhật", "i")]/following-sibling::p//text()').get()
        item['due_date'] = response.xpath('//strong[re:test(., "hết hạn nộp", "i")]/following-sibling::p//text()').get()
        item['salary'] = response.xpath('//strong[re:test(., "lương", "i")]/following-sibling::p//text()').get()
        item['job_category'] = response.xpath('//strong[re:test(., "ngành nghề", "i")]/following-sibling::p//text()').get()
        item['experience'] = response.xpath('//strong[re:test(., "kinh nghiệm", "i")]/following-sibling::p//text()').getall()
        item['employment_type'] = response.xpath('//strong[re:test(., "hình thức", "i")]/following-sibling::p//text()').get()
        item['position'] = response.xpath('//strong[re:test(., "cấp bậc", "i")]/following-sibling::p//text()').get()
        
        item['benefits'] = response.xpath('//ul[@class="welfare-list"]/li/text()').getall()

        jd_text = response.xpath('//h2[re:test(., "mô tả công việc", "i")]/following-sibling::div//text()').getall()
        item['job_description'] = ' '.join(list(map(self.remove_html_tags, jd_text)))

        jr_text = response.xpath('//h2[re:test(., "yêu cầu công việc", "i")]/following-sibling::div//text()').getall()
        item['job_requirements'] = ' '.join(list(map(self.remove_html_tags, jr_text)))

        other_info_text = response.xpath('//h3[re:test(., "thông tin khác", "i")]/following-sibling::div//text()').getall()
        item['other_information'] = ' '.join(list(map(self.remove_html_tags, other_info_text)))
        item['platform'] = "CareerViet"

        logger.info(response.text[:2000])
        yield item

