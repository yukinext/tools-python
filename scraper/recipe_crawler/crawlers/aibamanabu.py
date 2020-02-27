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

logger = logging.getLogger(__name__)

class AibamanabuRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "aibamanabu"

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        wlist = overview_soup.find("div", "wlist")
        if wlist:
            for item in wlist.find_all("dd"):
                recipe = Recipe()
                recipe.detail_url = urllib.parse.urljoin(entry_url, item.a["href"])
                recipe.id = int(re.search(r".*/(\d+)/", recipe.detail_url).group(1))
                program_date_str, cooking_name_sub = item.get_text("\n").split(maxsplit=1)
                recipe.cooking_name_sub = cooking_name_sub
                recipe.program_name = self.program_name
                recipe.program_date = datetime.date(*[int(v) for v in re.match(r"(\d+)\D+(\d+)\D+(\d+)\D*", program_date_str).groups()])
                recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        number_node = detail_soup.select_one("#number")
        date_node = number_node.find_next_sibling("dt")
        title_nodes = detail_soup.select("span[class*=tit]")
        
        start_index = 1
        if len(title_nodes) == 1:
            overview_recipe.cooking_name_sub = None
            start_index = 0
        else:
            overview_recipe.cooking_name_sub = "{} {}".format(number_node.text, title_nodes[0].text)

        overview_recipe.program_date = datetime.date(*[int(v) for v in re.match(r"(\d+)\D+(\d+)\D+(\d+)\D*", date_node.text).groups()])
        
        for title_node in title_nodes[start_index:]:
            recipe = copy.deepcopy(overview_recipe)
            recipe.cooking_name = title_node.text.translate(self.__class__._TABLE_REMOVE_KAKKO)
            
            img_node = title_node.parent.find_next_sibling("div")
            if img_node is None:
                img_node = title_node.find_next_sibling("div")
            
            if img_node:
                if img_node.img:
                    recipe.image_urls.append(
                            urllib.parse.urljoin(
                                    recipe.detail_url, img_node.img["src"]))
            materials_node = title_node.parent.find_next_sibling("table")
            if materials_node is None:
                materials_node = title_node.find_next_sibling("table")
            
            recipe_steps_title_node = None
            if materials_node:
                recipe_steps_title_node = materials_node.find_next_sibling("span").parent.ol
                
                material_title = materials_node \
                                .tr.find_all("td")[1].text \
                                .replace("【材料】", "") \
                                .replace("材料", "") \
                                .translate(self.__class__._TABLE_REPLACE_MARUKAKKO)
                if len(material_title):
                    recipe.materials.append(RecipeText(material_title))
    
                for material in materials_node.find_all("tr")[1:]:
                    recipe.materials.append(RecipeText(
                            ": ".join([m.text.replace("…", "") for m in material.find_all("td")[1:] if len(m.text.strip())])))
            
            else:
                recipe_steps_title_node = title_node.parent.find_next("ol")
                
            for i, recipe_step in enumerate(recipe_steps_title_node.find_all("li")):
                recipe.recipe_steps.append(RecipeText("（{}）{}".format(i + 1, recipe_step.text),))
            
            yield recipe
