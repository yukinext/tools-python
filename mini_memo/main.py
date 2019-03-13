#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 13 07:12:40 2019

@author: yuki_next
"""

import argparse
import datetime
import pathlib
import logging
import os
import sys
import collections
import yaml

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

yaml.add_representer(collections.OrderedDict, lambda dumper, instance: dumper.represent_mapping('tag:yaml.org,2002:map', instance.items()))
yaml.add_representer(type(None), lambda dumper, instance: dumper.represent_scalar('tag:yaml.org,2002:null', "~"))
yaml.add_constructor('tag:yaml.org,2002:map', lambda loader, node: collections.OrderedDict(loader.construct_pairs(node)))

# https://pyyaml.org/wiki/PyYAMLDocumentation#Constructorsrepresentersresvers
class Message(yaml.YAMLObject):
    yaml_tag = "!Message"
    
    def __init__(self, msg, created=datetime.datetime.now()):
        self.msg = msg
        self.created = created
    
    def __repr__(self):
        return "{!s}(msg={!r), created={!r})".format(self.__class__.__name__, self.msg, self.created)
    
    
def proc_insert(args):
    messages = dict() # key: date, value: list() Message
    
    store_filename = args.work_dir / args.store_file
    if store_filename.exists():
        with store_filename.open("r") as fp:
            messages = yaml.load(fp)

    today = datetime.date.today()
    if not today in messages:
        messages[today] = list()
    messages[today].append(Message(args.message))
    
    with store_filename.open("w") as fp:
        yaml.dump(messages, stream=fp, allow_unicode=True, default_flow_style=False)
    
def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--work-dir", default=pathlib.Path("~/.mini_memo/").expanduser(), type=pathlib.Path, help="working directory")
    common_parser.add_argument("--store-file", default="memo_{:%Y%m}.yaml".format(datetime.date.today()), help="messages store file name.")

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    
    parser_insert = subparsers.add_parser("insert", parents=[common_parser], help="insert message", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser_insert.add_argument("message")
    parser_insert.set_defaults(handler=proc_insert)
    
    args = parser.parse_args()
    
    args.work_dir.mkdir(parents=True, exist_ok=True)
    
    if hasattr(args, "handler"):
        args.handler(args)

if __name__ == "__main__":
    main()