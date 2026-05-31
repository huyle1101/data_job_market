# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ScrapyShellItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class careerviet_item(scrapy.Item):
    url = scrapy.Field()
    job_title = scrapy.Field()
    company_name = scrapy.Field()
    location = scrapy.Field()
    posted_date = scrapy.Field()
    due_date = scrapy.Field()
    salary = scrapy.Field()
    job_category = scrapy.Field()
    years_of_experience = scrapy.Field()
    employment_type = scrapy.Field()
    position = scrapy.Field()
    benefits = scrapy.Field()
    job_description = scrapy.Field()
    job_requirements = scrapy.Field()
    other_information = scrapy.Field()
    platform = scrapy.Field()

