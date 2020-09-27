#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 27 18:08:25 2020

@author: yuki_next
"""

import argparse
import pathlib
import bs4
import re
import html


class Folder(object):
    def __init__(self, name, add_date=None, last_modified=None, personal_toolbar_folder=None):
        self.parent = None
        self.name = name
        self.add_date = add_date
        self.last_modified = last_modified
        self.personal_toolbar_folder = personal_toolbar_folder
        self.contents = []

    @property
    def absolute_name(self):
        if self.parent:
            return f"{self.parent.absolute_name}/{self.name}"
        return ""

    def add(self, node):
        self.contents.append(node)
        node.parent = self
        
    def to_string(self, depth=0, indent_char="    "):
        attributes = dict(
                ADD_DATE=self.add_date,
                LAST_MODIFIED=self.last_modified,
                PERSONAL_TOOLBAR_FOLDER=self.personal_toolbar_folder)
        attribute = ' '.join(f'{k}="{v}"' for (k, v) in attributes.items() if v is not None)
        ret = []
        if self.parent:
            ret.append(f"{indent_char * depth}<DT><H3 {attribute}>{html.escape(self.name).replace('&#x27;', '&#39;')}</H3>")
        ret.append(f"{indent_char * depth}<DL><p>")
        for content in self.contents:
            ret.append(content.to_string(depth + 1, indent_char))
        ret.append(f"{indent_char * depth}</DL><p>")
        
        return "\n".join(ret)
        
        

class Link(object):
    def __init__(self, name, href, add_date=None, last_modified=None, icon=None):
        self.parent = None
        self.name = name
        self.href = href
        self.add_date = add_date
        self.last_modified = last_modified
        self.icon = icon


    def to_string(self, depth=0, indent_char="    "):
        attributes = dict(
                HREF=self.href,
                ADD_DATE=self.add_date,
                LAST_MODIFIED=self.last_modified,
                ICON=self.icon)
        attribute = ' '.join(f'{k}="{v}"' for (k, v) in attributes.items() if v is not None)
        return f"{indent_char * depth}<DT><A {attribute}>{html.escape(self.name).replace('&#x27;', '&#39;')}</A>"

def parse_chrome(args):
    target_file_path = args.bookmark_file_path
    encoding = args.bookmark_file_encoding
    
    # cleanup
    content = target_file_path.read_text(encoding=encoding)
    content = content.replace("<p>", "")
    content = re.sub(r"<DT>(.*)", r"<DT>\1</DT>", content)
    soup = bs4.BeautifulSoup(content, "lxml")
    root_node = soup.dl
    root_folder = Folder("Bookmarks")

    def _crawl_node(parent_folder, content_node):
        for node in content_node.find_all("dt", recursive=False):        
            if node.h3:
                folder_node = node.h3
                folder = Folder(
                        folder_node.text,
                        add_date=folder_node.get("add_date"),
                        last_modified=folder_node.get("last_modified"),
                        personal_toolbar_folder=folder_node.get("personal_toolbar_folder"),
                        )
                parent_folder.add(folder)
                _crawl_node(folder, folder_node.parent.find_next_sibling("dl"))
                continue
            if node.a:
                link_node = node.a
                parent_folder.add(Link(
                        link_node.text,
                        link_node.get("href"),
                        add_date=link_node.get("add_date"),
                        last_modified=link_node.get("last_modified"),
                        icon=link_node.get("icon"),
                        ))
                continue
    
    _crawl_node(root_folder, root_node)
        
    folder_cache = dict() # key: absolute_name, value: Folder
    new_root_folder = Folder("New Bookmarks")
    folder_cache[root_folder.absolute_name] = new_root_folder
    
    def _crawl_node2(parent_folder):
        for content in parent_folder.contents:
            if isinstance(content, Folder):
                if not content.absolute_name in folder_cache:
                    new_folder = Folder(
                            content.name,
                            content.add_date,
                            content.last_modified,
                            content.personal_toolbar_folder,
                            )
                    folder_cache[content.absolute_name] = new_folder
                    folder_cache[content.parent.absolute_name].add(new_folder)
                    
                _crawl_node2(content)
                continue
            if isinstance(content, Link):
                new_link = Link(
                        content.name,
                        content.href,
                        content.add_date,
                        content.last_modified,
                        content.icon,
                        )
                folder_cache[content.parent.absolute_name].add(new_link)
                continue

    _crawl_node2(root_folder)

    return new_root_folder
    
    

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bookmark_file_path", type=pathlib.Path)
    parser.add_argument("bookmark_output_file_path", type=pathlib.Path)
    parser.add_argument("--target_format", choices=["chrome"], default="chrome")
    parser.add_argument("--bookmark_file_encoding", default="utf-8")

    args = parser.parse_args()
    
    if args.target_format == "chrome":
        root_folder = parse_chrome(args)
        output = f"""<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
     It will be read and overwritten.
     DO NOT EDIT! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
{root_folder.to_string(0)}
"""
        args.bookmark_output_file_path.write_text(output.replace("\n", "\r\n"), encoding=args.bookmark_file_encoding)

if __name__ == "__main__":
    main()