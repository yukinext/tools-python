#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 22:05:39 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import urllib
import re
import logging
import copy
import datetime

logger = logging.getLogger(__name__)

class NikomaruKitchenRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "nikomaru"

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.find_all("dl"):
            recipe = Recipe()
            name, date, _ = item.find_all("dd")
            recipe.detail_url = urllib.parse.urljoin(entry_url, name.a["href"])
            recipe.id = int(re.search(r".*/(\d+)$", recipe.detail_url).group(1))
            recipe.cooking_name = name.text
            recipe.program_name = self.program_name
            recipe.program_date = datetime.date(*[int(v) for v in re.match(r"(\d+)\D+(\d+)\D+(\d+)\D*", date.text).groups()])
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        recipe.image_urls.append(urllib.parse.urljoin(recipe.detail_url, detail_soup.find("div", "photo").img["src"]))

        material_title_node = detail_soup.find("div", "material")
        material_title = material_title_node.h4.text.replace("材料", "").strip()
        if material_title:
            recipe.materials.append(RecipeText("（{}）".format(material_title)))
        for material in material_title_node.find_all("li"):
            texts = [m.text for m in material.find_all("span")]
            if "".join([t.strip() for t in texts]) == "":
                continue
            recipe.materials.append(RecipeText(": ".join(texts)))

        recipe_steps_title_node = detail_soup.find("div", "make")

        for i, recipe_step in enumerate(recipe_steps_title_node.find_all("li")):
            for j, l in enumerate(recipe_step.text.splitlines()):
                if j == 0:
                    recipe.recipe_steps.append(RecipeText("（{}）{}".format(i + 1, l)))
                    continue                
                recipe.recipe_steps.append(RecipeText(l))
        
        yield recipe
