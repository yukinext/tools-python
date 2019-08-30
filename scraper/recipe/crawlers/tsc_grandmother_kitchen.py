#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 22:10:59 2019

@author: yuki_next

"""
from . import bases
from models import Recipe, RecipeText

from bs4 import BeautifulSoup
import re
import logging
import copy
import requests
import datetime

logger = logging.getLogger(__name__)

class TscGrandmotherKitchenRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "tsc_grandmother_kitchen"

    def _expand_entry_urls(self):
        ret = set()
        for entry_url in self.entry_urls:
            res = requests.get(entry_url)
            if res.ok:
                soup = BeautifulSoup(res.content, "html5lib", from_encoding=res.apparent_encoding)
                last_page_url = soup.find("div", "pagination").find_all("a")[-1]["href"]
                page_url, last_page_num_str = re.search(r"(.*)/(\d+)/$", last_page_url).groups()
                for page_num in range(1, int(last_page_num_str) + 1):
                    ret.add("{}/{}/".format(page_url, page_num))
            
        return ret

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.find_all("article", "post-archive"):
            recipe = Recipe()
            
            cns_buf = [l.translate(self.__class__._TABLE_REMOVE_KAKKO) for l in reversed(item.h2.get_text("\n").splitlines())]
            cns_buf.insert(1, item.find("div", "recipe-archive-cast").text)
            
            recipe.cooking_name_sub = "/".join(cns_buf)
            recipe.detail_url = item.a["href"]
            recipe.id = int(re.search(r"/(\d+)\D*$", recipe.detail_url).group(1))
            recipe.program_name = self.program_name
            recipe.program_date = datetime.date(*[int(s) for s in re.search(r"(\d+)\D+(\d+)\D+(\d+)\D+", item.find("div", "recipe-onairs").text).groups()])
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        for recipe_box_node in detail_soup.find_all("section", "recipe-box"):
            if recipe_box_node.h3 is None:
                continue

            recipe = copy.deepcopy(overview_recipe)
            recipe.cooking_name = recipe_box_node.h3.text.translate(self.__class__._TABLE_REMOVE_KAKKO)
            recipe.image_urls.append(detail_soup.find("div", "recipe-food-img").img["src"])
    
            material_title_node = recipe_box_node.find("div", "recipe-material")
            m_buf = []
            m_buf.append("（{}）".format(material_title_node.span.text))
            for dt in material_title_node.find_all("dt"):
                material_title = dt.text.replace("材料", "").translate(self.__class__._TABLE_REPLACE_MARUKAKKO).strip()
                if len(material_title):
                    m_buf.append(material_title)
                dd = dt.find_next_sibling("dd")
                for material in [": ".join([td.text.strip() for td in tr.find_all("td")]) for tr in dd.find_all("tr")]:
                    if len(material.strip()):
                        m_buf.append("　" + material)
            recipe.materials.extend([RecipeText(m) for m in m_buf])
            
            for i, recipe_step in enumerate(recipe_box_node.find("ol", "recipe-process-list").find_all("li")):
                recipe_step_str = recipe_step.text.strip()
                if len(recipe_step_str):
                    recipe.recipe_steps.append(RecipeText("（{}）{}".format(i + 1, recipe_step_str)))
            
            yield recipe
