#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 22:10:59 2019

@author: yuki_next

"""
from . import bases
from recipe_crawler.models import Recipe, RecipeText

from bs4 import BeautifulSoup
import re
import logging
import copy
import requests
import dateutil
import urllib

logger = logging.getLogger(__name__)

class TbsObigohanRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "tbs_obigohan"

    def _expand_entry_urls(self):
        ret = set()
        def extract_back_url(target_url):
            res = requests.get(target_url)
            if res.ok:
                soup = BeautifulSoup(res.content, "html5lib", from_encoding=res.apparent_encoding)
                back_btn = soup.select_one("#backBtn")
                if back_btn:
                    back_url = urllib.parse.urljoin(target_url, back_btn.a["href"])
                    ret.add(back_url)
                    extract_back_url(back_url)
            
        for entry_url in self.entry_urls:
                extract_back_url(entry_url)
            
        return ret

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        detail_urls = [urllib.parse.urljoin(entry_url, waku.a["href"]) for waku in overview_soup.find_all("div", "waku") if waku.a]
        for detail_url in detail_urls:
            recipe = Recipe()
            
            recipe.detail_url = detail_url
            recipe.id = int(re.search(r"/\D*(\d+)\D*$", recipe.detail_url).group(1))
            recipe.program_name = self.program_name
            recipe.program_date = dateutil.parser.parse(str(recipe.id))
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        for recipe_area_node in detail_soup.find_all("section", "recipe_area"):
            if recipe_area_node.h4 is None:
                continue

            recipe = copy.deepcopy(overview_recipe)
            recipe.cooking_name = "/".join([t.text.strip() for t in recipe_area_node.find_all("h4")])
            pic_sub = recipe_area_node.find("div", "pic_sub")
            if pic_sub:
                for class_v in pic_sub["class"]:
                    if class_v.lower().startswith("photo"):
                        image_url = urllib.parse.urljoin(recipe.detail_url, "../img/recipe/{}/{}.jpg".format(recipe.id, class_v))
                        recipe.image_urls.append(image_url)
    
            material_title_node = recipe_area_node.find("div", "material_box")
            material_title = material_title_node.find("span", "people")
            if material_title:
                material_title = material_title.text.translate(self.__class__._TABLE_REPLACE_MARUKAKKO).strip()
                recipe.materials.append(RecipeText(material_title))
                
            for tr in material_title_node.find_all("tr"):
                recipe.materials.append(RecipeText(": ".join([td.text.strip() for td in tr.find_all("td")])))
                        
            recipe_title_node = recipe_area_node.find("div", "recipe_main_box")
            for i, recipe_step in enumerate(recipe_title_node.find_all("span", "recipe_text")):
                recipe_step_str = recipe_step.text.strip()
                if len(recipe_step_str):
                    recipe.recipe_steps.append(RecipeText("（{}）{}".format(i + 1, recipe_step_str)))
            
            point_title_node = recipe_area_node.find("div", "point_box_wide")
            if point_title_node:
                recipe.important_points.extend([RecipeText(p) for p in point_title_node.find("span", "point").text.strip().splitlines()])
            
            yield recipe
