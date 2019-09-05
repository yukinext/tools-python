#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:57:16 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import urllib
import re
import logging
import dateutil
import copy

logger = logging.getLogger(__name__)

class OshaberiRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "oshaberi"

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.select("td .mon,.tue,.wed,.thu,.fri"):
            for link in item.find_all("a"):
                recipe = Recipe()
                recipe.detail_url = urllib.parse.urljoin(entry_url, link["href"])
                program_date_str = re.search(r"/(\d+)\.html", recipe.detail_url).group(1)
                recipe.id = int(program_date_str)
                recipe.cooking_name = link.text.split()[-1]
                recipe.program_name = self.program_name
                recipe.program_date = dateutil.parser.parse(program_date_str)
                recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)
        
        recipe.cooking_name_sub = detail_soup.find("td", "tema").text if detail_soup.find("td", "tema") else None
        recipe.image_urls.append(urllib.parse.urljoin(recipe.detail_url, detail_soup.select_one('img[src$="jpg"]')["src"]))

        recipe_steps_title_node, material_title_node = detail_soup.find_all("table", "text2")
        material_title = "（{}）".format(detail_soup.find("td", "making").text)
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        recipe.materials.extend([RecipeText(tr.text.strip().replace("\n", ": ")) for tr in material_title_node.find_all("tr")])

        recipe.recipe_steps = [RecipeText("（{}）{}".format(i+1, tr.text.strip())) for i, tr in enumerate(recipe_steps_title_node.find_all("tr"))]
        
        yield recipe

