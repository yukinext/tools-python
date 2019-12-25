#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:48:13 2019

@author: yuki_next
"""

from . import bases
from recipe_crawler.models import Recipe, RecipeText
import io
import re
import pathlib
import logging
import dateutil
import copy
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTContainer, LTTextBox
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage

logger = logging.getLogger(__name__)

class NhkNoukameshiRecipeCrawler(bases.RecipeCrawlerTemplate):
    site_name = "nhk_noukameshi"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return True

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        links = [a for a in overview_soup.find_all("a") if a.text == "レシピ"]
        for link in links:
            recipe = Recipe()
            recipe.detail_url = link["href"]
            recipe.id = pathlib.Path(recipe.detail_url).stem
            recipe.program_name = self.program_name
            recipes[recipe.id] = recipe
            
        return recipes
    
    def _convert_detail_content(self, raw_content):
        # Layout Analysisのパラメーターを設定。縦書きの検出を有効にする。
        laparams = LAParams(detect_vertical=True)
        
        # 共有のリソースを管理するリソースマネージャーを作成。
        resource_manager = PDFResourceManager()
        
        # ページを集めるPageAggregatorオブジェクトを作成。
        device = PDFPageAggregator(resource_manager, laparams=laparams)
        
        # Interpreterオブジェクトを作成。
        interpreter = PDFPageInterpreter(resource_manager, device)

        ret = ""
        for page in PDFPage.get_pages(io.BytesIO(raw_content)):
            interpreter.process_page(page)
            layout = device.get_result()
            boxes = NhkNoukameshiRecipeCrawler.find_textboxes_recursively(layout)
            boxes.sort(key=lambda b: (-b.y1, b.x0))
            for box in boxes:
                tmp = box.get_text()
                if len(tmp.strip()):
                    if len(tmp.strip()) == 1:
                        ret += "\n" + tmp.strip()
                    else:
                        ret += tmp
        return ret
            
    
    def _recipe_details_generator(self, converted_content, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        def get_cooking_shop_strings(lines):
            ret = []
            buf = None
            is_recipe_step_area = False
            for l in lines:
                if re.search("軒目", l.strip()) or re.match(r"^[①-⑳＊].*『.*』", l.strip()) or re.match(r"^[①-⑳＊].*「.*」", l.strip()):
                    if buf:
                        ret.append(buf)
                    buf = l.strip()
                    continue

                if re.search("^料理", l.strip()):
                    is_recipe_step_area = False

                if re.search("^材料", l.strip()):
                    title, materials = re.search("(材料)(.*)", l.strip()).groups()
                    # buf += "\n" + "\n".join(l.strip().split(None, 1))
                    buf += "\n" + title + "\n" + materials.strip()
                    continue

                if re.search("^作り方", l.strip()):
                    is_recipe_step_area = True
                    title, recipe_steps = re.search("(作り方)(.*)", l.strip()).groups()
                    # buf += "\n" + "\n".join(l.strip().split(None, 1))
                    buf += "\n" + title + "\n" + recipe_steps.strip()
                    continue
                
                if buf:
                    if is_recipe_step_area:
                        if re.match(r"^[①-⑳＊]", l.strip()):
                            buf += "\n" + l.strip()
                        else:
                            buf += l.strip()
                    else:
                        buf += "\n" + l.strip()
            if buf:
                ret.append(buf)

            return ret
            
            
        for ii, l in enumerate(converted_content.splitlines()):
            if ii == 1:
                overview_recipe.cooking_name_sub = l.strip()
                continue
            
            if -1 < l.find("初回放送"):
                overview_recipe.program_date = dateutil.parser.parse("/".join(re.search(r"(\d+)\D+(\d+)\D+(\d+)\D+", l).groups()))
                break

        cooking_shop_strings = get_cooking_shop_strings(converted_content.splitlines())

        logger.debug("-" * 20)
        logger.debug(cooking_shop_strings)
        for shop_string in cooking_shop_strings:
            recipe_shop = None
            recipe = None
            is_material_area = False
            is_recipe_step_area = False
            for l in shop_string.splitlines():
                if len(l.strip()) == 0:
                    continue
                
                if is_material_area == False and is_recipe_step_area == False:
                    if re.search("軒目", l.strip()) or re.match(r"^[①-⑳＊].*『.*』", l.strip()) or re.match(r"^[①-⑳＊].*「.*」", l.strip()):
                        recipe_shop = copy.deepcopy(overview_recipe)
                        recipe = None
    
                        m = re.search(r"「(.*)」", l)
                        if m:
                            recipe_shop.cooking_name_sub += "/" + m.group(1)
                        else:
                            m2 = re.search(r"『(.*)』", l)
                            if m2:
                                recipe_shop.cooking_name_sub += "/" + m2.group(1)
                                
                        continue
                
                if re.search("^料理", l.strip()):
                    is_material_area = False
                    is_recipe_step_area = False
                    if recipe:
                        yield recipe

                    if recipe_shop:
                        recipe = copy.deepcopy(recipe_shop)
                    else:
                        recipe = copy.deepcopy(overview_recipe)
                    
                    if -1 < l.find(":"):
                        recipe.cooking_name = l.split(":")[1].strip()
                    elif -1 < l.find("："):
                        recipe.cooking_name = l.split("：")[1].strip()
                    else:
                        recipe.cooking_name = l.split(None, 1)[1].strip()
                    continue
                
                if re.search("^材料", l.strip()):
                    is_material_area = True
                    is_recipe_step_area = False
                    if l.strip() == "材料":
                        continue
                
                if re.search("^作り方", l.strip()):
                    is_material_area = False
                    is_recipe_step_area = True
                    if l.strip() == "作り方":
                        pass
                    else:
                        l = l.replace("作り方", "", 1)
                        # recipeがNoneの場合はエラーとして検出したい
                        recipe.recipe_steps.append(RecipeText(l.strip()))
                    continue
                        
    
                if is_material_area:
                    for material in l.strip().split("、"):
                        material = material.strip()
                        if len(material):
                            if material.startswith("("):
                                recipe.materials.append(RecipeText(material))
                            else:
                                recipe.materials.append(RecipeText(material.replace("（", ": ").replace("）", "")))
                
                if is_recipe_step_area:
                    recipe.recipe_steps.append(RecipeText(l.strip()))
            if recipe:
                yield recipe
            
    @classmethod
    def find_textboxes_recursively(cls, layout_obj):
        """
        再帰的にテキストボックス（LTTextBox）を探して、テキストボックスのリストを取得する。
        """
        # LTTextBoxを継承するオブジェクトの場合は1要素のリストを返す。
        if isinstance(layout_obj, LTTextBox):
            return [layout_obj]
    
        # LTContainerを継承するオブジェクトは子要素を含むので、再帰的に探す。
        if isinstance(layout_obj, LTContainer):
            boxes = []
            for child in layout_obj:
                boxes.extend(NhkNoukameshiRecipeCrawler.find_textboxes_recursively(child))
    
            return boxes
    
        return []  # その他の場合は空リストを返す。
