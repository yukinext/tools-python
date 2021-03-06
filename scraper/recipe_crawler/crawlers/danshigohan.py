#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:54:28 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import re
import dateutil
import logging
import copy
import urllib

logger = logging.getLogger(__name__)

class DanshigohanRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "danshigohan"

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
        for item in overview_soup.find_all("div", "item"):
            recipe = Recipe()
            recipe.detail_url = item.a["href"]
            id_s = re.search(r"/(\d+)/(.*)?\.html", recipe.detail_url)
            recipe.id = "{}_{}".format(id_s.group(1), id_s.group(2))
            recipe.cooking_name = item.h4.text
            recipe.program_name = self.program_name
            recipe.program_date = dateutil.parser.parse(item.find("div", "date").text)
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        h6s = detail_soup.find_all("h6")
        # h6s = detail_soup.select("h5,h6") # 2020.01.05 アンパドラット
        threshold_len = int(len(h6s)/2)
        material_title_nodes = h6s[0:threshold_len]
        recipe_steps_title_nodes = h6s[threshold_len:]

        for i, (material_title_node, recipe_steps_title_node) in enumerate(zip(material_title_nodes, recipe_steps_title_nodes)):
            recipe = copy.deepcopy(overview_recipe)
    
            recipe.image_urls.append(urllib.parse.urljoin(recipe.detail_url, detail_soup.find("div", "common_contents_box_mini").img["src"]))

            material_title = material_title_node.text.replace("材料", "").strip()
            if material_title:
                if i:
                    recipe.cooking_name = "%s / %s" % (recipe.cooking_name, material_title)
                recipe.materials.append(RecipeText(material_title))
            for material in material_title_node.find_next_sibling("ul").find_all("li"):
                recipe.materials.append(RecipeText(": ".join([m.text for m in material.find_all("span")])))
    
            for j, recipe_step in enumerate(recipe_steps_title_node.find_next_sibling("ul").find_all("li")):
                recipe.recipe_steps.append(RecipeText("（{}）{}".format(j + 1, recipe_step.text.strip())))
            
            yield recipe
