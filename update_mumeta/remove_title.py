#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar 14 21:36:32 2021

@author: yuki_next
"""

import pathlib
import argparse

def command_mp4(args):
    from mutagen.mp4 import MP4
    for p in args.target_dir.glob("*.mp4"):
        print(p)
        tags = MP4(p)
        if "©nam" in tags:
            if ("na" in tags["©nam"]) or ("" in tags["©nam"]):
                print("  title is invalid: clear")
                tags.pop("©nam", None)
                tags.save()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target_dir", type=pathlib.Path, default=pathlib.Path("./"))
    parser.add_argument("--format", default="mp4", choices=["mp4"])
    
    args = parser.parse_args()
    
    if args.format == "mp4":
        command_mp4(args)
    

if __name__ == "__main__":
    main()