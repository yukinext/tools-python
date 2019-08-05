#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  4 10:45:28 2019

@author: yuki_next
"""

import datetime
import argparse
import dateutil.relativedelta
import string

TEMPLATE_WEEKDAY = {
        0:"昼晩 {}", # 月
        1:"朝 、昼 {}、晩 白さら", # 火
        2:"晩 紫さら", # 水
        3:"朝 、昼 {}、晩 白さら", # 木
        4:"昼晩 紫さら", # 金
        5:"朝 、昼 {}、晩 白さら", # 土
        6:"晩 紫さら", # 日
        }

NEMAKI_CHOICES = ["桃ふわ", "白ふわ"]

def valid_date(s):
    try:
        return datetime.datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)

def get_replace_fields_num(format_string):
    # num of "{}" (no name field)
    counter = 0
    for literal_text, field_name, format_spec, conversion in string.Formatter().parse(format_string):
        if field_name == "":
            counter += 1
    return counter

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("start_date", type=valid_date, help="The Start Date - format YYYYMMDD", default=datetime.date.today(), nargs="?")
    parser.add_argument("end_date", type=valid_date, nargs="?")
    parser.add_argument("--start", choices=NEMAKI_CHOICES, default=NEMAKI_CHOICES[0])
    args = parser.parse_args()
    
    if args.end_date is None:
        args.end_date = args.start_date + dateutil.relativedelta.relativedelta(days=-args.start_date.day, months=1)
    
    buf = list()
    nemaki_choices_counter = NEMAKI_CHOICES.index(args.start)
    for offset in range((args.end_date - args.start_date).days + 1):
        target_date = args.start_date + datetime.timedelta(days=offset)
        w = target_date.weekday()
        lw = TEMPLATE_WEEKDAY[w]
        fields_num = get_replace_fields_num(lw)
        tmp_nemaki_fields = list()
        for i in range(fields_num):
            tmp_nemaki_fields.append(NEMAKI_CHOICES[nemaki_choices_counter % len(NEMAKI_CHOICES)])
            nemaki_choices_counter += 1
        l = lw.format(*tmp_nemaki_fields)
        buf.append("{:%Y%m%d} {}".format(target_date, l))
    
    buf.reverse()
    for l in buf:
        print(l)

if __name__ == "__main__":
    main()