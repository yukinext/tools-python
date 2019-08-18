#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  6 21:30:16 2019

@author: yuki_next
"""
import argparse
import copy
import chardet
import datetime
import requests
from bs4 import BeautifulSoup
import bs4
import logging
import logging.handlers
import yaml
import collections
import os
import pathlib
import sys
import json
import re
import urllib
import time
import hashlib
import mimetypes
import dateutil.parser
import pprint

import jinja2
from evernote.api.client import EvernoteClient
import evernote.edam.type.ttypes as Types
import evernote.edam.notestore.ttypes as NSTypes

import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

log_dir = pathlib.Path("./logs")
log_dir.mkdir(parents=True, exist_ok=True)
handler = logging.handlers.TimedRotatingFileHandler(log_dir / (os.path.splitext(sys.argv[0])[0] + ".log"), when="midnight", backupCount=31)
handler.setFormatter(formatter)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)

handler = logging.StreamHandler()
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

yaml.add_representer(collections.OrderedDict, lambda dumper, instance: dumper.represent_mapping('tag:yaml.org,2002:map', instance.items()))
yaml.add_representer(type(None), lambda dumper, instance: dumper.represent_scalar('tag:yaml.org,2002:null', "~"))
yaml.add_constructor('tag:yaml.org,2002:map', lambda loader, node: collections.OrderedDict(loader.construct_pairs(node)))

class EvernoteTransrator(object):
    default_tag_names = ["recipe", "レシピ"]
    
    _template = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
{%- autoescape true %}
<h1><a href="{{ recipe.detail_url }}">{{ recipe.cooking_name }}</a></h1>
{%- if recipe.cooking_name_sub %}
{{ recipe.cooking_name_sub }}<br />
{%- endif %}
{%- for image_url in recipe.image_urls %}
<en-media type="{{ image_resources[image_url].mime }}" hash="{{ image_resources[image_url].data.bodyHash }}" /><br />
{%- endfor %}

{%- if 0 < recipe.materials|length %}
<h2>材料</h2>
<ul>
{%- for material in recipe.materials %}
    <li>
        <div>{{ material.text }}</div>
{%- for image_url in material.image_urls %}
        <br /><en-media type="{{ image_resources[image_url].mime }}" hash="{{ image_resources[image_url].data.bodyHash }}" />
{%- endfor %}        
{%- for important_point in material.important_points %}
        <br /><strong>{{ important_point }}</strong>
{%- endfor %}        
    </li>
{%- endfor %}
</ul>
{%- endif %}

{%- if 0 < recipe.recipe_steps|length %}
<h2>作り方</h2>
{%- for important_point in recipe.important_points %}
<strong>{{ important_point.text }}</strong><br/>
{%- endfor %}

<ul>
{%- for recipe_step in recipe.recipe_steps %}
    <li>
        <div>{{ recipe_step.text }}</div>
{%- for image_url in recipe_step.image_urls %}
        <br /><en-media type="{{ image_resources[image_url].mime }}" hash="{{ image_resources[image_url].data.bodyHash }}" />
{%- endfor %}        
{%- for important_point in recipe_step.important_points %}
        <br /><strong>{{ important_point }}</strong>
{%- endfor %}        
    </li>
{%- endfor %}
</ul>
{%- endif %}

{%- endautoescape %}
</en-note>
"""

    def __init__(self, recipe, site_config):
        assert isinstance(recipe, Recipe)
        self.recipe = recipe
        self.site_config = site_config

    @property
    def title(self):
        ret = "{}「{}」".format(self.recipe.program_name, self.recipe.cooking_name)
        if self.recipe.program_date:
            ret +=  " {:%Y.%m.%d}".format(self.recipe.program_date)
        return ret

    @property
    def body_resources(self):
        image_resources = dict() # key: image_url, value: resource
        
        image_resources.update(self.__class__._get_create_evernote_resource_dict(self.recipe.image_urls))

        for material in self.recipe.materials:
            image_resources.update(self.__class__._get_create_evernote_resource_dict(material.image_urls))
        
        for recipe_step in self.recipe.recipe_steps:
            image_resources.update(self.__class__._get_create_evernote_resource_dict(recipe_step.image_urls))
        
        return image_resources, jinja2.Template(EvernoteTransrator._template).render(recipe=self.recipe, image_resources=image_resources)
    
    @property
    def tag_names(self):
        ret = set(EvernoteTransrator.default_tag_names)
        ret.add(self.recipe.program_name)
        if self.recipe.program_date:
            ret.add("{:%Y.%m.%d}".format(self.recipe.program_date))
        if self.site_config.get("tag_names"):
            ret.update(self.site_config["tag_names"])
        return ret

    @staticmethod
    def _get_create_evernote_resource_dict(source_urls):
        ret = dict()
        for source_url in source_urls:
            resource = EvernoteTransrator._get_create_evernote_resource(source_url)
            if resource:
                ret[source_url] = resource
        
        return ret

    @staticmethod
    def _get_create_evernote_resource(source_url):
        logger.debug("get: {}".format(source_url))
        res = requests.get(source_url)
        if res.ok:
            attachment_filename = pathlib.Path(urllib.parse.urlparse(source_url).path).name
            return EvernoteTransrator._create_evernote_resource(
                        attachment_filename, res.content, source_url=source_url)
    
    @staticmethod
    def _create_evernote_resource(attachment_filename, byte_data, source_url=None):
        data = Types.Data(
                bodyHash=hashlib.md5(byte_data).hexdigest(),
                size=len(byte_data),
                body=byte_data,
                )
        return Types.Resource(
                data=data,
                mime=mimetypes.guess_type(attachment_filename)[0],
                attributes=Types.ResourceAttributes(
                        sourceURL=source_url,
                        fileName=attachment_filename,
                        ),
                )
    
