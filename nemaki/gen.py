#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  4 10:45:28 2019

@author: yuki_next
"""

import datetime
import argparse
import dateutil.relativedelta

TEMPLATE_WEEKDAY = {
        0:"昼晩 白さら", # 月
        1:"朝 、昼 {}、晩 白さら", # 火
        2:"晩 {}", # 水
        3:"朝 、昼 {}、晩 白さら", # 木
        4:"昼晩 {}", # 金
        5:"朝 、昼 {}、晩 白さら", # 土
        6:"晩 {}", # 日
        }

NEMAKI_CHOICES = ["桃ふわ", "白ふわ"]

def valid_date(s):
    try:
        return datetime.datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("start_date", type=valid_date, help="The Start Date - format YYYYMMDD", default=datetime.date.today(), nargs="?")
    parser.add_argument("end_date", type=valid_date, nargs="?")
    parser.add_argument("--start", choices=NEMAKI_CHOICES, default=NEMAKI_CHOICES[0])
    args = parser.parse_args()
    
    if args.end_date is None:
        args.end_date = args.start_date + dateutil.relativedelta.relativedelta(days=-args.start_date.day, months=1)
    
    nemaki_offset = NEMAKI_CHOICES.index(args.start)
    buf = list()
    for offset in range((args.end_date - args.start_date).days + 1):
        target_date = args.start_date + datetime.timedelta(days=offset)
        w = target_date.weekday()
        l = TEMPLATE_WEEKDAY[w].format(NEMAKI_CHOICES[(offset + nemaki_offset) % len(NEMAKI_CHOICES)])
        buf.append("{:%Y%m%d} {}".format(target_date, l))
    
    buf.reverse()
    for l in buf:
        print(l)

if __name__ == "__main__":
    main()