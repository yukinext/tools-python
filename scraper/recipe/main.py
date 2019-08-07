#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  6 21:30:16 2019

@author: yuki_next
"""
import argparse
import copy
import datetime
import requests
from bs4 import BeautifulSoup
import bs4
import logging
import yaml
import collections
import os
import pathlib
import sys
import json
import re
import urllib
import time

import jinja2
from evernote.api.client import EvernoteClient
import evernote.edam.type.ttypes as Types
import evernote.edam.notestore.ttypes as NSTypes

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

class EvernoteTransrator(object):
    default_tag_names = ["recipe", "レシピ"]
    
    _template = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
<h1><a href="{{ recipe.detail_url }}">{{ recipe.cooking_name }}</a></h1>
<h2>材料</h2>
<ul>
{%- for material in recipe.materials %}
    <li>
        <div>{{ material }}</div>
    </li>
{%- endfor %}
</ul>
<h2>作り方</h2>
<ul>
{%- for recipe_step in recipe.recipe_steps %}
    <li>
        <div>{{ recipe_step }}</div>
    </li>
{%- endfor %}
</ul>
</en-note>
"""

    def __init__(self, recipe, site_config):
        assert isinstance(recipe, Recipe)
        self.recipe = recipe
        self.site_config = site_config

    @property
    def title(self):
        return "{}「{}」 {:%Y.%m.%d}".format(self.recipe.program_name, self.recipe.cooking_name, self.recipe.program_date)

    @property
    def body(self):
        return jinja2.Template(EvernoteTransrator._template).render(recipe=self.recipe)
    
    @property
    def tag_names(self):
        ret = set(EvernoteTransrator.default_tag_names)
        ret.add(self.recipe.program_name)
        ret.add("{:%Y.%m.%d}".format(self.recipe.program_date))
        if self.site_config.get("tag_names"):
            ret.update(self.site_config["tag_names"])
        return ret
    
class Recipe(object):
    def __init__(self):
        self.id = None
        self.detail_url = None
        self.cooking_name = None # 料理名
        self.program_name = None # 番組名
        self.program_date = datetime.date.today() # 番組日付
        self.materials = list() # 材料
        self.recipe_steps = list() # 作り方
    
