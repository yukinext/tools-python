#!/usr/bin/env python3
"""
Created on Fri Aug 30 22:01:23 2019

@author: yuki_next
"""

import copy
import logging
import re
from typing import Any

import bs4
import dateutil

from recipe_crawler.models import Recipe, RecipeText

from . import bases

logger = logging.getLogger(__name__)


class OishimeshiRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "oishimeshi"

    def _get_recipe_overviews(self, overview_soup: bs4.BeautifulSoup, entry_url: str) -> dict[Any, Recipe]:
        recipes = dict()  # key: Recipe.id, value: Recipe
        for item in overview_soup.find_all("div", "titletext"):
            tmp = item.find("p", "title")
            recipe = Recipe(
                detail_url=tmp.a["href"],
                id=None,
                cooking_name=tmp.text,
                cooking_name_sub=None,
                program_name=self.program_name,
            )
            if recipe.detail_url:
                m = re.search(r"date=(\d+)\D?", recipe.detail_url)
                if m:
                    program_date_str = m.group(1)
                    recipe.id = int(program_date_str)
                    recipe.program_date = dateutil.parser.parse(program_date_str)
            recipes[recipe.id] = recipe

        return recipes

    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        material_title_node = detail_soup.select_one("#zairyou_box")
        recipe_steps_title_node = detail_soup.find("table", "recipe")
        material_title = (
            material_title_node.p.text.replace("材料", "").translate(self.__class__._TABLE_REPLACE_MARUKAKKO).strip()
        )
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        recipe.materials.extend(
            [
                RecipeText(": ".join([mm.text for mm in m.find_all("td") if len(mm.text.strip())]))
                for m in material_title_node.find_all("tr")
            ]
        )

        for recipe_step in recipe_steps_title_node.find_all("tr"):
            num, text, point = recipe_step.find_all("td")
            recipe.recipe_steps.append(RecipeText(f"（{num.text.strip()}）{text.text.strip()}"))
            if len(point.text.strip()):
                recipe.recipe_steps.append(RecipeText(point.text.strip()))

        yield recipe
