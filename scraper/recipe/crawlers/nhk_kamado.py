#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 22:03:12 2019

@author: yuki_next
"""

from . import bases
from models import Recipe, RecipeText
import urllib
import re
import logging
import copy
import datetime

logger = logging.getLogger(__name__)

class NhkKamadoRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "nhk_kamado"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return int(re.search(r"(\d+)", target_fn.stem).group(1))

    def _is_valid_cache_filename(self, target_fn):
        return not target_fn.stem.startswith("_")

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.find("ul", "recipeTable").find_all("li"):
            recipe = Recipe()
            recipe.detail_url = urllib.parse.urljoin(entry_url, item.a["href"])
            recipe.id = re.search(r".*/(.*)\.html", recipe.detail_url).group(1)
            
            program_date_str, _, cooking_name_sub, _ = item.find_all("p")
            recipe.cooking_name_sub = "〜{}〜より".format(cooking_name_sub.text)
            recipe.program_name = self.program_name
            recipe.program_date = datetime.date(*[int(v) for v in re.match(r"(\d+)\D+(\d+)\D+(\d+)\D*", program_date_str.text).groups()])
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        recipe.cooking_name = "".join(detail_soup.h2.text.split()) # No.153 is invalid title ex. "(太陽みたいなでっか～い)\tアンパン"
        recipe.image_urls.append(urllib.parse.urljoin(recipe.detail_url, "".join(detail_soup.find("p", "plat").img["src"].split()))) # No.135 is invalid: 'https://www.nhk.or.jp/kamado/images/135\n\n/recipe_plat.jpg'

        if detail_soup.find("div", "sozai_inner"):
            # exist materials part
            material_title_node = detail_soup.find("div", "sozai_inner").table
            for material in material_title_node.find_all("tr"):
                recipe.materials.append(RecipeText(": ".join(material.text.strip().split())))
    
            kimete = detail_soup.find("div", "kimete")
            if kimete:
                if kimete.h4:
                    recipe.important_points.append(RecipeText(kimete.h4.text))
                kimete_l = kimete.select_one("div.kimete_l,div.kimete_inner2")
                if kimete_l:
                    for p in kimete_l.find_all("p"):
                        recipe.important_points.append(RecipeText(": ".join([c.text if hasattr(c, "text") else c for c in p.contents])))
            recipe_prepare_node = detail_soup.find("table", "prepare")
            if recipe_prepare_node:
                recipe.recipe_steps.append(RecipeText("準備"))
                recipe_prepare_l = recipe_prepare_node.find("p", "txt")
                if recipe_prepare_l is None:
                    ps = recipe_prepare_node.find_all("p")
                    if ps:
                        recipe_prepare_l = ps[-1]
                    else:
                        recipe_prepare_l = detail_soup.dl # example: id=04
                if recipe_prepare_l:
                    for c in recipe_prepare_l.contents:
                        tmp = c
                        if hasattr(c, "text"):
                            tmp = c.text
                        tmp = tmp.strip()
                        if len(tmp):
                            recipe.recipe_steps.append(RecipeText(tmp))
                else:
                    logger.debug("no prepare: {}".format(recipe.id))
        
        for step_table in detail_soup.find_all("table", "step"): # No.92 has multiple table(include invalid format)
            # exist recipe steps part
            recipe_steps_title_node = step_table
            if recipe_steps_title_node.tbody:
                recipe_steps_title_node = recipe_steps_title_node.tbody # No.92 has no tbody element
                
            for recipe_step in recipe_steps_title_node.find_all("tr", recursive=False):
                for td in recipe_step.find_all("td", recursive=False):
                    image_urls = [urllib.parse.urljoin(recipe.detail_url, img["src"]) for img in td.select('img[src$="jpg"]')]
                    
                    text = ""
                    if td.img:
                        # img_alt = td.img["alt"] # 02 is invalid step number.
                        img_src = td.img["src"]
                        m = re.search(r".*step(\d+)\.png", img_src)
                        if m:
                            num = m.group(1)
                            num = int(num)
                            text += "（{}）".format(num)
                        else:
                            text += td.img["alt"]
    
                    if len(td.text.strip()):
                        text += td.text.strip()
                    
                    if len(text):
                        image_urls = ["".join(image_url.split()) for image_url in image_urls] # No.120 is invalid "../images/120\n/recipe_process03.jpg"
                        recipe.recipe_steps.append(RecipeText(text, image_urls=image_urls))
            
        yield recipe
