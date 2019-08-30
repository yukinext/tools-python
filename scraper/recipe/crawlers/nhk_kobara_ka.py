#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 22:06:50 2019

@author: yuki_next
"""

from . import bases
from models import Recipe, RecipeText
import urllib
import re
import logging
import dateutil
import copy
import hashlib

logger = logging.getLogger(__name__)

class NhkKobaraSuitemasenkaRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "nhk_kobara_ka"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return not target_fn.stem.startswith("_")

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe

        current_subtitle = None
        current_recipe_important_points = list()
        for item in overview_soup.find_all("section")[1:]:
            if item.h1:
                continue
            
            subtitle_node = item.find("h2", "option-sub-title")
            if subtitle_node and subtitle_node.find_next_sibling("p") is None: # 
                current_subtitle = subtitle_node.text.translate(self.__class__._TABLE_REMOVE_KAKKO).strip()
                current_recipe_important_points.clear()
                continue            
            
            if item.h2:
                title_node = item
                
                recipe = Recipe()
                recipe.detail_url = entry_url
                recipe.cooking_name = title_node.h2.text.translate(self.__class__._TABLE_REMOVE_KAKKO).strip()
                recipe.cooking_name_sub = current_subtitle
                recipe.program_name = self.program_name
                recipe.program_date = dateutil.parser.parse("{}/{}".format(*re.search("(\d+)\D+(\d+)\D+", recipe.cooking_name_sub).groups()))
                recipe.image_urls.append(urllib.parse.urljoin(entry_url, title_node.img["src"]))
            
                is_material_area = False
                is_recipe_step_area = False
                for l in title_node.find("div", "option-media-row").get_text("\n").splitlines():
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
                        
                recipe.id = "{:%Y%m%d}_{}".format(recipe.program_date, hashlib.md5(("{}/{}".format(recipe.cooking_name_sub, recipe.cooking_name) if recipe.cooking_name_sub else recipe.cooking_name).encode("utf-8")).hexdigest())
                recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        yield recipe
