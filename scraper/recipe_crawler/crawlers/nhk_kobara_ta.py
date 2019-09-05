#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 22:08:17 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import urllib
import re
import logging
import copy
import hashlib

logger = logging.getLogger(__name__)

class NhkKobaraGaSukimashitaRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "nhk_kobara_ta"

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
            if item.table:
                continue
            
            if item.h1:
                continue
            
            if item.h2:
                current_subtitle = item.h2.text.translate(self.__class__._TABLE_REMOVE_KAKKO).strip()
                current_recipe_important_points.clear()
                continue
            
            if item.p is None:
                continue
            
            recipe = Recipe()
            recipe.detail_url = entry_url
            recipe.program_name = self.program_name
            recipe.program_date = None
            
            if item.img is None:
                for l in item.p.get_text("\n").splitlines():
                    current_recipe_important_points.append(RecipeText(l))
                continue
            
            if item.h3:
                # multiple recipe
                recipe.cooking_name = item.h3.text
                recipe.cooking_name_sub = current_subtitle
            else:
                # single recipe
                recipe.cooking_name = current_subtitle
            
            recipe.important_points.extend(current_recipe_important_points)
            recipe.image_urls.append(urllib.parse.urljoin(entry_url, item.img["src"]))
                
            is_material_area = False
            is_recipe_step_area = False
            # for l in item.find("div", "option-media-row").get_text("\n").splitlines():
            for l in item.p.get_text("\n").splitlines():
                if len(l.strip()) == 0:
                    continue
                
                if -1 < l.find("◎材料"):
                    is_material_area = True
                    material_title = l.replace("◎材料", "").translate(self.__class__._TABLE_REPLACE_MARUKAKKO).strip()
                    if len(material_title):
                        recipe.materials.append(RecipeText(material_title))
                    continue
                if -1 < l.find("＜作り方＞"):
                    is_material_area = False
                    is_recipe_step_area = True
                    continue
                
                if is_material_area:
                    l = l.replace(" 本", "本").replace(" 個", "個")
                    recipe.materials.extend([RecipeText(m.replace(":", ": ")) for m in l.split()])
                elif is_recipe_step_area:
                    m = re.match(r"(\d+).\s*(.*)", l)
                    if m:
                        gs = m.groups()
                        num = int(gs[0])
                        recipe_step = gs[1]
                        recipe.recipe_steps.append(RecipeText("（{}）{}".format(num, recipe_step)))
                    else:
                        recipe.recipe_steps.append(RecipeText(l))

            recipe.id = hashlib.md5(("{}/{}".format(recipe.cooking_name_sub, recipe.cooking_name) if recipe.cooking_name_sub else recipe.cooking_name).encode("utf-8")).hexdigest()          
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        yield recipe
