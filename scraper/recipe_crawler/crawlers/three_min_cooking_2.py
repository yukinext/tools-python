#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:58:43 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import urllib
import re
import logging
import dateutil
import requests
import copy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class ThreeMinCooking2RecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "three_minutes_cooking_2"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return not target_fn.stem.startswith("_")

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _get_recipe_overviews(self, overview_soup, entry_url):
        def get_other_recipes(detail_url):
            ret = dict() # key: Recipe.id, value: Recipe
            res = requests.get(detail_url, verify=False)
            if res.ok:
                soup = BeautifulSoup(res.content, "html5lib", from_encoding=res.apparent_encoding)
                for other_recipe_node in soup.find_all("div", "detail-more-title"):
                    other_recipe = Recipe()
                    other_recipe.detail_url = urllib.parse.urljoin(detail_url, other_recipe_node.a["href"])
                    other_recipe.id = "_".join(re.search(r".*/(.*)/(.*)/", other_recipe.detail_url).groups())
                    ret[other_recipe.id] = other_recipe
            return ret
        
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in [item for item in overview_soup.find_all("div", "result-title")]:
            recipe = Recipe()
            recipe.detail_url = urllib.parse.urljoin(entry_url, item.parent["href"])
            recipe.id = re.search(r".*/(.*)/", recipe.detail_url).group(1)
            recipes[recipe.id] = recipe

            other_recipes = get_other_recipes(recipe.detail_url)
            recipes.update(other_recipes)

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)
        recipe.cooking_name = detail_soup.find("p", "detail-title-name").text.strip()
        recipe.program_name = self.program_name
        recipe.program_date = dateutil.parser.parse(recipe.id.split("_")[0])

        recipe.image_urls.append(detail_soup.find("meta", attrs=dict(property="og:image"))["content"])
        title_nodes = detail_soup.find_all("h2")

        material_title_node = title_nodes[0]
        advice_title_node = title_nodes[-5]
        
        material_title = material_title_node.text.replace("材料", "").translate(self.__class__._TABLE_REPLACE_MARUKAKKO).strip()
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        
        recipe.materials.extend([RecipeText(": ".join(li.text.split())) for li in material_title_node.parent.parent.select("h4,li")])

        for i, howto_item in enumerate(detail_soup.find_all("div", "howto-item")):
            if i:
                recipe.recipe_steps.append(RecipeText("")) # 空行
            if howto_item.find("div", "howto-child") is not None:
                # https://www.ntv.co.jp/3min/recipe/20200704/
                for recipe_item in howto_item.find_all("li"):
                    for j, recipe_step in enumerate(recipe_item.find_all("div", "howto-group-inner")):
                        buf = ""
                        if j:
                            num, step = re.search(r"【(\d+)】(.*)", recipe_step.text.strip()).groups()
                            num = num.strip()
                            if len(num):
                                buf += "（{}）".format(num)
                            buf += step.strip()
                        else:
                            buf = recipe_step.text.strip()
                            
                        image_urls = []
                        for img in recipe_step.find_all("img"):
                            image_urls.append(img["src"])
                        
                        recipe.recipe_steps.append(RecipeText(buf, image_urls=image_urls))
                                        
                    for j, howto_memo_item in enumerate(recipe_item.find_all("div", "howto-memo-item")):
                        if j:
                            recipe.recipe_steps.append(RecipeText("")) # 空行
                        buf = "（メモ）" + howto_memo_item.text.strip()
                        
                        image_urls = []
                        for img in howto_memo_item.find_all("img"):
                            if ("class" in img) and img["class"] != "howto-memo-icon":
                                image_urls.append(img["src"])
                        
                        recipe.recipe_steps.append(RecipeText(buf, image_urls=image_urls))
            else:
                # for recipe_step in recipe_steps_title_node.parent.parent.find_all("li"):
                for recipe_step in howto_item.find_all("li"):
                    buf = ""
                    if i:
                        buf = recipe_step.text.strip()
                    else:
                        ps = recipe_step.find_all("p")
                        if len(ps) == 2:
                            num, step = ps
                            num = num.text.strip()
                            if len(num):
                                buf += "（{}）".format(num)
                        else:
                            # https://www.ntv.co.jp/3min/recipe/20200812/ :no num parts
                            step = ps[0]
                        buf += step.text.strip()
                    
                    image_urls = []
                    for img in recipe_step.find_all("img"):
                        image_urls.append(img["src"])
                    
                    recipe.recipe_steps.append(RecipeText(buf, image_urls=image_urls))

        for i, points_item in enumerate(detail_soup.find_all("div", "points-item")):
            if i:
                recipe.recipe_steps.append(RecipeText("")) # 空行
            buf = "（ポイント）" + points_item.text.strip()
            
            image_urls = []
            for img in points_item.find_all("img"):
                if ("class" in img) and img["class"] != "points-icon":
                    image_urls.append(img["src"])
            
            recipe.recipe_steps.append(RecipeText(buf, image_urls=image_urls))

        
        for advice in advice_title_node.parent.parent.find_all("li"):
            recipe.important_points.append(RecipeText(advice.text.strip()))
        
        yield recipe