class Recipe(object):
    def __init__(self):
        self.id = None
        self.detail_url = None
        self.image_urls = list() # original image sourece urls
        self.cooking_name = None # 料理名
        self.cooking_name_sub = None
        self.program_name = None # 番組名
        self.program_date = datetime.date.today() # 番組日付
        self.materials = list() # 材料. value: RecipeText
        self.recipe_steps = list() # 作り方: RecipeText
        self.important_points = list() # RecipeText

    def __repr__(self):
        return self.__class__.__name__ + pprint.pformat(self.__dict__)
    
class RecipeText(object):
    def __init__(self, text, image_urls=None, important_points=None):
        self.text = text
        self.image_urls = image_urls if image_urls else []
        self.important_points = important_points if important_points else []

    def __repr__(self):
        return self.__class__.__name__ + pprint.pformat(self.__dict__)
    
class RecipeCrawlerTemplate(object):
    site_name = ""
    def __init__(self):
        pass

    def init(self, args, site_config):
        self.program_name = site_config["program_name"]
        self.cache_dir = args.work_dir / self.__class__.site_name
        if site_config.get("cache_dir"):
            self.cache_dir = args.work_dir / site_config["cache_dir"]
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
        self.entry_urls = site_config["entry_urls"]
    
        self.processed_list_filename = args.work_dir / "_{}{}".format(self.__class__.site_name, args.processed_list_filename_postfix)
        if site_config.get("processed_list_filename"):
            self.processed_list_filename = pathlib.Path(site_config["processed_list_filename"])
        

    def process(self):
        logger.info("{}: proc start".format(self.__class__.site_name))
        
        recipes = dict() # key: Recipe.id, value: Recipe

        for entry_url in self.entry_urls:
            res = requests.get(entry_url, verify=False)
            if res.ok:
                soup = BeautifulSoup(res.content, "html5lib", from_encoding=res.apparent_encoding)
                recipes.update(self._get_recipe_overviews(soup, entry_url))

        processed_recipe_ids = set()
            
        if self.processed_list_filename.exists():
            with self.processed_list_filename.open() as fp:
                processed_recipe_ids.update([self._trans_to_recipe_id_from_str(l.strip()) for l in fp.readlines() if len(l.strip())])
        
        recipes_num = len(recipes)
        for i, recipe in enumerate(recipes.values()):
            if self._is_existed_recipe(recipe):
                logger.debug("{} ({:05d}/{:05d}): skip: {}".format(self.__class__.site_name, i + 1, recipes_num, recipe.id))
                continue
    
            time.sleep(1)
            res = requests.get(recipe.detail_url, verify=False)
            if res.ok:
                logger.info("{} ({:05d}/{:05d}): get : {}".format(self.__class__.site_name, i + 1, recipes_num, recipe.id))
                (self.cache_dir / str(recipe.id)).open("wb").write(res.content)
        # get detail recipe info
        for target_fn in sorted(self.cache_dir.glob("[!_*]*"), key=lambda k: self._sortkey_cache_filename(k)):
            if not self._is_valid_cache_filename(target_fn):
                logger.debug("{}: skip file : {}".format(self.__class__.site_name, target_fn.name))
                continue
            
            recipe_id = self._get_recipe_id_from_cache_file(target_fn)
            if recipe_id in processed_recipe_ids:
                logger.debug("{}: skip : {}".format(self.__class__.site_name, recipe_id))
                continue
            
            if not recipe_id in recipes:
                logger.warn("{}: not exists in overview. skip recipe id: {}".foramt(self.__class__.site_name, recipe_id))
                continue
            
            try:
                logger.info("{}: start : {}".format(self.__class__.site_name, recipe_id))
                content = target_fn.open("rb").read()
                soup = BeautifulSoup(content, "html5lib", from_encoding=chardet.detect(content)["encoding"])
                
                for detail_recipe in self._recipe_details_generator(soup, recipes[recipe_id]):
                    yield self.processed_list_filename, detail_recipe
                
            except AttributeError:
                logger.exception("not expected format.")
                logger.info("{}: remove : {}".format(self.__class__.site_name, recipe_id))
                new_target_fn = self._get_new_fn(target_fn, "_", 1)
                logger.info("{}: rename : {} -> {}".format(self.__class__.site_name, target_fn.name, new_target_fn.name))
                target_fn.rename(new_target_fn)
    
    def _is_existed_recipe(self, recipe):
        assert isinstance(recipe, Recipe)
        return (self.cache_dir / str(recipe.id)).exists()

    def _get_new_fn(self, from_path, prefix_mark, prefix_times):
        prefix = prefix_mark * prefix_times
        to_path = from_path.with_name(prefix + from_path.name)
        if to_path.exists():
            return self._get_new_fn(from_path, prefix_mark, prefix_times + 1)
        return to_path

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return int(target_id_str)

    def _sortkey_cache_filename(self, target_fn):
        return int(str(target_fn.stem))

    def _is_valid_cache_filename(self, target_fn):
        return target_fn.stem.isdigit()

    def _get_recipe_id_from_cache_file(self, target_fn):
        return int(target_fn.stem)

    def _get_recipe_overviews(self, overview_soup, entry_url):
        pass
    
    def _recipe_details_generator(self, detail_soup, recipe):
        """
        must deepcopy "recipe" before use
        """
        pass

