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
import logging.config
# import logging.config
import re
import sys
import urllib
import time

DEFAULT_URL_INDEXS = [
        "https://pannofes.jp/bakeries/",
        "https://pannofes.jp/bakeries/page/2/",
        "https://pannofes.jp/bakeries/page/3/",
        "https://pannofes.jp/bakeries/page/4/",
        "https://pannofes.jp/bakeries/page/5/",
        ]

logging.config.fileConfig('logging.config', disable_existing_loggers=False)
logger = logging.getLogger(__name__)

class ShopInfo(object):
    def __init__(self,):
        self.id = None
        self.detail_url = None
        self.name = None
        self.address = None
        self.address_url = None
        self.business_hours = None
        self.store_holidays = None
        self.site_url = None
        self.is_first = False
        self.desc = None
        self.image_urls = set()

    def __repr__(self):
        return str(self.__dict__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=pathlib.Path, default=pathlib.Path("out"))
    parser.add_argument("--output_fn", type=pathlib.Path, default=pathlib.Path("_pannofes.xlsx"))
    parser.add_argument("--work_dir", type=pathlib.Path, default=pathlib.Path("html"))
    parser.add_argument("--processed_list_filename", type=pathlib.Path, default=pathlib.Path("_processed_shop_names.txt"))
    parser.add_argument("--oauth_json_filename", 
                        default=os.path.join(
                                os.path.dirname(os.path.abspath(sys.argv[0])),
                                "cred.json"))
    parser.add_argument("--sn_shop_info", default="2019.akarenga")
    args = parser.parse_args()
    
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    if not os.path.exists(args.work_dir):
        os.makedirs(args.work_dir)
    
    detail_urls = set()
    for index_url in DEFAULT_URL_INDEXS:
        time.sleep(1)
        res = requests.get(index_url)
        if res.ok:
            soup_index = BeautifulSoup(res.content, "html5lib", from_encoding=res.apparent_encoding)
            detail_urls.update([li.a["href"] for li in soup_index.select_one("#bakery_list").ul.find_all("li")])

    processed_shop_names = set()
    if args.processed_list_filename.exists():
        with args.processed_list_filename.open() as fp:
            processed_shop_names.update([l.strip() for l in fp.readlines() if len(l.strip())])

    for detail_url in detail_urls:
        id = urllib.parse.urlsplit(detail_url).path.split("/")[-2]
        work_filename = args.work_dir / ("{}.html".format(id))
        if work_filename.exists():
            logger.info("exists: {}".format(id))
        else:
            time.sleep(1)
            res = requests.get(detail_url)
            if res.ok:
                work_filename.write_bytes(res.content)
                logger.info("store : {}".format(id))
    
    shop_infos = list() # ShopInfo
    for target_fn in sorted(pathlib.Path(args.work_dir).glob("*.html")):
        id = target_fn.stem
        if id in processed_shop_names:
            logger.info("skip : {}".format(id))
            continue
        
        logger.info("start: {}".format(id))
        soup = BeautifulSoup(target_fn.open(errors="backslashreplace").read(), "html5lib")
        si = ShopInfo()
        si.id = id
        si.detail_url = "https://pannofes.jp/bakery/{}/".format(id)
        info = soup.find("section", "bakery-info")
        for dt in info.find_all("dt"):
            title = dt.text
            dd = dt.find_next("dd")
            value = dd.text
            
            if title == "店名":
                if -1 < value.find("<初出店>"):
                    si.is_first = True
                    si.name = value.replace("<初出店>", "")
                else:
                    si.name = value
            elif title == "住所":
                si.address = value
                if dd.a:
                    si.address_url = dd.a["href"]
            elif title == "営業時間":
                si.business_hours = "\n".join(value.split())
            elif title == "店休日":
                si.store_holidays = "\n".join(value.split("・"))
            elif title == "web":
                si.site_url = value
            else:
                logger.warning("unknown title: {}={} in {}".format(title, value, detail_url))
        
        si.image_urls.update([img["src"] for img in soup.select("img[src*=uploads]")])
        si.desc = "\n".join([l for l in soup.find("div", "post-block").get_text("\n").splitlines() if len(l.strip())])
        shop_infos.append(si)
    
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
                    "初?",
                    "店名",
                    "URL",
                    "住所",
                    "営業時間",
                    "店休日",
                    "紹介",
                    ])
        counter = 0
        for shop_info in shop_infos:
            if counter:
                time.sleep(2)
            logger.info("(gs) write {}".format(shop_info.name))
            gws.append_row([
                    "x" if shop_info.is_first else "",
                    '=HYPERLINK("{}", "{}")'.format(shop_info.detail_url, shop_info.name) if shop_info.detail_url else shop_info.name,
                    '=HYPERLINK("{}", "■")'.format(shop_info.site_url) if shop_info.site_url else "",
                    '=HYPERLINK("{}", "{}")'.format(shop_info.address_url, shop_info.address) if shop_info.address_url else shop_info.address,
                    shop_info.business_hours,
                    shop_info.store_holidays,
                    shop_info.desc,
                    ] + ['=IMAGE("{}")'.format(image_url) for image_url in shop_info.image_urls], value_input_option='USER_ENTERED')
            counter += 1
        
            with args.processed_list_filename.open("a") as fp:
                fp.write(shop_info.id + "\n")
        
if __name__ == "__main__":
    main()