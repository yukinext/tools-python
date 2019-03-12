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
import re
import sys
import urllib
import time

DEFAULT_URL_INDEX = "http://www.rnc.co.jp/tv/siawase/?page_id=100"
DEFAULT_URL_DETAIL_PAGE = "http://www.rnc.co.jp/tv/siawase/?p={page_id:d}"
DEFAULT_FILENAME_DETAIL = "{:06d}.html"
RE_DATE_ = re.compile(r"(\d+)\D+(\d+)\D+(\d+)\D+")

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
    def __init__(self, page_id, target_date):
        self.page_id = page_id
        self.target_date = target_date
        self.shop_infos = list() # ShopInfo

    def __repr__(self):
        return str(self.__dict__)

class ShopInfo(object):
    def __init__(self, category, name, detail, url_site=None, url_map=None):
        self.category = category
        self.name = name
        self.detail = detail
        self.url_site = url_site
        self.url_map = url_map

    def __repr__(self):
        return str(self.__dict__)

def get_detail_urls(soup, base_url):
    return [(urllib.parse.urljoin(base_url, h3.a["href"]), h3.a.text) for h3 in soup.find("div", "contentsIn").find_all("h3")]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target_bn_index_url", nargs="?")
    parser.add_argument("--is_skip_get_detail_page", action="store_true")
    parser.add_argument("--is_skip_write_to_gspread", action="store_true")
    parser.add_argument("--output_dir", default="out")
    parser.add_argument("--output_fn", default="_ShiawaseKibun.xlsx")
    parser.add_argument("--work_dir", default="html")
    parser.add_argument("--index_url", default=DEFAULT_URL_INDEX)
    parser.add_argument("--processed_list_filename", default="_processed_data.txt")
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

    if args.is_skip_get_detail_page:
        logger.info("skip get detail page from web.")
    else:
        def get_detail_urls(bn_index_url):
            res = requests.get(bn_index_url)
            if res.ok:
                soup = BeautifulSoup(res.content, "lxml")
                return [
                        (int(urllib.parse.parse_qs(urllib.parse.splitquery(div.a["href"])[1])["p"][0]),
                         div.a["href"])
                        for div in soup.find_all("div", "btitle")]
            
        
        detail_urls = set() # (page_id, url)
        bn_index_urls = list()
        
        if args.target_bn_index_url:
            bn_index_urls.append(args.target_bn_index_url)
        else:
            res = requests.get(args.index_url)
            if res.ok:
                soup = BeautifulSoup(res.content, "lxml")
                bn_index_urls.extend([a["href"] for a in soup.find("ul", "backnumber").find_all("a")])
    
        for bn_index_url in bn_index_urls:
            tmp_detail_urls = get_detail_urls(bn_index_url)
            logger.info("append: {}".format(tmp_detail_urls))
            detail_urls.update(tmp_detail_urls)
    
        for i, (page_id, detail_url) in enumerate(sorted(detail_urls)):
            target_detail_filename = os.path.join(args.work_dir, DEFAULT_FILENAME_DETAIL.format(page_id))
            if os.path.exists(target_detail_filename):
                logger.info("({:05d}/{:05d}) skip: {:d}".format(i + 1, len(detail_urls), page_id))
                continue
    
            time.sleep(1)
            res = requests.get(detail_url)
            if res.ok:
                logger.info("({:05d}/{:05d}) get: {:d}".format(i + 1, len(detail_urls), page_id))
                with open(target_detail_filename, "wb") as fp:
                    fp.write(res.content)
    
    processed_page_ids = set()
    if os.path.exists(args.processed_list_filename):
        with open(args.processed_list_filename) as fp:
            processed_page_ids.update([int(l) for l in fp.readlines() if len(l.strip())])
    
    detail_infos = dict() # key: date, value: DetailInfo
    for target_fn in sorted(pathlib.Path(args.work_dir).glob("*.html")):
        target_page_id = int(target_fn.stem)
        if target_page_id in processed_page_ids:
            logger.info("skip : {:d}".format(target_page_id))
            continue
        
        logger.info("start : {:d}".format(target_page_id))
        soup = BeautifulSoup(open(target_fn).read(), "lxml")
        target_date = None
        m = RE_DATE_.search(soup.strong.text)
        if m:
            target_date = datetime.date(*[int(s) for s in m.groups()])
        detail_info = DetailInfo(
                target_page_id,
                target_date,
                )
        detail_infos[target_page_id] = detail_info
        tables = soup.find_all("table")[3:-1]
        
        category = None
        for t in tables:
            if not "class" in t.attrs: # title table
                strongs = [s.text.strip() for s in t.find_all("strong") if len(s.text.strip())]
                if len(strongs) == 1:
                    category = strongs[0]
                elif 1 < len(strongs): # 1st category
                    category = strongs[1]
            else: # shop table
                # ls = t.find("td", "style21").text.splitlines() # page_id: 3871 is not valid
                tds = t.find_all("td")
                ls = [""]
                for td in tds:
                    if td.strong and len(td.strong.text.strip()):
                        ls = [l.strip() for l in td.text.splitlines()]
                        break
                if -1 < ls[0].find("『"): # shop info
                    name = ls[0]
                    if ls[0].startswith("『"):
                        name = ls[0][1:-1]
                    detail = "\n".join([l for l in ls[1:] if len(l)])
                    detail_info.shop_infos.append(ShopInfo(category, name, detail))
        logger.debug(detail_info)

    if args.is_skip_write_to_gspread:
        logger.info("skip write to gspread.")
    else:
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
                         "id",
                         "date",
                         "category",
                         "name",
                         "detail",
                         "goto map",
                        ])
            with open(args.processed_list_filename, "a") as fp:
                counter = 0
                for target_page_id, detail_info in sorted(detail_infos.items(), key=lambda v: v[1].target_date):
                    for shop_info in detail_info.shop_infos:
                        if counter:
                            time.sleep(2)
                        logger.info("(gs) write {} {:%Y-%m-%d} {}".format(target_page_id, detail_info.target_date, shop_info.name))
                        gws.append_row([
                                '=HYPERLINK("{}", "{}")'.format(DEFAULT_URL_DETAIL_PAGE.format(page_id=target_page_id), target_page_id),
                                "{:%Y-%m-%d}".format(detail_info.target_date),
                                shop_info.category,
                                '=HYPERLINK("{}", "{}")'.format(shop_info.url_site, shop_info.name) if shop_info.url_site else shop_info.name,
                                shop_info.detail,
                                '=HYPERLINK("{}", "■")'.format(shop_info.url_map) if shop_info.url_map else "",
                                ], value_input_option='USER_ENTERED')
                        counter += 1
                    fp.write("{:d}\n".format(target_page_id))
        
if __name__ == "__main__":
    main()