#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 22:09:43 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import urllib
import re
import logging
import dateutil
import copy
import datetime

logger = logging.getLogger(__name__)

class NhkKiichiRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "nhk_kiichi"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return True

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        items = overview_soup.select("section,hr")[1:-1]
        
        subtitle_node = None
        title_node = None
        title_node_counter = 0
        for item in items:
            if item.name == "hr":
                subtitle_node = None
                title_node = None
                title_node_counter = 0
                continue
            if subtitle_node is None:
                subtitle_node = item
                continue
            else:
                title_node = item
                title_node_counter += 1

            recipe = Recipe()
            recipe.detail_url = entry_url
            recipe.cooking_name = title_node.h2.text.translate(self.__class__._TABLE_REMOVE_KAKKO).strip()
            recipe.cooking_name_sub = subtitle_node.h2.text.strip()
            recipe.program_name = self.program_name
            recipe.program_date = dateutil.parser.parse("{}/{}".format(*re.search("(\d+)\D+(\d+)\D+", recipe.cooking_name_sub).groups()))
            if title_node.img:
                recipe.image_urls.append(urllib.parse.urljoin(entry_url, title_node.img["src"]))
            
            is_material_area = False
            is_recipe_step_area = False
            for l in title_node.find("div", "option-media-row").get_text("\n").splitlines():
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
                    materials = [m.replace("… ", "…").replace("…", ": ") for m in l.split("\n") if len(m.strip())]
                    materials = [m[1:] if m.startswith("・") else m for m in materials]
                    recipe.materials.extend([RecipeText(m) for m in materials])
                elif is_recipe_step_area:
                    recipe.recipe_steps.append(RecipeText(l))

            if not recipe.program_date < datetime.datetime.now():
                logger.info("{} is invalid date".format(recipe.program_date))
                continue

            # recipe.id = hashlib.md5("{}/{}".format(recipe.cooking_name_sub, recipe.cooking_name).encode("utf-8")).hexdigest()            
            recipe.id = "{:%Y%m%d}".format(recipe.program_date)
            if 1 < title_node_counter:
                recipe.id += "_{}".format(title_node_counter)

            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        yield recipe
