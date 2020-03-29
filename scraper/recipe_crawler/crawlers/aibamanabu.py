#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 22:03:12 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import urllib
import re
import logging
import copy
import datetime
import json
import chardet

logger = logging.getLogger(__name__)

class AibamanabuRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "aibamanabu"

    def _convert_overview_content(self, raw_content):
        return json.loads(raw_content, encoding=chardet.detect(raw_content))

    def _get_recipe_overviews(self, jdata, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in jdata:
            recipe = Recipe()
            recipe.detail_url = urllib.parse.urljoin(entry_url, "../../" + item["url"])
            recipe.id = int(re.search(r".*/(\d+)/", recipe.detail_url).group(1))
            recipe.cooking_name_sub = item["title"]
            recipe.program_name = self.program_name
            program_date_str = item["date"]
            recipe.program_date = datetime.date(*[int(v) for v in re.match(r"(\d+)\D+(\d+)\D+(\d+)\D*", program_date_str).groups()])
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        overview_recipe.cooking_name_sub = " ".join(detail_soup.h3.text.split()[1:])
        title_nodes = detail_soup.select("div[class=ttl]")
        for title_node in title_nodes:
            recipe = copy.deepcopy(overview_recipe)
            recipe.cooking_name = title_node.text.translate(self.__class__._TABLE_REMOVE_KAKKO)
            
            img_node = title_node.find_next_sibling("div")
            
            if img_node:
                if img_node.img:
                    recipe.image_urls.append(
                            urllib.parse.urljoin(
                                    recipe.detail_url, img_node.img["src"]))
    
            material_node = title_node.find_next_sibling("div", text=re.compile(r"\[材料\].*"))
            if material_node:
                material_title = material_node \
                                    .text \
                                    .replace("[材料]", "") \
                                    .translate(self.__class__._TABLE_REPLACE_MARUKAKKO)
                if len(material_title):
                    recipe.materials.append(RecipeText(material_title))
                for dl in material_node.find_next_sibling("div").select("dl"):
                    recipe.materials.append(RecipeText(
                            dl.text.strip().replace("\n", ": ")))
    
            recipe_steps_title_node = title_node.find_next_sibling("div", text="[作り方]")
            for i, recipe_step in enumerate(recipe_steps_title_node.find_next_sibling("ol").find_all("li")):
                recipe.recipe_steps.append(RecipeText("（{}）{}".format(i + 1, recipe_step.text),))
            
            yield recipe
