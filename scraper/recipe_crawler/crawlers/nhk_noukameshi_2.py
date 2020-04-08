#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:48:13 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import re
import logging
import dateutil
import json
import chardet
import copy

logger = logging.getLogger(__name__)

class NhkNoukameshi2RecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "nhk_noukameshi_2"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return True

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _convert_overview_content(self, raw_content):
        return json.loads(raw_content, encoding=chardet.detect(raw_content))

    def _get_recipe_overviews(self, jdata, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in jdata["result"]:
            recipe = Recipe()
            recipe.detail_url = item["url"]
            recipe.id = item["id"]
            recipe.cooking_name_sub = item["identifierGroup"]["episodeName"][1:-1]
            recipe.program_name = self.program_name
            for be in item["broadcastEvent"]:
                if be["misc"]["releaseLevel"] == "original":
                    program_date_str = be["identifierGroup"]["date"]
                    recipe.program_date = dateutil.parser.parse(program_date_str).date()
                    recipe.id = "{}_{}".format(program_date_str, item["id"])
            recipes[recipe.id] = recipe
        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        def convert_material(material_s):
            m = re.match(r"(.*)[\(（](.*)[\)）]", material_s)
            if m:
                return ": ".join(m.groups())
            return material_s
        
        recipe_title_node = detail_soup.find("span", text=re.compile(r".*レシピは？"))
        if recipe_title_node is None:
            return
        
        subtitle = None
        recipe = None
        is_recipe_step_area = False
        recipe_counter = 0
        for line_ in recipe_title_node.parent.find_next_sibling("ul").text.replace("　", " ").splitlines():
            line_ = line_.strip()
            if len(line_) == 0:
                continue
            
            m_subtitle = re.match(r".*?軒目\s*「(.*?)」", line_)
            if m_subtitle:
                if recipe:
                    yield recipe
                subtitle = m_subtitle.group(1)
                recipe = None
                is_recipe_step_area = False
                continue
            
            m_title = re.match(r"^料理.*?：(.*)", line_)
            if m_title:
                if recipe:
                    yield recipe
                is_recipe_step_area = False
                title = m_title.group(1)
                recipe = copy.deepcopy(overview_recipe)
                recipe.cooking_name = title
                recipe.cooking_name_sub = "{}/{}".format(recipe.cooking_name_sub, subtitle)
                recipe.id = "{}_{}".format(recipe.id, recipe_counter)
                recipe_counter += 1
                continue
            
            m_material = re.match(r"材料\s*(.*)", line_)
            if m_material:
                material = m_material.group(1)
                recipe.materials.extend([RecipeText(convert_material(material_s)) for material_s in material.split("、")])
                # material area is 1 line.
                continue
            
            m_recipe_step = re.match(r"作り方\s*(.*)", line_)
            if m_recipe_step:
                is_recipe_step_area = True
                recipe.recipe_steps.append(RecipeText(m_recipe_step.group(1).strip()))
                continue
            
            if is_recipe_step_area:
                recipe.recipe_steps.append(RecipeText(line_.strip()))
                continue
        
        if recipe:
            yield recipe