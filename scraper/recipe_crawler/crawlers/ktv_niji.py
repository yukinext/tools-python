#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 22:10:59 2019

@author: yuki_next

"""
from . import bases
from recipe_crawler.models import Recipe, RecipeText

import re
import logging
import copy
import datetime
import dateutil
import urllib
import pathlib

logger = logging.getLogger(__name__)

class KtvNijiiroRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "ktv_niji"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return True

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _expand_entry_urls(self):
        ret = set()
        entry_url_base = self.entry_urls[0]
        base = datetime.date.today()
        for d in range(0, 5):
            offset = -1 - d
            target = base + dateutil.relativedelta.relativedelta(weekday=dateutil.relativedelta.SA(offset))
            ret.add(urllib.parse.urljoin(entry_url_base, "/niji/{:%y%m%d}.html".format(target)))
            
        return ret

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipe_title_node = overview_soup.find("h2", text="レシピ")
        if recipe_title_node is None:
            logger.info("{} have no recipe.".format(entry_url))
            return dict()
        
        recipe_root_node = recipe_title_node.parent

        recipes = dict() # key: Recipe.id, value: Recipe
        for ii, recipe_node in enumerate([h3.parent for h3 in recipe_root_node.find_all("h3")]):
            recipe = Recipe()
            
            recipe.program_date = dateutil.parser.parse("20{}".format(pathlib.Path(entry_url).stem))
            recipe.program_name = self.program_name
            recipe.detail_url = entry_url
            recipe.cooking_name = recipe_node.h3.text
            recipe.image_urls.append(urllib.parse.urljoin(entry_url, re.search("background-image:url\((.*?)\);", recipe_node.img["style"]).group(1)))
            

            is_material_area = False
            is_recipe_step_area = False
            for l in recipe_node.find_all("p")[1].text.splitlines():
                if len(l.strip()) == 0:
                    continue
                
                if -1 < l.find("【材料】"):
                    if is_recipe_step_area == False:
                        is_material_area = True
                        l = l.replace("【材料】", "").translate(self.__class__._TABLE_REPLACE_MARUKAKKO).strip()
                        if len(l):
                            recipe.materials.append(RecipeText(l))
                        continue
                if -1 < l.find("【作り方】"):
                    is_material_area = False
                    is_recipe_step_area = True
                    continue
                
                if is_material_area:
                    material = l.replace("：", ": ")
                    recipe.materials.append(RecipeText(material))
                elif is_recipe_step_area:
                    recpe_step_text = l
                    m = re.match("^(\d+)(.*)", l)
                    if m:
                        num, recipe_t = m.groups()
                        recpe_step_text = "（{}）{}".format(num, recipe_t.strip())
                    recipe.recipe_steps.append(RecipeText(recpe_step_text))
                    
            recipe.id = "{:%Y%m%d}_{}".format(recipe.program_date, ii)

            recipes[recipe.id] = recipe
            
        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        yield recipe