def proc_nhk_umai(args, site_config):
    program_name = site_config["program_name"]
    cache_dir = args.work_dir / "nhk_umai"
    if site_config.get("cache_dir"):
        cache_dir = args.work_dir / site_config["cache_dir"]
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    recipes = dict() # key: Recipe.id, value: Recipe
    for entry_url in site_config["entry_urls"]:
        res = requests.get(entry_url)
        if res.ok:
            soup = BeautifulSoup(res.content, "lxml")
            links = [a for a in soup.find_all("a") if a.img]
            for link in links:
                recipe = Recipe()
                recipe.detail_url = urllib.parse.urljoin(entry_url, link["href"])
                recipe.id = int(urllib.parse.splitvalue(recipe.detail_url)[1])
                recipe.program_name = program_name
                recipes[recipe.id] = recipe
                
                m = re.match(r".*?(\d{6}).*", pathlib.Path(link.img["src"]).name)
                if m:
                    yymmdd = m.groups()[0]
                    logger.debug("program_date:{}".format(yymmdd))
                    recipe.program_date = datetime.date(year=2000 + int(yymmdd[0:2]), month=int(yymmdd[2:4]), day=int(yymmdd[4:6]))

    processed_recipe_ids = set()
    processed_list_filename = args.work_dir / "_nhk_umai{}".format(args.processed_list_filename_postfix)
    if site_config.get("processed_list_filename"):
        processed_list_filename = pathlib.Path(site_config["processed_list_filename"])
        
    if processed_list_filename.exists():
        with processed_list_filename.open() as fp:
            processed_recipe_ids.update([int(l) for l in fp.readlines() if len(l.strip())])

    def is_existed_recipe(recipe):
        assert isinstance(recipe, Recipe)
        return (cache_dir / str(recipe.id)).exists()
    
    recipes_num = len(recipes)
    for i, recipe in enumerate(recipes.values()):
        if is_existed_recipe(recipe):
            logger.info("({:05d}/{:05d}) skip: {:d}".format(i + 1, recipes_num, recipe.id))
            continue

        time.sleep(1)
        res = requests.get(recipe.detail_url)
        if res.ok:
            logger.info("({:05d}/{:05d}) get: {:d}".format(i + 1, recipes_num, recipe.id))
            (cache_dir / str(recipe.id)).open("wb").write(res.content)
            

    for target_fn in sorted(cache_dir.glob("[!_*]*"), key=lambda k: int(str(k.stem))):
        if not target_fn.stem.isdigit():
            logger.info("skip file : {}".format(target_fn.name))
            continue
        
        recipe_id = int(target_fn.stem)
        if recipe_id in processed_recipe_ids:
            logger.info("skip : {:d}".format(recipe_id))
            continue
        
        try:
            logger.info("start : {:d}".format(recipe_id))
            soup = BeautifulSoup(target_fn.open("r", errors="ignore").read(), "lxml")
            for cooking_name_node in soup.find_all("h4"):
                recipe = copy.deepcopy(recipes[recipe_id])
                recipe.cooking_name = cooking_name_node.text
                
                material_title_node = cooking_name_node.parent.find(text="材料")
                recipe_steps_title_node = cooking_name_node.parent.find(text="作り方")

                recipe.materials = [material[1:] if material.startswith("・") else material for material in material_title_node.parent.find_next_sibling().text.splitlines() if len(material.strip())]
                recipe.recipe_steps = [recipe_step for recipe_step in recipe_steps_title_node.parent.find_next_sibling().text.splitlines() if len(recipe_step.strip())]
                
                if len(recipe.materials) == 0:
                    m_buf = list()
                    for material in material_title_node.parent.next_siblings:
                        if material == recipe_steps_title_node.parent:
                            break
                        if isinstance(material, bs4.NavigableString):
                            for m in material.replace("\u3000：", "：").replace("\u3000", "\n").strip().splitlines():
                                if len(m):
                                    if m.startswith("・"):
                                        m_buf.append(m[1:])
                                    else:
                                        m_buf.append(m)
                    recipe.materials = m_buf
                
                if len(recipe.recipe_steps) == 0:
                    recipe.recipe_steps = [recipe_step.strip() for recipe_step in recipe_steps_title_node.parent.next_siblings if isinstance(recipe_step, bs4.NavigableString) and len(recipe_step.strip())]
                
                if len(recipe.recipe_steps) == 0:
                    r_buf = list()
                    for recipe_step in recipe_steps_title_node.parent.next_siblings:
                        if isinstance(recipe_step, bs4.NavigableString):
                            if len(recipe_step.strip()):
                                r_buf.append(recipe_step.strip())
                        else:
                            r_ = recipe_step.text.strip()
                            if len(r_):
                                for r in r_.splitlines():
                                    if len(r):
                                        r_buf.append(r)
                    recipe.recipe_steps = r_buf
                
                yield processed_list_filename, recipe
        except AttributeError:
            logger.exception("not expected format.")
            logger.info("remove : {:d}".format(recipe_id))
            new_target_fn = _get_new_fn(target_fn, "_", 1)
            logger.info("rename : {} -> {}".format(target_fn.name, new_target_fn.name))
            target_fn.rename(new_target_fn)
        
