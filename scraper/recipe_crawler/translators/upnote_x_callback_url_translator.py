#!/usr/bin/env python3
"""
Created on Sat Jul 20 19:51:50 2024

@author: yuki_next
"""

import base64
import logging
import re

import recipe_crawler.models

logger = logging.getLogger(__name__)


def bin_to_base64(b_data):
    return base64.b64encode(b_data).decode("utf-8")


class UpnoteXCallbackUrlTranslator:
    default_tag_names = ["recipe", "レシピ"]

    _template = """{%- autoescape true %}
# [{{ recipe.cooking_name }}]({{ recipe.detail_url }})
{%- if recipe.cooking_name_sub %}
{{ recipe.cooking_name_sub }}  
{%- endif %}
{%- for image_url in recipe.image_urls %}
{%- if image_url in image_resources %}
[]({{ image_resources[image_url].data.bodyHash }})
{%- endif %}
{%- endfor %}
    
    
    
    <?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
{%- autoescape true %}
<h1><a href="{{ recipe.detail_url }}">{{ recipe.cooking_name }}</a></h1>
{%- if recipe.cooking_name_sub %}
{{ recipe.cooking_name_sub }}<br />
{%- endif %}
{%- for image_url in recipe.image_urls %}
{%- if image_url in image_resources %}
<en-media type="{{ image_resources[image_url].mime }}" hash="{{ image_resources[image_url].data.bodyHash }}" /><br />
{%- endif %}
{%- endfor %}

{%- if 0 < recipe.materials|length %}
<h2>材料</h2>
<ul>
{%- for material in recipe.materials %}
    <li>
        <div>{{ material.text }}</div>
{%- for image_url in material.image_urls %}
{%- if image_url in image_resources %}
        <br /><en-media type="{{ image_resources[image_url].mime }}" hash="{{ image_resources[image_url].data.bodyHash }}" />
{%- endif %}
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
<ul>
{%- for recipe_step in recipe.recipe_steps %}
    <li>
        {%- set recipe_step_ls = recipe_step.text.splitlines() %}
        {%- for recipe_step_l in recipe_step_ls %}
        <div><p>{{ recipe_step_l }}</p></div>
        {%- endfor %}
{%- for image_url in recipe_step.image_urls %}
{%- if image_url in image_resources %}
        <br /><en-media type="{{ image_resources[image_url].mime }}" hash="{{ image_resources[image_url].data.bodyHash }}" />
{%- endif %}
{%- endfor %} 
{%- for important_point in recipe_step.important_points %}
        <br /><strong>{{ important_point }}</strong>
{%- endfor %}        
    </li>
{%- endfor %}
</ul>
{%- endif %}

{%- for important_point in recipe.important_points %}
<strong>{{ important_point.text }}</strong><br/>
{%- endfor %}

{%- endautoescape %}
</en-note>
"""

    def __init__(self, recipe, site_config):
        assert isinstance(recipe, recipe_crawler.models.Recipe)
        self.recipe = recipe
        self.site_config = site_config

    @property
    def title(self):
        ret = f"{self.recipe.program_name}「{self.recipe.cooking_name}」"
        if self.recipe.program_date:
            ret += f" {self.recipe.program_date:%Y.%m.%d}"
        return ret

    @property
    def tag_names(self):
        ret = set(self.__class__.default_tag_names)
        ret.add(self.recipe.program_name)
        if self.recipe.program_date:
            ret.add(f"{self.recipe.program_date:%Y-%m}")
            ret.add(f"{self.recipe.program_date:%Y}")
        if self.site_config.get("tag_names"):
            ret.update(self.site_config["tag_names"])
        return [re.sub(r"[¥s¥.]", "-", t) for t in ret]
