#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  6 21:30:16 2019

@author: yuki_next
"""
import argparse
import datetime
import logging
import logging.config
import logging.handlers
import yaml
import collections
import pathlib
import sys
import inspect
import json
import time
import dateutil.parser
import pprint
import pickle
import math

import recipe_crawler.models
import recipe_crawler.translators
import recipe_crawler.crawlers

from evernote.api.client import EvernoteClient
import evernote.edam.type.ttypes as Types
import evernote.edam.notestore.ttypes as NSTypes

import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

yaml.add_representer(collections.OrderedDict, lambda dumper, instance: dumper.represent_mapping('tag:yaml.org,2002:map', instance.items()))
yaml.add_representer(type(None), lambda dumper, instance: dumper.represent_scalar('tag:yaml.org,2002:null', "~"))
yaml.add_constructor('tag:yaml.org,2002:map', lambda loader, node: collections.OrderedDict(loader.construct_pairs(node)))

logging.config.dictConfig(yaml.safe_load(pathlib.Path('recipe_crawler_logging.yml').open("r").read()))
logger = logging.getLogger(__name__)

def create_enex(recipes, args, site_config):

    for recipe in recipes():
        trans = recipe_crawler.translators.EvernoteLocalEnexTranslator(recipe, site_config)
        
        yield recipe, trans.enex

def store_evernote(recipes, args, site_config, evernote_cred, is_note_exist_check=True):
    client = EvernoteClient(token=evernote_cred["developer_token"], sandbox=evernote_cred["is_sandbox"])
    note_store = None
    try:
        note_store = client.get_note_store()
    except:
        logger.error(sys.exc_info()[0])
    
    if note_store is None:
        logger.error("note store in Evernote is None")
        return

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

    # for processed_list_filename, recipe in recipes(args, site_config):
    for recipe in recipes():
        trans = recipe_crawler.translators.EvernoteTranslator(recipe, site_config)
        note_title = trans.title

        is_note_exist = False
        if is_note_exist_check:
            note_filter = NSTypes.NoteFilter()
            note_filter.notebookGuid = target_notebook.guid
            note_filter.words = note_title
            resultSpec = NSTypes.NotesMetadataResultSpec()
            resultSpec.includeTitle = True
            metalist = note_store.findNotesMetadata(note_filter, 0, 10, resultSpec)
    
            for meta_ in metalist.notes:
                if note_title == meta_.title:
                    logger.debug("skip: {} exists.".format(note_title))
                    is_note_exist = True
                    break
        if not is_note_exist:
            logger.info("create note: {}".format(note_title))
            resources, body = trans.body_resources
            attributes = trans.attributes
            note = Types.Note(title=note_title, content=body, resources=resources.values(), attributes=attributes, notebookGuid=target_notebook.guid)
            note.tagNames = trans.tag_names
            note_store.createNote(note)
            time.sleep(1)
            
        yield recipe
    

def change_tag_evernote(args, evernote_cred):
    client = EvernoteClient(token=evernote_cred["developer_token"], sandbox=evernote_cred["is_sandbox"])
    note_store = client.get_note_store()
    
    notebook_name = evernote_cred["notebook_name"]
    notebooks = note_store.listNotebooks()
    target_notebook = None
    for notebook in notebooks:
        if notebook_name == notebook.name:
            target_notebook = notebook
            break

    note_filter = NSTypes.NoteFilter()
    note_filter.notebookGuid = target_notebook.guid

    notes_per_page = 50
    note_list = note_store.findNotes(note_filter, 0, 1)
    note_num = note_list.totalNotes
    max_page_num = math.ceil(note_num / notes_per_page)
    note_num_digits = len(str(note_num))
    message_current_max = "({{:0{digits}d}}/{{:0{digits}d}})".format(digits=note_num_digits)
    for page_num in range(0, max_page_num):
        note_list = note_store.findNotes(note_filter, notes_per_page * page_num, notes_per_page * (page_num + 1))
        
        for i, note in enumerate(note_list.notes):
            logger.info((message_current_max + ": {}").format(notes_per_page * page_num + i + 1, note_num, note.title))
            current_tag_names = note_store.getNoteTagNames(note.guid)
            new_tag_names = set()
            for current_tag_name in current_tag_names:
                try:
                    program_date = dateutil.parser.parse(current_tag_name)
                    new_tag_names.add("{:%Y}".format(program_date))
                    new_tag_names.add("{:%Y.%m}".format(program_date))
                except:
                    new_tag_names.add(current_tag_name)
                    
            logger.info("change tags: {}->{}".format(current_tag_names, new_tag_names))
            note.tagGuids.clear()
            note.content = None
            note.resources = None
            note.tagNames = new_tag_names
            note_store.updateNote(note)

def store_local(store_dirname, recipe):
    pickle_filename = store_dirname / "{}.pickle".format(recipe.id)

    recipes = dict()

    if pickle_filename.exists():
        recipes.update(pickle.load(pickle_filename.open("rb")))

    recipes[recipe.cooking_name] = recipe

    with pickle_filename.open("wb") as fp:
        pickle.dump(recipes, fp)

def store_local_enex(store_dirname, program_title, enexs):
    merged_enex = recipe_crawler.translators.EvernoteLocalEnexTranslator.merge(enexs)
    output_filename = store_dirname / "{}.{:%Y%m%d}.enex".format(program_title, datetime.datetime.now())
    output_filename.write_text(merged_enex)

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
    root_dir = pathlib.Path(sys.argv[0]).parent
    parser.add_argument("sites", nargs="*", help="site name in config yaml file. no input is select all sites. if specified explicitly, it is executed regardless of the 'enable' value.")
    parser.add_argument("--view-config", action="store_true")
    parser.add_argument("--config-yaml-filename", default=root_dir / "recipe_crawler_config.yml", type=pathlib.Path)
    parser.add_argument("--work-dir", default=root_dir / ".work_recipes", type=pathlib.Path, help="working directory")
    parser.add_argument("--credential-json-filename", default=root_dir / "recipe_crawler_cred.json", type=pathlib.Path)
    parser.add_argument("--no-check-existed-note", action="store_true", help="no check existed notes and append new note. if do not check existed note and skip.")
    parser.add_argument("--processed-list-filename-postfix", default="_processed_data.txt")
    parser.add_argument("--use-local", action="store_true", help="store local enex file. do not sync cloud evernote")

    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    
    if not args.config_yaml_filename.exists():
        logger.error("not exists config file: {}".format(args.config_yaml_filename))
        return

    crawlers = [crawler_clazz() for _, crawler_clazz in inspect.getmembers(recipe_crawler.crawlers, inspect.isclass) if issubclass(crawler_clazz, recipe_crawler.crawlers.bases.RecipeCrawlerTemplate) and not inspect.isabstract(crawler_clazz)]
    crawlers_map = dict([(crawler.site_name, crawler) for crawler in crawlers])
    
    config = yaml.safe_load(args.config_yaml_filename.open("r").read())
    if args.view_config:
        view_results = dict()
        for site, site_config in config.items():
            if len(args.sites):
                for a_site in args.sites:
                    if not a_site in view_results:
                        view_results[a_site] = list()
                    if -1 < site.find(a_site):
                        view_results[a_site].append((site, site_config))
            else:
                if not "" in view_results:
                    view_results[""] = list()
                view_results[""].append((site, site_config))
        pprint.pprint(view_results)
        return
    
    evernote_cred = _get_evernote_credential(args.credential_json_filename)
    # change_tag_evernote(args, evernote_cred)

    if args.sites is None or len(args.sites) == 0:
        args.sites = [key for key in config.keys() if config[key].get("enable", True)] # True if 'enable' is omitted
    
    for site in args.sites:
        if site in config and site in crawlers_map:
            site_config = config[site]
            
            crawler = crawlers_map[site]
            crawler.init(args, site_config)
            recipe_pickle_dir = crawler.cache_dir / "_pickle"
            recipe_pickle_dir.mkdir(parents=True, exist_ok=True)
            
            if args.use_local:
                logger.info("store local enex")
                enexs = list()
                for recipe, (enex_title, enex) in create_enex(crawler.process, args, site_config):
                    store_local(recipe_pickle_dir, recipe)
                    enexs.append(enex)
                
                enex_dir = args.work_dir / "_enex"
                enex_dir.mkdir(parents=True, exist_ok=True)

                store_local_enex(enex_dir, site_config["program_name"], enexs)

                with crawler.processed_list_filename.open("a") as fp:
                    fp.write("{}\n".format(recipe.id))
            else:
                for recipe in store_evernote(crawler.process, args, site_config, evernote_cred, is_note_exist_check=not args.no_check_existed_note):
                    if recipe:
                        with crawler.processed_list_filename.open("a") as fp:
                            fp.write("{}\n".format(recipe.id))
                        
                        store_local(recipe_pickle_dir, recipe)
        else:
            logger.warning("not exist: {}".format(site))

if __name__ == "__main__":
    main()