class NhkUmaiRecipeCrawler(RecipeCrawlerTemplate):
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
        for cooking_name_node in detail_soup.find_all("h4"):
            recipe = copy.deepcopy(overview_recipe)
            recipe.cooking_name = cooking_name_node.text
            recipe.image_urls = [urllib.parse.urljoin(recipe.detail_url, node["src"]) for node in cooking_name_node.parent.parent.select('img[src$="jpg"]')]
            
            material_title_node = cooking_name_node.parent.find(text="材料")
            recipe_steps_title_node = cooking_name_node.parent.find(text="作り方")

            recipe.materials = [RecipeText(material[1:]) if material.startswith("・") else RecipeText(material) for material in material_title_node.parent.find_next_sibling().text.splitlines() if len(material.strip())]
            recipe.recipe_steps = [RecipeText(recipe_step) for recipe_step in recipe_steps_title_node.parent.find_next_sibling().text.splitlines() if len(recipe_step.strip())]
            
            if len(recipe.materials) == 0:
                m_buf = list()
                for material in material_title_node.parent.next_siblings:
                    if material == recipe_steps_title_node.parent:
                        break
                    if isinstance(material, bs4.NavigableString):
                        for m in material.replace("\u3000：", "：").replace("\u3000", "\n").strip().splitlines():
                            if len(m):
                                if m.startswith("・"):
                                    m_buf.append(m[1:])
                                else:
                                    m_buf.append(m)
                recipe.materials = [RecipeText(m) for m in m_buf]
            
            if len(recipe.recipe_steps) == 0:
                recipe.recipe_steps = [RecipeText(recipe_step.strip()) for recipe_step in recipe_steps_title_node.parent.next_siblings if isinstance(recipe_step, bs4.NavigableString) and len(recipe_step.strip())]
            
            if len(recipe.recipe_steps) == 0:
                r_buf = list()
                for recipe_step in recipe_steps_title_node.parent.next_siblings:
                    if isinstance(recipe_step, bs4.NavigableString):
                        if len(recipe_step.strip()):
                            r_buf.append(recipe_step.strip())
                    else:
                        r_ = recipe_step.text.strip()
                        if len(r_):
                            for r in r_.splitlines():
                                if len(r):
                                    r_buf.append(r)
                recipe.recipe_steps = [RecipeText(r) for r in r_buf]
            
            yield recipe


