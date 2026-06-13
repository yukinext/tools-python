#!/usr/bin/env python3
"""
Created on Fri Aug 30 22:10:59 2019

@author: yuki_next

"""

import copy
import datetime
import logging
import pathlib
import re
import urllib

import dateutil

from recipe_crawler.models import Recipe, RecipeText

from . import bases

logger = logging.getLogger(__name__)


class KtvNijiiroRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "ktv_niji"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return True

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _expand_entry_urls(self):
        ret = set()
        entry_url_base = self.entry_urls[0]
        base = datetime.date.today()
        for d in range(0, 5):
            offset = -1 - d
            target = base + dateutil.relativedelta.relativedelta(weekday=dateutil.relativedelta.SA(offset))
            ret.add(urllib.parse.urljoin(entry_url_base, f"/niji/{target:%y%m%d}.html"))

        return ret

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipe_title_node = overview_soup.find("h2", text=re.compile(r"レシピ.*"))
        if recipe_title_node is None:
            logger.info(f"{entry_url} have no recipe.")
            return dict()

        recipe_root_node = recipe_title_node.parent

        recipes = dict()  # key: Recipe.id, value: Recipe
        for ii, recipe_node in enumerate([h3.parent for h3 in recipe_root_node.find_all("h3")]):
            recipe = Recipe()

            recipe.program_date = dateutil.parser.parse(f"20{pathlib.Path(entry_url).stem}")
            recipe.program_name = self.program_name
            recipe.detail_url = entry_url
            recipe.cooking_name = recipe_node.h3.text
            recipe.image_urls.append(
                urllib.parse.urljoin(
                    entry_url, re.search(r"background-image:url\((.*?)\);", recipe_node.img["style"]).group(1)
                )
            )

            is_material_area = False
            is_recipe_step_area = False
            for l in recipe_node.find_all("p")[1].text.splitlines():
                if len(l.strip()) == 0:
                    continue

                if -1 < l.find("【材料】"):
                    if is_recipe_step_area == False:
                        is_material_area = True
                        l = l.replace("【材料】", "").translate(self.__class__._TABLE_REPLACE_MARUKAKKO).strip()
                        if len(l):
                            recipe.materials.append(RecipeText(l))
                        continue
                if -1 < l.find("【作り方】"):
                    is_material_area = False
                    is_recipe_step_area = True
                    continue

                if is_material_area:
                    material = l.replace("：", ": ")
                    recipe.materials.append(RecipeText(material))
                elif is_recipe_step_area:
                    recpe_step_text = l
                    m = re.match(r"^(\d+)(.*)", l)
                    if m:
                        num, recipe_t = m.groups()
                        recpe_step_text = f"（{num}）{recipe_t.strip()}"
                    recipe.recipe_steps.append(RecipeText(recpe_step_text))

            recipe.id = f"{recipe.program_date:%Y%m%d}_{ii}"

            recipes[recipe.id] = recipe

        return recipes

    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        yield recipe
