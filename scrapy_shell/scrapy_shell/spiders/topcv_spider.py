import scrapy
from scrapy_shell.items import topcv_item
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


class TopcvSpiderSpider(scrapy.Spider):
    name = "topcv_spider"
    allowed_domains = ["www.topcv.vn"]
    start_urls = ["https://www.topcv.vn/"]

    custom_settings={
        "DOWNLOADER_MIDDLEWARES" :{
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
            'scrapy_user_agents.middlewares.RandomUserAgentMiddleware': None,
            'scrapy_shell.middlewares.CurlCffiMiddleware': 543,
        },
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


    KEYWORDS = [
        # Data Core
        "data", "data-analyst", "data-engineer", "data-scientist",
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
        # Data Core Intern
        "intern-data", "intern-data-analyst", "intern-data-engineer", 
        "intern-data-scientist", "intern-data-science", "intern-data-analytics", 
        "intern-data-architect", "intern-data-modeler", "intern-data-warehouse", 
        "intern-data-governance", "intern-data-quality", "intern-big-data",

        # BI Intern
        "intern-business-intelligence", "intern-analytics-engineer", 
        "intern-bi-developer", "intern-power-bi", "intern-tableau",

        # Engineering / Database Intern
        "intern-etl", "intern-database-administrator", "intern-sql",

        # ML / AI Classic Intern
        "intern-machine-learning", "intern-deep-learning", "intern-mlops", 
        "intern-ai-engineer", "intern-ai-developer", "intern-ai-researcher", 
        "intern-artificial-intelligence", "intern-computer-vision", "intern-nlp",

        # GenAI / Modern AI Intern
        "intern-generative-ai", "intern-gen-ai", "intern-llm", 
        "intern-prompt-engineer", "intern-chatbot"
    ]


    # https://www.topcv.vn/tim-viec-lam-{keyword}
    def parse(self, response):
        pass

    def parse_job(self, response):
        item = topcv_item() 

        item['url'] = response.url

        item['job_title'] = response.xpath('normalize-space(string(//h1[contains(@class, "job-detail__info--title")]))').get()

        item['salary_range'] = response.xpath('//div[contains(@class, "section-salary")]//div[@class="job-detail__info--section-content-value"]/text()').get()

        explicit_location = response.xpath('normalize-space(string(//div[contains(@class, "job-description__item")][h3[contains(., "Địa điểm làm việc")]]//div[contains(@class, "job-description__item--content")]))').get()
        if explicit_location:
            item['location'] = explicit_location
        else:
            item['location'] = response.xpath('//div[contains(@class, "section-location")]//a/text()').get()

        item['years_of_experience'] = response.xpath('//div[@id="job-detail-info-experience"]//div[@class="job-detail__info--section-content-value"]/text()').get().split()[0]

        general_information_list = response.xpath('//div[contains(@class, "job-tags__group-list-tag-scroll")]//a/text()').getall()
        # Đã đổi 'item' thành 'tag' trong vòng lặp để tránh xung đột với biến item lưu dữ liệu
        item['general_information'] = [tag.strip() for tag in general_information_list]

        item['job_description'] = response.xpath('normalize-space(string(//div[@class="job-description__item--content"]))').get()

        item['job_requirement'] = response.xpath('//div[h3[contains(text(), "Yêu cầu ứng viên")]]//li//text()').getall()

        item['benefits'] = [text.strip() for text in response.css('.benefit .job-description__item--content *::text').getall() if text.strip()]

        item['due_date'] = response.xpath('//div[@class="job-detail__information-detail--actions-label"]/text()').get().strip().split()[-1]

        item['platform'] = 'TopCV'

        yield item