class DanshigohanRecipeCrawler(RecipeCrawlerTemplate):
    site_name = "danshigohan"

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.find_all("div", "item"):
            recipe = Recipe()
            recipe.detail_url = item.a["href"]
            recipe.id = int(re.search(r"_(\d+)\.html", recipe.detail_url).group(1))
            recipe.cooking_name = item.h4.text
            recipe.program_name = self.program_name
            recipe.program_date = dateutil.parser.parse(item.find("div", "date").text)
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        recipe.image_urls.append(detail_soup.find("div", "common_contents_box_mini").img["src"])

        material_title_node, recipe_steps_title_node = detail_soup.find_all("h6")
        material_title = material_title_node.text.replace("材料", "").strip()
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        for material in material_title_node.find_next_sibling("ul").find_all("li"):
            recipe.materials.append(RecipeText(": ".join([m.text for m in material.find_all("span")])))

        for recipe_step in recipe_steps_title_node.find_next_sibling("ul").find_all("li"):
            recipe.recipe_steps.append(RecipeText(recipe_step.text.strip()))
        
        yield recipe


class RskCookingRecipeRecipeCrawler(RecipeCrawlerTemplate):
    site_name = "rsk_cooking_recipe"
    
    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.find_all("div", "recipe-piece"):
            recipe = Recipe()
            recipe.detail_url = urllib.parse.urljoin(entry_url, item.a["href"])
            program_date_str = re.search(r"/(\d+)\.html", recipe.detail_url).group(1)
            recipe.id = int(program_date_str)
            recipe.program_name = self.program_name
            recipe.program_date = dateutil.parser.parse(program_date_str)
            recipes[recipe.id] = recipe

        return recipes

    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)
        recipe.cooking_name = detail_soup.strong.text if detail_soup.strong else detail_soup.find_all("b")[1].text
        
        recipe.image_urls.append(urllib.parse.urljoin(recipe.detail_url, detail_soup.select_one('img[src$="jpg"]')["src"]))

        material_title = "（{}）".format(detail_soup.find("td", align="right").b.text.strip())
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        
        for material in detail_soup.find("div","zairyo").text.strip().splitlines():
            if -1 < material.find("監修"):
                break
            if len(material):
                recipe.materials.append(RecipeText(material.replace("…", ": ")))

        for recipe_step in detail_soup.find_all("table")[-2].find_all("td")[1].text.strip().splitlines():
            recipe_step = recipe_step.strip()
            if -1 < recipe_step.find("監修"):
                break

            if len(recipe_step):
                recipe.recipe_steps.append(RecipeText(recipe_step))
        
        yield recipe

class OshaberiRecipeCrawler(RecipeCrawlerTemplate):
    site_name = "oshaberi"

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.select("td .mon,.tue,.wed,.thu,.fri"):
            for link in item.find_all("a"):
                recipe = Recipe()
                recipe.detail_url = urllib.parse.urljoin(entry_url, link["href"])
                program_date_str = re.search(r"/(\d+)\.html", recipe.detail_url).group(1)
                recipe.id = int(program_date_str)
                recipe.cooking_name = link.text.split()[-1]
                recipe.program_name = self.program_name
                recipe.program_date = dateutil.parser.parse(program_date_str)
                recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)
        
        recipe.cooking_name_sub = detail_soup.find("td", "tema").text if detail_soup.find("td", "tema") else None
        recipe.image_urls.append(urllib.parse.urljoin(recipe.detail_url, detail_soup.select_one('img[src$="jpg"]')["src"]))

        recipe_steps_title_node, material_title_node = detail_soup.find_all("table", "text2")
        material_title = "（{}）".format(detail_soup.find("td", "making").text)
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        recipe.materials.extend([RecipeText(tr.text.strip().replace("\n", ": ")) for tr in material_title_node.find_all("tr")])

        recipe.recipe_steps = [RecipeText("（{}）{}".format(i+1, tr.text.strip())) for i, tr in enumerate(recipe_steps_title_node.find_all("tr"))]
        
        yield recipe


