#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar 10 06:39:47 2019

@author: yuki_next
"""

import requests
from bs4 import BeautifulSoup
import argparse
import datetime
import os
import pathlib
import pickle
import logging
# import logging.config
import re
import sys
import urllib
import time

DEFAULT_URL_INDEX = "http://www.ohk.co.jp/kinbaku/log/index.php?PAGE={:d}"
DEFAULT_FILENAME_INDEX = "_index_page_{:02d}"
DEFAULT_FILENAME_DETAIL = "{:%Y-%m-%d}.html"

RE_DATE_URL = re.compile(r"DATE=(\d*)")

"""
logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'myFormatter': {
            'format': '%(asctime)s:%(message)s',
        }
    },
    'handlers': {
        'default': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'stream': 'ext://sys.stdout',
            'formatter': 'myFormatter',
        }
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['default'],
    },
    'disable_existing_loggers': False,
})

logger = logging.getLogger()
"""
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

handler = logging.FileHandler(os.path.splitext(sys.argv[0])[0] + ".log")
handler.setFormatter(formatter)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)

handler = logging.StreamHandler()
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

class DetailInfo(object):
    def __init__(self, target_date, title, guest):
        self.target_date = target_date
        self.title = title
        self.guest = guest
        self.shop_infos = list() # ShopInfo

    def __repr__(self):
        return str(self.__dict__)

class ShopInfo(object):
    def __init__(self, shop_li):
        ps = [p for p in shop_li.find_all("p")]
        self.category = ps[0].text
        self.name = shop_li.h4.text
        self.detail = ps[1].text
        self.url_site = None
        shop_site_link_p = shop_li.find("p", "shopSiteLink")
        if shop_site_link_p:
            self.url_site = shop_site_link_p.a["href"]
        self.url_map = None
        map_iframe = shop_li.find("iframe")
        if map_iframe:
            self.url_map = map_iframe["src"]
        self.comment = ps[-1].text

    def __repr__(self):
        return str(self.__dict__)

def get_detail_urls(soup, base_url):
    return [(urllib.parse.urljoin(base_url, h3.a["href"]), h3.a.text) for h3 in soup.find("div", "contentsIn").find_all("h3")]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="out")
    parser.add_argument("--output_fn", default="_Kinbaku.xlsx")
    parser.add_argument("--work_dir", default="html")
    parser.add_argument("--index_url", default=DEFAULT_URL_INDEX)
    parser.add_argument("--processed_list_filename", default="_processed_date.txt")
    parser.add_argument("--oauth_json_filename", 
                        default=os.path.join(
                                os.path.dirname(os.path.abspath(sys.argv[0])),
                                "My_Project_81200-9c7848aee338.json"))
    parser.add_argument("--sn_shop_info", default="Shop Info")
    args = parser.parse_args()
    
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    if not os.path.exists(args.work_dir):
        os.makedirs(args.work_dir)
    
    detail_urls = set()
    page_urls = set()
    res = requests.get(args.index_url.format(1))
    if res.ok:
        soup = BeautifulSoup(res.content, "lxml")
        page_urls.update([urllib.parse.urljoin(args.index_url, li.a["href"]) for li in soup.find("ul", id="pageNav").find_all("li")[1:]])
        detail_urls.update(get_detail_urls(soup, args.index_url))
    
        for page_url in page_urls:
            time.sleep(1)
            res = requests.get(page_url)
            if res.ok:
                soup = BeautifulSoup(res.content, "lxml")
                detail_urls.update(get_detail_urls(soup, args.index_url))

    for i, (detail_url, title) in enumerate(sorted(detail_urls)):
        m = RE_DATE_URL.search(detail_url)
        if m:
            target_date = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
            target_detail_filename = os.path.join(args.work_dir, DEFAULT_FILENAME_DETAIL.format(target_date))
            if os.path.exists(target_detail_filename):
                logger.info("({:03d}/{:03d}) skip: ({:%Y-%m-%d}) {}".format(i + 1, len(detail_urls), target_date, title))
                continue

            time.sleep(1)
            res = requests.get(detail_url)
            if res.ok:
                logger.info("({:03d}/{:03d}) get : ({:%Y-%m-%d}) {}".format(i + 1, len(detail_urls), target_date, title))
                with open(target_detail_filename, "wb") as fp:
                    fp.write(res.content)
    
    processed_date = set()
    if os.path.exists(args.processed_list_filename):
        with open(args.processed_list_filename) as fp:
            processed_date.update([datetime.datetime.strptime(l, "%Y%m%d\n").date() for l in fp.readlines() if len(l.strip())])
    
    detail_infos = dict() # key: date, value: DetailInfo
    for target_fn in sorted(pathlib.Path(args.work_dir).glob("*.html")):
        target_date = datetime.datetime.strptime(str(target_fn.name), "%Y-%m-%d.html").date()
        if target_date in processed_date:
            logger.info("skip : {:%Y-%m-%d}".format(target_date))
            continue
        
        logger.info("start: {:%Y-%m-%d}".format(target_date))
        soup = BeautifulSoup(open(target_fn).read(), "lxml")
        detail_info = DetailInfo(
                target_date,
                soup.h3.text,
                soup.find("div", "guestTop").text.strip().split("：")[-1],
                )
        detail_infos[target_date] = detail_info
        
        for shop_li in soup.find("div", "shopInfo").find_all("li"):
            shop_info = ShopInfo(shop_li)
            detail_info.shop_infos.append(shop_info)
    
        # logger.debug(detail_info)
    
    if os.path.exists(args.oauth_json_filename):
        from oauth2client.service_account import ServiceAccountCredentials
        import gspread
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(args.oauth_json_filename, scope)
        gc = gspread.authorize(credentials)
        gwb = gc.open(os.path.splitext(args.output_fn)[0])

        gws = gwb.worksheet(args.sn_shop_info)
        if 0 == gws.row_count:
            logger.info("(gs) write header")
            gws.append_row([
                     "date",
                     "title"	,
                     "guest",
                     "category",
                     "name",
                     "detail",
                     "comment",
                     "goto map",
                    ])
        counter = 0
        for target_date, detail_info in sorted(detail_infos.items()):
            for shop_info in detail_info.shop_infos:
                if counter:
                    time.sleep(2)
                logger.info("(gs) write {:%Y-%m-%d} {}".format(target_date, shop_info.name))
                gws.append_row([
                        "{:%Y-%m-%d}".format(detail_info.target_date),
                        detail_info.title,
                        detail_info.guest,
                        shop_info.category,
                        '=HYPERLINK("{}", "{}")'.format(shop_info.url_site, shop_info.name) if shop_info.url_site else shop_info.name,
                        shop_info.detail,
                        shop_info.comment,
                        '=HYPERLINK("{}", "■")'.format(shop_info.url_map) if shop_info.url_map else "",
                        ], value_input_option='USER_ENTERED')
                counter += 1

    with open(args.processed_list_filename, "a") as fp:
        for target_date in sorted(detail_infos.keys()):
            fp.write("{:%Y%m%d}\n".format(target_date))
        
if __name__ == "__main__":
    main()