def store_evernote(recipes, args, site_config, evernote_cred, is_note_exist_check=True):
    client = EvernoteClient(token=evernote_cred["developer_token"], sandbox=evernote_cred["is_sandbox"])
    note_store = client.get_note_store()
    
    notebook_name = evernote_cred["notebook_name"]
    notebooks = note_store.listNotebooks()
    target_notebook = None
    for notebook in notebooks:
        if notebook_name == notebook.name:
            target_notebook = notebook
            break
    
    if target_notebook is None:
        logger.info("create notebook: {}".format(notebook_name))
        target_notebook = Types.Notebook()
        target_notebook.name = notebook_name
        target_notebook = note_store.createNotebook(target_notebook)

    for processed_list_filename, recipe in recipes(args, site_config):
        trans = EvernoteTransrator(recipe, site_config)
        note_title = trans.title

        if is_note_exist_check:
            filter = NSTypes.NoteFilter()
            filter.notebookGuid = target_notebook.guid        
            resultSpec = NSTypes.NotesMetadataResultSpec()
            resultSpec.includeTitle = True
            metalist = note_store.findNotesMetadata(filter, 0, 10, resultSpec)
    
            for meta_ in metalist.notes:
                if note_title == meta_.title:
                    logger.info("skip: {} exists.".format(note_title))
                    continue
        
        logger.info("create note: {}".format(note_title))
        note = Types.Note(title=note_title, content=trans.body, notebookGuid=target_notebook.guid)
        note.tagNames = trans.tag_names
        note_store.createNote(note)
        
        with processed_list_filename.open("a") as fp:
            fp.write("{}\n".format(recipe.id))
        
        time.sleep(1)

def _get_new_fn(from_path, prefix_mark, prefix_times):
    prefix = prefix_mark * prefix_times
    to_path = from_path.with_name(prefix + from_path.name)
    if to_path.exists():
        return _get_new_fn(from_path, prefix_mark, prefix_times + 1)
    return to_path

def _get_evernote_credential(credential_json_filename):
    if not credential_json_filename.exists():
        logger.debug("credential file not found: {}".format(credential_json_filename))
        return None
    
    j = None
    with credential_json_filename.open("r") as fp:
        j = json.load(fp)
    
    if not "evernote" in j:
        logger.debug("\"evernote\" not found in credential file: {}".format(credential_json_filename))
        return None
    
    cred = j["evernote"]
    if "enable" in cred and cred["enable"] == False:
        logger.debug("\"evernote.enable\" is disable in credential file: {}".format(credential_json_filename))
        return None
    
    if all(key in cred for key in ("sandbox", "developer_token", "notebook_name")):
        return {
            "is_sandbox": cred["sandbox"],
            "developer_token": cred["developer_token"],
            "notebook_name": cred["notebook_name"],
        }
    else:
        logger.debug('"sandbox" or "developer_token" or "notebook_name" are not exists in "evernote" section in credential file: {}'.format(credential_json_filename))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sites", nargs="*", help="site name in config yaml file. no input is select all sites")
    parser.add_argument("--config-yaml-filename", default=pathlib.Path(sys.argv[0]).parent / "config.yml", type=pathlib.Path)
    parser.add_argument("--work-dir", default=pathlib.Path(sys.argv[0]).parent / ".work_recipes", type=pathlib.Path, help="working directory")
    parser.add_argument("--credential-json-filename", default=pathlib.Path(sys.argv[0]).parent / "cred.json", type=pathlib.Path)
    parser.add_argument("--skip-existed-note", action="store_true", help="check existed note and if existed skip.")
    parser.add_argument("--processed-list-filename-postfix", default="_processed_data.txt")

    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    
    args.config_yaml_filename
    config = yaml.load(args.config_yaml_filename.open("r").read())
    evernote_cred = _get_evernote_credential(args.credential_json_filename)
    if args.sites is None or len(args.sites) == 0:
        args.sites = [key for key in config.keys()]
    
    for site in args.sites:
        if site in config:
            recipe_generator = eval("proc_{}".format(site))
            store_evernote(recipe_generator, args, config[site], evernote_cred, is_note_exist_check=not args.skip_existed_note)
        else:
            logger.warn("not exist: {}".format(site))
        
                    

if __name__ == "__main__":
    main()