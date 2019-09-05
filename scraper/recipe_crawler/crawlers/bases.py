#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:18:51 2019

@author: yuki_next
"""

import pathlib
from bs4 import BeautifulSoup
import requests
import time
import chardet
import logging
import recipe_crawler.models

logger = logging.getLogger(__name__)

class RecipeCrawlerTemplate(object):
    site_name = ""
    _TABLE_REMOVE_KAKKO = str.maketrans({"「": "", "」": ""})
    _TABLE_REPLACE_MARUKAKKO = str.maketrans({"(": "（", ")":"）"})
    def __init__(self):
        pass

    def init(self, args, site_config):
        self.program_name = site_config["program_name"]
        self.cache_dir = args.work_dir / self.__class__.site_name
        if site_config.get("cache_dir"):
            self.cache_dir = args.work_dir / site_config["cache_dir"]
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
        self.entry_urls = site_config["entry_urls"]
        if site_config.get("is_expand_entry_urls", False):
            self.entry_urls = self._expand_entry_urls()
    
        self.processed_list_filename = args.work_dir / "_{}{}".format(self.__class__.site_name, args.processed_list_filename_postfix)
        if site_config.get("processed_list_filename"):
            self.processed_list_filename = pathlib.Path(site_config["processed_list_filename"])
        

    def process(self):
        logger.info("{}: proc start".format(self.__class__.site_name))
        
        recipes = dict() # key: Recipe.id, value: Recipe

        for entry_url in self.entry_urls:
            res = requests.get(entry_url, verify=False)
            if res.ok:
                soup = BeautifulSoup(res.content, "html5lib", from_encoding=res.apparent_encoding)
                recipes.update(self._get_recipe_overviews(soup, entry_url))

        processed_recipe_ids = set()
            
        if self.processed_list_filename.exists():
            with self.processed_list_filename.open() as fp:
                processed_recipe_ids.update([self._trans_to_recipe_id_from_str(l.strip()) for l in fp.readlines() if len(l.strip())])
        
        recipes_num = len(recipes)
        recipes_num_digits = len(str(recipes_num))
        message_current_max = "({{:0{digits}d}}/{{:0{digits}d}})".format(digits=recipes_num_digits)
        for i, recipe in enumerate(recipes.values()):
            if self._is_existed_recipe(recipe):
                logger.debug(("{} " + message_current_max + ": skip: {}").format(self.__class__.site_name, i + 1, recipes_num, recipe.id))
                continue
    
            time.sleep(1)
            res = requests.get(recipe.detail_url, verify=False)
            if res.ok:
                logger.info(("{} " + message_current_max + ": get : {}").format(self.__class__.site_name, i + 1, recipes_num, recipe.id))
                (self.cache_dir / str(recipe.id)).open("wb").write(res.content)
        # get detail recipe info
        for target_fn in sorted(self.cache_dir.glob("[!_|.*]*"), key=lambda k: self._sortkey_cache_filename(k)):
            if not self._is_valid_cache_filename(target_fn):
                logger.debug("{}: skip file : {}".format(self.__class__.site_name, target_fn.name))
                continue
            
            recipe_id = self._get_recipe_id_from_cache_file(target_fn)
            if recipe_id in processed_recipe_ids:
                logger.debug("{}: skip : {}".format(self.__class__.site_name, recipe_id))
                continue
            
            if not recipe_id in recipes:
                logger.warn("{}: not exists in overview. skip recipe id: {}".foramt(self.__class__.site_name, recipe_id))
                continue
            
            try:
                logger.info("{}: start : {}".format(self.__class__.site_name, recipe_id))
                content = target_fn.open("rb").read()
                soup = BeautifulSoup(content, "html5lib", from_encoding=chardet.detect(content)["encoding"])
                
                for detail_recipe in self._recipe_details_generator(soup, recipes[recipe_id]):
                    yield detail_recipe
                
            except AttributeError:
                logger.exception("not expected format.")
                logger.info("{}: remove : {}".format(self.__class__.site_name, recipe_id))
                new_target_fn = self._get_new_fn(target_fn, "_", 1)
                logger.info("{}: rename : {} -> {}".format(self.__class__.site_name, target_fn.name, new_target_fn.name))
                target_fn.rename(new_target_fn)
    
    def _expand_entry_urls(self):
        return self.entry_urls
    
    def _is_existed_recipe(self, recipe):
        assert isinstance(recipe, recipe_crawler.models.Recipe)
        return (self.cache_dir / str(recipe.id)).exists()

    def _get_new_fn(self, from_path, prefix_mark, prefix_times):
        prefix = prefix_mark * prefix_times
        to_path = from_path.with_name(prefix + from_path.name)
        if to_path.exists():
            return self._get_new_fn(from_path, prefix_mark, prefix_times + 1)
        return to_path

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return int(target_id_str)

    def _sortkey_cache_filename(self, target_fn):
        return int(str(target_fn.stem))

    def _is_valid_cache_filename(self, target_fn):
        return target_fn.stem.isdigit()

    def _get_recipe_id_from_cache_file(self, target_fn):
        return int(target_fn.stem)

    def _get_recipe_overviews(self, overview_soup, entry_url):
        pass
    
    def _recipe_details_generator(self, detail_soup, recipe):
        """
        must deepcopy "recipe" before use
        """
        pass
