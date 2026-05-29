import scrapy
from scrapy_shell.items import topcv_item
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
import logging
logger = logging.getLogger(__name__)
# import os

# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # get project root dir
# print("BASE_DIR:", BASE_DIR)  # thêm dòng này

# OUTPUT_DIR = os.path.join(BASE_DIR, "test/topcv/raw_data")
# print("BASE_DIR:", BASE_DIR)  # thêm dòng này
# os.makedirs(OUTPUT_DIR, exist_ok=True)
# OUTPUT_FILE = os.path.join(OUTPUT_DIR, "topcv_test_data.jsonl")
# print("OUTPUT_DIR created!")  # thêm dòng này

# LOG_DIR = os.path.join(BASE_DIR, "test/topcv/logs")
# os.makedirs(LOG_DIR, exist_ok=True)
# LOG_FILE = os.path.join(LOG_DIR, f"topcv_{timestamp}.log")

class TopcvSpiderSpider(scrapy.Spider):
    name = "topcv_spider"
    allowed_domains = ["www.topcv.vn"]
    # start_urls = ["https://www.topcv.vn/"]

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
            "scrapy_user_agents.middlewares.RandomUserAgentMiddleware": None,
            "scrapy_shell.middlewares.CurlCffiMiddleware": 543,
        },
        "LOG_FILE": f"f:/data_job_market_repo/test/topcv/logs/topcv_{timestamp}.log",
        "LOG_LEVEL": "INFO",
        "FEEDS": {
            f"f:/data_job_market_repo/test/topcv/raw_data/topcv_{timestamp}.jsonl": {
                "format": "jsonlines",
                "encoding": "utf8",
                # "overwrite": False
            }
        },
        "CONCURRENT_REQUESTS": 8,  # maximum number of requests to all domains
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,  # increase this first to increase speed
        "DOWNLOAD_DELAY": 10,
        "RANDOMIZED_DOWNLOAD_DELAY": True,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429, 403],
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 5,  # initial download delay
        "AUTOTHROTTLE_MAX_DELAY": 60,  # maximum download delay to be set in case of high latencies
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1,  # average number of requests Scrapy should be sending in parallel to each remote server
        "FEED_EXPORT_FIELDS": [
            "url",
            "job_title",
            "salary_range",
            "location",
            "years_of_experience",
            "general_information",
            "job_description",
            "job_requirements",
            "benefits",
            "due_date",
            "platform",
        ],
    }

    KEYWORDS = [
        # Data Core
        "data-analyst",
        "data",
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
        # intern versions
        # Data Core Intern
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
        # BI Intern
        "intern-business-intelligence",
        "intern-analytics-engineer",
        "intern-bi-developer",
        "intern-power-bi",
        "intern-tableau",
        # Engineering / Database Intern
        "intern-etl",
        "intern-database-administrator",
        "intern-sql",
        # ML / AI Classic Intern
        "intern-machine-learning",
        "intern-deep-learning",
        "intern-mlops",
        "intern-ai-engineer",
        "intern-ai-developer",
        "intern-ai-researcher",
        "intern-artificial-intelligence",
        "intern-computer-vision",
        "intern-nlp",
        # GenAI / Modern AI Intern
        "intern-generative-ai",
        "intern-gen-ai",
        "intern-llm",
        "intern-prompt-engineer",
        "intern-chatbot",
    ]

    # https://www.topcv.vn/tim-viec-lam-{keyword}
    # current_keyword_index=0
    # start_urls = [f"https://www.topcv.vn/tim-viec-lam-{KEYWORDS[0]}"]
    
    async def start(self):
        logger.info(f"start_requests called, total keywords: {len(self.KEYWORDS)}")
        for keyword in self.KEYWORDS:
            logger.info(f"Yielding request for keyword: {keyword}")
            yield scrapy.Request(
                url=f"https://www.topcv.vn/tim-viec-lam-{keyword}",
                callback=self.parse,
                cb_kwargs={"keyword": keyword}
            )
    
    
    # def parse(self, response):
    #     jobs = response.css("div.job-item-search-result")
    #     if len(jobs)>0: 
    #         for job in jobs:
    #             job_url = job.css("h3.title a::attr('href')").get()
    #             if job_url:
    #                 yield response.follow(
    #                     job_url, 
    #                     callback=self.parse_job
    #                 )
    #         next_page_url = response.css('ul.pagination li a[rel="next"]::attr(data-href)').get()
    #         if next_page_url:
    #             yield response.follow(next_page_url, callback=self.parse)
        
    #     else:
    #         logger.info(f"No job links found on {response.url}")
    #         logger.info(f"Done with keyword: {self.KEYWORDS[self.current_keyword_index]}, moving to the next keyword")
    #         self.current_keyword_index += 1
    #         if self.current_keyword_index < len(self.KEYWORDS):
    #                 next_keyword = self.KEYWORDS[self.current_keyword_index]
    #                 next_url = f"https://careerviet.vn/viec-lam/{next_keyword}-k-vi.html"
                    
    #                 logger.info(f"Proceeding with {next_keyword}")
    #                 yield scrapy.Request(url=next_url, callback=self.parse)
    #         else:
    #             logger.info("Keyword list exhausted. Crawling completed.")


    def parse(self, response, keyword):
        jobs = response.css("div.job-item-search-result")
        logger.info(f"[{keyword}] final_url={response.url}, jobs={len(jobs)}")
        if jobs:
            for job in jobs:
                job_url = job.css("h3.title a::attr(href)").get()
                if job_url:
                    yield response.follow(job_url, callback=self.parse_job)
            
            next_page_url = response.css('ul.pagination li a[rel="next"]::attr(data-href)').get()
            if next_page_url:
                yield response.follow(next_page_url, callback=self.parse, cb_kwargs={"keyword": keyword})
        else:
            logger.info(f"No jobs found for keyword: {keyword}")

    def parse_job(self, response):
        item = topcv_item()

        item["url"] = response.url

        title_1 = response.xpath('normalize-space(string(//h1[contains(@class, "job-detail__info--title")]))').get()
        title_2 = response.xpath('normalize-space(//h2[contains(@class, "premium-job-basic-information__content--title")])').get()
        item["job_title"] = title_1 if title_1 else title_2

        salary_range_1 = response.xpath('//div[contains(@class, "section-salary")]//div[@class="job-detail__info--section-content-value"]/text()').get()
        salary_range_2 = response.xpath('//div[contains(@class, "basic-information-item__data--label") and re:test(., "mức lương", "i")]/following-sibling::div[contains(@class, "basic-information-item__data--value")]/text()').get()
        item["salary_range"] = salary_range_1 if salary_range_1 else salary_range_2

        explicit_location_1 = response.xpath('normalize-space(string(//div[contains(@class, "job-description__item")][h3[contains(., "Địa điểm làm việc")]]//div[contains(@class, "job-description__item--content")]))').get()
        explicit_location_2 = response.xpath('normalize-space(string(//div[contains(@class, "premium-job-description__box")][h2[contains(., "Địa điểm")]]/div))').get()
        if explicit_location_1:
            item["location"] = explicit_location_1
        elif explicit_location_2:
            item["location"] = explicit_location_1
        else:
            item["location"] = response.xpath('//div[contains(@class, "section-location")]//a/text()').get() # keep

        yoe_1 = response.xpath('//div[@id="job-detail-info-experience"]//div[@class="job-detail__info--section-content-value"]/text()').get()
        yoe_2 = response.xpath('//div[contains(@class, "basic-information-item__data--label") and re:test(., "kinh nghiệm", "i")]/following-sibling::div[contains(@class, "basic-information-item__data--value")]/text()').get()
        if yoe_1:
            item["years_of_experience"] = yoe_1.split()[0]
        elif yoe_2:
            item["years_of_experience"] = yoe_2.split()[0]

        general_information_list = response.xpath('//div[contains(@class, "job-tags__group-list-tag-scroll")]//a/text()').getall()
        item["general_information"] = [tag.strip() for tag in general_information_list]


        jd_1 = response.xpath('normalize-space(string(//div[@class="job-description__item--content"]))').get()
        jd_2_list = response.xpath('//div[contains(@class, "premium-job-description__box")][h2[contains(., "Mô tả công việc")]]/div[contains(@class, "premium-job-description__box--content")]//text()').getall()
        if jd_1:
            item["job_description"] = jd_1
        elif len(jd_2_list)>0:
            item['job_description'] = [el.strip() for el in jd_2_list] 


        jr_1 = response.xpath('//div[h3[contains(text(), "Yêu cầu ứng viên")]]//li//text()').getall()
        jr_2 = response.xpath('//div[contains(@class, "premium-job-description__box")][h2[contains(., "Yêu cầu")]]/div[contains(@class, "premium-job-description__box--content")]//text()').getall()
        if jr_1:
            item["job_requirements"] = jr_1
        elif len(jd_2_list):
            item['job_requirements'] = [el.strip() for el in jr_2]

        benefits_1 = [text.strip() for text in response.css(".benefit .job-description__item--content *::text").getall() if text.strip()]
        benefits_2 = [node.xpath('normalize-space(.)').get() for node in response.xpath('//div[contains(@class, "premium-job-description__box")][h2[contains(., "Quyền lợi")]]/div[contains(@class, "premium-job-description__box--content")]//*[self::li or self::p]') if node.xpath('normalize-space(.)').get()]
        if benefits_1:
            item["benefits"] = benefits_1
        elif benefits_2:
            tmp = [b.strip() for b in response.xpath('normalize-space(//h3[contains(@class, "custom-form-job__item--title") and contains(., "Quyền lợi")]/following-sibling::div[contains(@class, "custom-form-job__item--content")])').get().split(',') if b.strip()]
            item['benefits'] = benefits_2 + tmp if tmp else benefits_2

        due_date = response.xpath('//div[@class="job-detail__information-detail--actions-label"]/text()').get() # keep
        item["due_date"] = due_date.strip().split()[-1] if due_date else None

        item["platform"] = "TopCV"

        yield item
