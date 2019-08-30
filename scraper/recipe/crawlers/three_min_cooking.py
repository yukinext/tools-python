#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:58:43 2019

@author: yuki_next
"""

from . import bases
from models import Recipe, RecipeText
import urllib
import re
import logging
import dateutil
import requests
import copy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class ThreeMinCookingRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "three_minutes_cooking"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return not target_fn.stem.startswith("_")

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _get_recipe_overviews(self, overview_soup, entry_url):
        def get_other_recipe(detail_url):
            res = requests.get(detail_url, verify=False)
            if res.ok:
                soup = BeautifulSoup(res.content, "html5lib", from_encoding=res.apparent_encoding)
                other_recipe_node = soup.select_one("#other-recipe")
                if other_recipe_node:
                    other_recipe = Recipe()
                    other_recipe.detail_url = urllib.parse.urljoin(detail_url, other_recipe_node.a["href"])
                    other_recipe.id = re.search(r".*/(.*)\.html", other_recipe.detail_url).group(1)
                    return other_recipe
        
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in [item for item in overview_soup.find_all("div", "waku") if item.a]:
            recipe = Recipe()
            recipe.detail_url = urllib.parse.urljoin(entry_url, item.a["href"])
            recipe.id = re.search(r".*/(.*)\.html", recipe.detail_url).group(1)
            recipes[recipe.id] = recipe

            other_recipe = get_other_recipe(recipe.detail_url)
            if other_recipe:
                recipes[other_recipe.id] = other_recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)
        recipe.cooking_name = detail_soup.h3.text
        recipe.program_name = self.program_name
        recipe.program_date = dateutil.parser.parse(recipe.id.split("_")[0])

        recipe.image_urls.append(urllib.parse.urljoin(recipe.detail_url, detail_soup.select_one("#thumbnail")["src"]))

        material_title_node = detail_soup.find("div", "ingredient")
        recipe_steps_title_node = detail_soup.find("div", "howto")
        
        material_title = material_title_node.h4.text.replace("材料", "").translate(self.__class__._TABLE_REPLACE_MARUKAKKO).strip()
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        for material in material_title_node.find_all("tr"):
            recipe.materials.append(RecipeText(": ".join([m.text for m in material.find_all("td")])))

        for recipe_step in recipe_steps_title_node.find_all("tr"):
            num, step = recipe_step.find_all("td")
            if step.li is None:
                buf = ""
                num = num.text.strip()
                if len(num):
                    buf += "（{}）".format(num)
                buf += step.text.strip()
                
                image_urls = None
                if step.img:
                    image_urls = [urllib.parse.urljoin(recipe.detail_url, step.img["src"])]
                
                recipe.recipe_steps.append(RecipeText(buf, image_urls=image_urls))
            else:  # No.20190824
                # exists sub steps.
                recipe.recipe_steps.append(RecipeText(step.next)) # line.1 is title in sub steps
                for sub_index, step_li in enumerate(step.find_all("li")):
                    image_urls = None
                    if step_li.img:
                        image_urls = [urllib.parse.urljoin(recipe.detail_url, step_li.img["src"])]
                    recipe.recipe_steps.append(RecipeText("（{}）{}".format(sub_index + 1, step_li.text), image_urls=image_urls))
        
        for appendix in detail_soup.find_all("div", "recipe-box"):
            for i, l in enumerate([t.strip() for t in appendix.get_text("\n").splitlines() if len(t.strip())]):
                if l.startswith("・"):
                    l = l[1:].strip()
                
                if i:
                    l = "　{}".format(l)
                
                recipe.important_points.append(RecipeText(l))
        
        yield recipe
