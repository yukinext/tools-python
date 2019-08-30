#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:55:49 2019

@author: yuki_next
"""

from . import bases
from models import Recipe, RecipeText
import urllib
import re
import logging
import dateutil
import copy

logger = logging.getLogger(__name__)

class RskCookingRecipeRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "rsk_cooking_recipe"
    
    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.find_all("div", "recipe-piece"):
            recipe = Recipe()
            recipe.detail_url = urllib.parse.urljoin(entry_url, item.a["href"])
            program_date_str = re.search(r"/(\d+)\.html", recipe.detail_url).group(1)
            recipe.id = int(program_date_str)
            recipe.program_name = self.program_name
            recipe.program_date = dateutil.parser.parse(program_date_str)
            recipes[recipe.id] = recipe

        return recipes

    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)
        recipe.cooking_name = detail_soup.strong.text if detail_soup.strong else detail_soup.find_all("b")[1].text
        
        recipe.image_urls.append(urllib.parse.urljoin(recipe.detail_url, detail_soup.select_one('img[src$="jpg"]')["src"]))

        material_title = "（{}）".format(detail_soup.find("td", align="right").b.text.strip())
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        
        for material in detail_soup.find("div","zairyo").text.strip().splitlines():
            if -1 < material.find("監修"):
                break
            if len(material):
                recipe.materials.append(RecipeText(material.replace("…", ": ")))

        for recipe_step in detail_soup.find_all("table")[-2].find_all("td")[1].text.strip().splitlines():
            recipe_step = recipe_step.strip()
            if -1 < recipe_step.find("監修"):
                break

            if len(recipe_step):
                recipe.recipe_steps.append(RecipeText(recipe_step))
        
        yield recipe