class ThreeMinCookingRecipeCrawler(RecipeCrawlerTemplate):
    site_name = "three_minutes_cooking"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return not target_fn.stem.startswith("_")

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _get_recipe_overviews(self, overview_soup, entry_url):
        def get_other_recipe(detail_url):
            res = requests.get(detail_url, verify=False)
            if res.ok:
                soup = BeautifulSoup(res.content, "html5lib", from_encoding=res.apparent_encoding)
                other_recipe_node = soup.select_one("#other-recipe")
                if other_recipe_node:
                    other_recipe = Recipe()
                    other_recipe.detail_url = urllib.parse.urljoin(detail_url, other_recipe_node.a["href"])
                    other_recipe.id = re.search(r".*/(.*)\.html", other_recipe.detail_url).group(1)
                    return other_recipe
        
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in [item for item in overview_soup.find_all("div", "waku") if item.a]:
            recipe = Recipe()
            recipe.detail_url = urllib.parse.urljoin(entry_url, item.a["href"])
            recipe.id = re.search(r".*/(.*)\.html", recipe.detail_url).group(1)
            recipes[recipe.id] = recipe

            other_recipe = get_other_recipe(recipe.detail_url)
            if other_recipe:
                recipes[other_recipe.id] = other_recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)
        recipe.cooking_name = detail_soup.h3.text
        recipe.program_name = self.program_name
        recipe.program_date = dateutil.parser.parse(recipe.id.split("_")[0])

        recipe.image_urls.append(urllib.parse.urljoin(recipe.detail_url, detail_soup.select_one("#thumbnail")["src"]))

        material_title_node = detail_soup.find("div", "ingredient")
        recipe_steps_title_node = detail_soup.find("div", "howto")
        
        material_title = material_title_node.h4.text.replace("材料", "").replace("(", "（").replace(")", "）").strip()
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        for material in material_title_node.find_all("tr"):
            recipe.materials.append(RecipeText(": ".join([m.text for m in material.find_all("td")])))

        for recipe_step in recipe_steps_title_node.find_all("tr"):
            num, step = recipe_step.find_all("td")
            if step.li is None:
                buf = ""
                num = num.text.strip()
                if len(num):
                    buf += "（{}）".format(num)
                buf += step.text.strip()
                
                image_urls = None
                if step.img:
                    image_urls = [urllib.parse.urljoin(recipe.detail_url, step.img["src"])]
                
                recipe.recipe_steps.append(RecipeText(buf, image_urls=image_urls))
            else:  # No.20190824
                # exists sub steps.
                recipe.recipe_steps.append(RecipeText(step.next)) # line.1 is title in sub steps
                for sub_index, step_li in enumerate(step.find_all("li")):
                    image_urls = None
                    if step_li.img:
                        image_urls = [urllib.parse.urljoin(recipe.detail_url, step_li.img["src"])]
                    recipe.recipe_steps.append(RecipeText("（{}）{}".format(sub_index + 1, step_li.text), image_urls=image_urls))
        
        for appendix in detail_soup.find_all("div", "recipe-box"):
            for i, l in enumerate([t.strip() for t in appendix.get_text("\n").splitlines() if len(t.strip())]):
                if l.startswith("・"):
                    l = l[1:].strip()
                
                if i:
                    l = "　{}".format(l)
                
                recipe.important_points.append(RecipeText(l))
        
        yield recipe


class OishimeshiRecipeCrawler(RecipeCrawlerTemplate):
    site_name = "oishimeshi"

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.find_all("div", "titletext"):
            recipe = Recipe()
            tmp = item.find("p", "title")
            recipe.detail_url = tmp.a["href"]
            program_date_str = re.search(r"date=(\d+)\D?", recipe.detail_url).group(1)
            recipe.id = int(program_date_str)
            recipe.cooking_name = tmp.text
            recipe.program_name = self.program_name
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
        material_title = material_title_node.p.text.replace("材料", "").replace("（", "（").replace(")", "）").strip()
        if material_title:
            recipe.materials.append(RecipeText(material_title))
        recipe.materials.extend([RecipeText(": ".join([mm.text for mm in m.find_all("td") if len(mm.text.strip())])) for m in material_title_node.find_all("tr")])

        for recipe_step in recipe_steps_title_node.find_all("tr"):
            num, text, point = recipe_step.find_all("td")
            recipe.recipe_steps.append("（{}）{}".format(num.text.strip(), text.text.strip()))
            if len(point.text.strip()):
                recipe.recipe_steps.append(RecipeText(point.text.strip()))
        
        yield recipe

