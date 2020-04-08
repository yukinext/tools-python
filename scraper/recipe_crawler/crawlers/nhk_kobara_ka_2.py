#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:48:13 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import re
import logging
import dateutil
import json
import chardet
import copy

logger = logging.getLogger(__name__)

class NhkKobaraSuitemasenka2RecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "nhk_kobara_ka_2"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return True

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _convert_overview_content(self, raw_content):
        return json.loads(raw_content, encoding=chardet.detect(raw_content))

    def _get_recipe_overviews(self, jdata, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in jdata["result"]:
            recipe = Recipe()
            recipe.detail_url = item["url"]
            recipe.id = item["id"]
            recipe.cooking_name_sub = item["identifierGroup"]["episodeName"][1:-1]
            recipe.program_name = self.program_name
            for be in item["broadcastEvent"]:
                if be["misc"]["releaseLevel"] == "original":
                    program_date_str = be["identifierGroup"]["date"]
                    recipe.program_date = dateutil.parser.parse(program_date_str).date()
                    recipe.id = "{}_{}".format(program_date_str, item["id"])
            recipes[recipe.id] = recipe
        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        def get_recipe_areas(lines):
            recipe_areas = list()
            recipe_area = None
            for ii, line in enumerate(lines):
                if ii == 0 or re.match(r"^「.*?」", line.strip()):
                    recipe_area = list()
                    recipe_areas.append(recipe_area)
                recipe_area.append(line)
            
            # 1st line in recipe_area is cooking_name
            return recipe_areas
        
        
        recipe_title_node = detail_soup.find("span", text=re.compile(r".*レシピ"))
        if recipe_title_node is None:
            return
        
        for recipe_area in get_recipe_areas(recipe_title_node.parent.find_next_sibling("ul").text.splitlines()):
            recipe = copy.deepcopy(overview_recipe)
            recipe.cooking_name = recipe_area[0].translate(self.__class__._TABLE_REMOVE_KAKKO).strip()
        
            is_material_area = False
            is_recipe_step_area = False
            for l in recipe_area[1:]:
                if len(l.strip()) == 0:
                    continue
                
                if -1 < l.find("＜材料＞"):
                    is_material_area = True
                    recipe.materials.append(RecipeText(l.replace("＜材料＞", "").translate(self.__class__._TABLE_REPLACE_MARUKAKKO)))
                    continue
                if -1 < l.find("＜作り方＞"):
                    is_material_area = False
                    is_recipe_step_area = True
                    continue
                
                if is_material_area:
                    recipe.materials.extend([RecipeText(m.replace(":", ": ")) for m in l.split()])
                elif is_recipe_step_area:
                    recipe.recipe_steps.append(RecipeText(l))

            yield recipe