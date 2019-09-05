#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:48:13 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import urllib
import re
import pathlib
import logging
import dateutil
import bs4
import copy

logger = logging.getLogger(__name__)

class NhkUmaiRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "nhk_umai"

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        links = [a for a in overview_soup.find_all("a") if a.img]
        for link in links:
            recipe = Recipe()
            recipe.detail_url = urllib.parse.urljoin(entry_url, link["href"])
            recipe.id = int(urllib.parse.splitvalue(recipe.detail_url)[1])
            recipe.program_name = self.program_name
            recipes[recipe.id] = recipe
            
            m = re.match(r".*?(\d{6}).*", pathlib.Path(link.img["src"]).name)
            if m:
                yymmdd = m.group(1)
                logger.debug("program_date:{}".format(yymmdd))
                # recipe.program_date = datetime.date(year=2000 + int(yymmdd[0:2]), month=int(yymmdd[2:4]), day=int(yymmdd[4:6]))
                recipe.program_date = dateutil.parser.parse("20{}".format(yymmdd))
        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        def get_cooking_string(target_cooking_name_node, cooking_name_nodes):
            ret = []
            for sibling in target_cooking_name_node.next_siblings:
                if sibling in cooking_name_nodes:
                    break
                if isinstance(sibling, bs4.NavigableString):
                    ret.append(sibling)
                else:
                    ret.append(sibling.text)
            return "\n".join([l for l in ret if len(l.strip())])
        
        cooking_name_nodes = detail_soup.find_all("h4")
        for cooking_name_node in cooking_name_nodes:
            recipe = copy.deepcopy(overview_recipe)
            recipe.cooking_name = cooking_name_node.text
            recipe.image_urls = [urllib.parse.urljoin(recipe.detail_url, node["src"]) for node in cooking_name_node.parent.parent.select('img[src$="jpg"]')]
            
            cooking_string = get_cooking_string(cooking_name_node, cooking_name_nodes)
            
            is_material_area = False
            is_recipe_step_area = False
            for l in cooking_string.splitlines():
                if len(l.strip()) == 0:
                    continue
                
                if -1 < l.find("材料"):
                    if is_recipe_step_area == False:
                        is_material_area = True
                        continue
                if -1 < l.find("作り方"):
                    is_material_area = False
                    is_recipe_step_area = True
                    continue
                
                if is_material_area:
                    if l.startswith("・"):
                        l = l[1:]
                    recipe.materials.append(RecipeText(l.replace("：", ": ")))
                elif is_recipe_step_area:
                    m = re.match(r"(\d+)[）．](.*)", l)
                    if m:
                        l = "（{}）{}".format(*m.groups())
                    recipe.recipe_steps.append(RecipeText(l))

            if len(recipe.materials) + len(recipe.recipe_steps):
                yield recipe