class NhkKamadoRecipeCrawler(RecipeCrawlerTemplate):
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


class NikomaruKitchenRecipeCrawler(RecipeCrawlerTemplate):
    site_name = "nikomaru"

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        for item in overview_soup.find_all("dl"):
            recipe = Recipe()
            name, date, _ = item.find_all("dd")
            recipe.detail_url = urllib.parse.urljoin(entry_url, name.a["href"])
            recipe.id = int(re.search(r".*/(\d+)$", recipe.detail_url).group(1))
            recipe.cooking_name = name.text
            recipe.program_name = self.program_name
            recipe.program_date = datetime.date(*[int(v) for v in re.match(r"(\d+)\D+(\d+)\D+(\d+)\D*", date.text).groups()])
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        recipe.image_urls.append(urllib.parse.urljoin(recipe.detail_url, detail_soup.find("div", "photo").img["src"]))

        material_title_node = detail_soup.find("div", "material")
        material_title = material_title_node.h4.text.replace("材料", "").strip()
        if material_title:
            recipe.materials.append(RecipeText("（{}）".format(material_title)))
        for material in material_title_node.find_all("li"):
            texts = [m.text for m in material.find_all("span")]
            if "".join([t.strip() for t in texts]) == "":
                continue
            recipe.materials.append(RecipeText(": ".join(texts)))

        recipe_steps_title_node = detail_soup.find("div", "make")

        for i, recipe_step in enumerate(recipe_steps_title_node.find_all("li")):
            for j, l in enumerate(recipe_step.text.splitlines()):
                if j == 0:
                    recipe.recipe_steps.append(RecipeText("（{}）{}".format(i + 1, l)))
                    continue                
                recipe.recipe_steps.append(RecipeText(l))
        
        yield recipe

class NhkKobaraSuitemasenkaRecipeCrawler(RecipeCrawlerTemplate):
    site_name = "nhk_kobara_ka"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return not target_fn.stem.startswith("_")

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        items = iter(overview_soup.find_all("section")[1:-1])
        for item in items:
            subtitle_node = item
            title_node = next(items)
            recipe = Recipe()
            recipe.detail_url = entry_url
            recipe.cooking_name = title_node.h2.text.replace("「", "").replace("」", "").strip()
            recipe.cooking_name_sub = subtitle_node.h2.text.strip()
            recipe.program_name = self.program_name
            recipe.program_date = None
            recipe.image_urls.append(urllib.parse.urljoin(entry_url, title_node.img["src"]))
            
            is_material_area = False
            is_recipe_step_area = False
            for l in title_node.find("div", "option-media-row").get_text("\n").splitlines():
                if len(l.strip()) == 0:
                    continue
                
                if -1 < l.find("＜材料＞"):
                    is_material_area = True
                    recipe.materials.append(RecipeText(l.replace("＜材料＞", "").replace("(", "（").replace(")", "）")))
                    continue
                if -1 < l.find("＜作り方＞"):
                    is_material_area = False
                    is_recipe_step_area = True
                    continue
                
                if is_material_area:
                    recipe.materials.extend([RecipeText(m.replace(":", ": ")) for m in l.split()])
                elif is_recipe_step_area:
                    recipe.recipe_steps.append(RecipeText(l))
                    
            recipe.id = hashlib.md5("{}/{}".format(recipe.cooking_name_sub, recipe.cooking_name).encode("utf-8")).hexdigest()            
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        yield recipe


