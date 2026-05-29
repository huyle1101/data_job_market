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
            f"f:/data_job_market_repo/test/careerviet/raw_data/careerviet_{timestamp}.jsonl":{
                'format':'jsonlines',
                "encoding": "utf8"
                # "overwrite": False
            }
    },
        "CONCURRENT_REQUESTS": 500, # maximum number of requests to all domains
        "CONCURRENT_REQUESTS_PER_DOMAIN" : 32, # increase this first to increase speed
        "DOWNLOAD_DELAY" : 1,
        "RANDOMIZED_DOWNLOAD_DELAY":True,
        
        "RETRY_ENABLED":True,
        "RETRY_TIMES": 3, 
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429, 403],

        
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 0.5, # initial download delay
        "AUTOTHROTTLE_MAX_DELAY": 60, # maximum download delay to be set in case of high latencies
        "AUTOTHROTTLE_TARGET_CONCURRENCY"  : 32, # average number of requests Scrapy should be sending in parallel to each remote server
        
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
    # tmp = []
    # for i in KEYWORDS:
    #     tmp.append(f"https://careerviet.vn/viec-lam/{i}-k-vi.html")

    # start with the first keyword, then move sequentially to the next one after exhausting all jobs of the current keyword
    current_keyword_index=0
    start_urls = [f"https://careerviet.vn/viec-lam/{KEYWORDS[0]}-k-vi.html"]

    def parse(self, response):
        # changed structured: https://careerviet.vn/vi/tim-viec-lam/chuyen-vien-tai-chinh-financial-analyst-financial-specialist.35C759A7.html
        job_links = response.xpath('//a[contains(@class, "job_link")]/@href').getall()
        if len(job_links) > 0:
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

        # if no job links found, move to the next keyword
        else:
            logger.info(f"No job links found on {response.url}")
            logger.info(f"Done with keyword: {self.KEYWORDS[self.current_keyword_index]}, moving to the next keyword")
            self.current_keyword_index += 1
            if self.current_keyword_index < len(self.KEYWORDS):
                    next_keyword = self.KEYWORDS[self.current_keyword_index]
                    next_url = f"https://careerviet.vn/viec-lam/{next_keyword}-k-vi.html"
                    
                    logger.info(f"Proceeding with {next_keyword}")
                    yield scrapy.Request(url=next_url, callback=self.parse)
            else:
                logger.info("Keyword list exhausted. Crawling completed.")

    def remove_html_tags(self, html_text):
        return re.sub(r'[\n\t]+', '', html_text)
    
    def parse_job(self, response):
        item = careerviet_item()
        item['url'] = response.url
        
        title_1 = response.xpath('//h1[@class="title"]/text()').get()
        title_2 = response.xpath('//div[contains(@class, "title")]/h2/text()').get()
        item['title'] = title_1 if title_1 else title_2

        company_name_1 = response.css('a.job-company-name::text').get()
        company_name_2 = response.xpath('//a[contains(@class, "company")]/text()').get()
        item['company_name'] = company_name_1 if company_name_1 else company_name_2

        # case 1
        explicit_location = response.xpath('//div[@class="place-name"]/span/text()').getall()
        location_1 = response.xpath('//strong[re:test(., "địa điểm", "i")]/following-sibling::p/a/text()').getall()
        location_2 = response.css('p.list-workplace a::text').getall()

        if location_1:
            item['location'] = list(set(location_1 + explicit_location))
        else:
            item['location'] = list(set(location_2 + explicit_location))
        
        # re:test to ignore case
        text_list = response.xpath('//td[@class="content"]/p[not(@class)]/text()').getall()
        
        posted_date_1 = response.xpath('//strong[re:test(., "ngày cập nhật", "i")]/following-sibling::p//text()').get()
        posted_date_2 = text_list[-1] if len(text_list) > 0 else None
        item['posted_date'] = posted_date_1 if posted_date_1 else posted_date_2

        due_date_1 = response.xpath('//strong[re:test(., "hết hạn nộp", "i")]/following-sibling::p//text()').get()
        due_date_2 = response.css('td.content p.red::text').get()
        item['due_date'] = due_date_1 if due_date_1 else due_date_2
        
        salary_1 = response.xpath('//strong[re:test(., "lương", "i")]/following-sibling::p//text()').get()
        salary_2 = response.css('div.box-info td.content p.green strong::text').get()
        item['salary'] = salary_1 if salary_1 else salary_2

        job_category_1 = response.xpath('//strong[re:test(., "ngành nghề", "i")]/following-sibling::p//text()').get()
        job_category_2 = response.css('td.content span a::text').getall()
        item['job_category'] = job_category_1 if job_category_1 else job_category_2
        
        
        item['experience'] = response.xpath('//strong[re:test(., "kinh nghiệm", "i")]/following-sibling::p//text()').getall()
        
        employment_type_1 = response.xpath('//strong[re:test(., "hình thức", "i")]/following-sibling::p//text()').get()
        employment_type_2 = text_list[0] if len(text_list) > 0 else None
        item['employment_type'] = employment_type_1 if employment_type_1 else employment_type_2
        
        position_1 = response.xpath('//strong[re:test(., "cấp bậc", "i")]/following-sibling::p//text()').get()
        position_2 = text_list[1] if len(text_list) > 1 else None
        item['position'] = position_1 if position_1 else position_2

        item['benefits'] = response.xpath('//ul[@class="welfare-list"]/li/text()').getall()

        jd_text = response.xpath('//h2[re:test(., "mô tả công việc", "i")]/following-sibling::div//text()').getall()
        item['job_description'] = ' '.join(list(map(self.remove_html_tags, jd_text)))

        jr_text = response.xpath('//h2[re:test(., "yêu cầu công việc", "i")]/following-sibling::div//text()').getall()
        item['job_requirements'] = ' '.join(list(map(self.remove_html_tags, jr_text)))

        other_info_text = response.xpath('//h3[re:test(., "thông tin khác", "i")]/following-sibling::div//text()').getall()
        item['other_information'] = ' '.join(list(map(self.remove_html_tags, other_info_text)))
        item['platform'] = "CareerViet"

        yield item

