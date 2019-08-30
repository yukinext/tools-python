#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:54:28 2019

@author: yuki_next
"""

from . import bases
from models import Recipe, RecipeText
import re
import dateutil
import logging
import copy

logger = logging.getLogger(__name__)

class DanshigohanRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "danshigohan"

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.find_all("div", "item"):
            recipe = Recipe()
            recipe.detail_url = item.a["href"]
            recipe.id = int(re.search(r"_(\d+)\.html", recipe.detail_url).group(1))
            recipe.cooking_name = item.h4.text
            recipe.program_name = self.program_name
            recipe.program_date = dateutil.parser.parse(item.find("div", "date").text)
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        recipe.image_urls.append(detail_soup.find("div", "common_contents_box_mini").img["src"])

        material_title_node, recipe_steps_title_node = detail_soup.find_all("h6")
        material_title = material_title_node.text.replace("材料", "").strip()
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        for material in material_title_node.find_next_sibling("ul").find_all("li"):
            recipe.materials.append(RecipeText(": ".join([m.text for m in material.find_all("span")])))

        for recipe_step in recipe_steps_title_node.find_next_sibling("ul").find_all("li"):
            recipe.recipe_steps.append(RecipeText(recipe_step.text.strip()))
        
        yield recipe
