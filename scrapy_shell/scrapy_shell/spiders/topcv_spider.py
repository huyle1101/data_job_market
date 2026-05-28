import scrapy


class TopcvSpiderSpider(scrapy.Spider):
    name = "topcv_spider"
    allowed_domains = ["www.topcv.vn"]
    start_urls = ["https://www.topcv.vn/"]

    def parse(self, response):
        pass