class NhkKobaraGaSukimashitaRecipeCrawler(RecipeCrawlerTemplate):
    site_name = "nhk_kobara_ta"

    def _trans_to_recipe_id_from_str(self, target_id_str):
        return target_id_str

    def _sortkey_cache_filename(self, target_fn):
        return target_fn.stem

    def _is_valid_cache_filename(self, target_fn):
        return not target_fn.stem.startswith("_")

    def _get_recipe_id_from_cache_file(self, target_fn):
        return target_fn.stem

    def _get_recipe_overviews(self, overview_soup, entry_url):
        recipes = dict() # key: Recipe.id, value: Recipe
        
        current_subtitle = None
        current_recipe_important_points = list()
        for item in overview_soup.find_all("section")[1:]:
            if item.table:
                continue
            
            if item.h1:
                continue
            
            if item.h2:
                current_subtitle = item.h2.text.replace("「", "").replace("」", "").strip()
                current_recipe_important_points.clear()
                continue
            
            if item.p is None:
                continue
            
            recipe = Recipe()
            recipe.detail_url = entry_url
            recipe.program_name = self.program_name
            recipe.program_date = None
            
            if item.img is None:
                for l in item.p.get_text("\n").splitlines():
                    current_recipe_important_points.append(RecipeText(l))
                continue
            
            if item.h3:
                # multiple recipe
                recipe.cooking_name = item.h3.text
                recipe.cooking_name_sub = current_subtitle
            else:
                # single recipe
                recipe.cooking_name = current_subtitle
            
            recipe.important_points.extend(current_recipe_important_points)
            recipe.image_urls.append(urllib.parse.urljoin(entry_url, item.img["src"]))
                
            is_material_area = False
            is_recipe_step_area = False
            # for l in item.find("div", "option-media-row").get_text("\n").splitlines():
            for l in item.p.get_text("\n").splitlines():
                if len(l.strip()) == 0:
                    continue
                
                if -1 < l.find("◎材料"):
                    is_material_area = True
                    material_title = l.replace("◎材料", "").replace("(", "（").replace(")", "）").strip()
                    if len(material_title):
                        recipe.materials.append(RecipeText(material_title))
                    continue
                if -1 < l.find("＜作り方＞"):
                    is_material_area = False
                    is_recipe_step_area = True
                    continue
                
                if is_material_area:
                    l = l.replace(" 本", "本").replace(" 個", "個")
                    recipe.materials.extend([RecipeText(m.replace(":", ": ")) for m in l.split()])
                elif is_recipe_step_area:
                    m = re.match(r"(\d+).\s*(.*)", l)
                    if m:
                        gs = m.groups()
                        num = int(gs[0])
                        recipe_step = gs[1]
                        recipe.recipe_steps.append(RecipeText("（{}）{}".format(num, recipe_step)))
                    else:
                        recipe.recipe_steps.append(RecipeText(l))

            recipe.id = hashlib.md5(("{}/{}".format(recipe.cooking_name_sub, recipe.cooking_name) if recipe.cooking_name_sub else recipe.cooking_name).encode("utf-8")).hexdigest()            
            recipes[recipe.id] = recipe

        return recipes
    
    def _recipe_details_generator(self, detail_soup, overview_recipe):
        """
        must deepcopy "recipe" before use
        """
        recipe = copy.deepcopy(overview_recipe)

        yield recipe


def store_evernote(recipes, args, site_config, evernote_cred, is_note_exist_check=True):
    client = EvernoteClient(token=evernote_cred["developer_token"], sandbox=evernote_cred["is_sandbox"])
    note_store = client.get_note_store()
    
    notebook_name = evernote_cred["notebook_name"]
    notebooks = note_store.listNotebooks()
    target_notebook = None
    for notebook in notebooks:
        if notebook_name == notebook.name:
            target_notebook = notebook
            break
    
    if target_notebook is None:
        logger.info("create notebook: {}".format(notebook_name))
        target_notebook = Types.Notebook()
        target_notebook.name = notebook_name
        target_notebook = note_store.createNotebook(target_notebook)

    # for processed_list_filename, recipe in recipes(args, site_config):
    for processed_list_filename, recipe in recipes():
        trans = EvernoteTransrator(recipe, site_config)
        note_title = trans.title

        is_note_exist = False
        if is_note_exist_check:
            filter = NSTypes.NoteFilter()
            filter.notebookGuid = target_notebook.guid        
            resultSpec = NSTypes.NotesMetadataResultSpec()
            resultSpec.includeTitle = True
            metalist = note_store.findNotesMetadata(filter, 0, 10, resultSpec)
    
            for meta_ in metalist.notes:
                if note_title == meta_.title:
                    logger.debug("skip: {} exists.".format(note_title))
                    is_note_exist = True
                    break
        if not is_note_exist:
            logger.info("create note: {}".format(note_title))
            resources, body = trans.body_resources
            note = Types.Note(title=note_title, content=body, resources=resources.values(), notebookGuid=target_notebook.guid)
            note.tagNames = trans.tag_names
            note_store.createNote(note)
            
            with processed_list_filename.open("a") as fp:
                fp.write("{}\n".format(recipe.id))
        
            time.sleep(1)

def _get_evernote_credential(credential_json_filename):
    if not credential_json_filename.exists():
        logger.debug("credential file not found: {}".format(credential_json_filename))
        return None
    
    j = None
    with credential_json_filename.open("r") as fp:
        j = json.load(fp)
    
    if not "evernote" in j:
        logger.debug("\"evernote\" not found in credential file: {}".format(credential_json_filename))
        return None
    
    cred = j["evernote"]
    if "enable" in cred and cred["enable"] == False:
        logger.debug("\"evernote.enable\" is disable in credential file: {}".format(credential_json_filename))
        return None
    
    if all(key in cred for key in ("sandbox", "developer_token", "notebook_name")):
        return {
            "is_sandbox": cred["sandbox"],
            "developer_token": cred["developer_token"],
            "notebook_name": cred["notebook_name"],
        }
    else:
        logger.debug('"sandbox" or "developer_token" or "notebook_name" are not exists in "evernote" section in credential file: {}'.format(credential_json_filename))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sites", nargs="*", help="site name in config yaml file. no input is select all sites")
    parser.add_argument("--view", action="store_true")
    parser.add_argument("--config-yaml-filename", default=pathlib.Path(sys.argv[0]).parent / "config.yml", type=pathlib.Path)
    parser.add_argument("--work-dir", default=pathlib.Path(sys.argv[0]).parent / ".work_recipes", type=pathlib.Path, help="working directory")
    parser.add_argument("--credential-json-filename", default=pathlib.Path(sys.argv[0]).parent / "cred.json", type=pathlib.Path)
    parser.add_argument("--no-check-existed-note", action="store_true", help="no check existed notes and append new note. if do not check existed note and skip.")
    parser.add_argument("--processed-list-filename-postfix", default="_processed_data.txt")

    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    
    if not args.config_yaml_filename.exists():
        logger.error("not exists config file: {}".format(args.config_yaml_filename))
        return

    recipe_crawlers = dict([(crawler.site_name, crawler) for crawler in [
            NhkUmaiRecipeCrawler(),
            DanshigohanRecipeCrawler(),
            RskCookingRecipeRecipeCrawler(),
            OshaberiRecipeCrawler(),
            ThreeMinCookingRecipeCrawler(),
            OishimeshiRecipeCrawler(),
            NhkKamadoRecipeCrawler(),
            NikomaruKitchenRecipeCrawler(),
            NhkKobaraSuitemasenkaRecipeCrawler(),
            NhkKobaraGaSukimashitaRecipeCrawler(),
            ]])

    config = yaml.load(args.config_yaml_filename.open("r").read())
    if args.view:
        view_results = dict()
        for site, site_config in config.items():
            if len(args.sites):
                for a_site in args.sites:
                    if not a_site in view_results:
                        view_results[a_site] = list()
                    if -1 < site.find(a_site):
                        view_results[a_site].append((site, site_config))
            else:
                if not "" in view_results:
                    view_results[""] = list()
                view_results[""].append((site, site_config))
        pprint.pprint(view_results)
        return
    
    evernote_cred = _get_evernote_credential(args.credential_json_filename)
    if args.sites is None or len(args.sites) == 0:
        args.sites = [key for key in config.keys()]
    
    for site in args.sites:
        if site in config and site in recipe_crawlers:
            site_config = config[site]
            if site_config["enable"]:
                recipe_crawler = recipe_crawlers[site]
                recipe_crawler.init(args, site_config)
                store_evernote(recipe_crawler.process, args, site_config, evernote_cred, is_note_exist_check=not args.no_check_existed_note)
            else:
                logger.warning("disable: {}".format(site))
        else:
            logger.warning("not exist: {}".format(site))
                    

if __name__ == "__main__":
    main()