#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:26:59 2019

@author: yuki_next
"""

import recipe_crawler.models
import jinja2
import logging
import evernote.edam.type.ttypes as Types
import requests
import pathlib
import urllib
import hashlib
import mimetypes

logger = logging.getLogger(__name__)

class EvernoteTranslator(object):
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
        {%- set recipe_step_ls = recipe_step.text.splitlines() %}
        {%- for recipe_step_l in recipe_step_ls %}
        <div>{{ recipe_step_l }}</div>
        {%- endfor %}
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
        assert isinstance(recipe, recipe_crawler.models.Recipe)
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
        
        return image_resources, jinja2.Template(self.__class__._template).render(recipe=self.recipe, image_resources=image_resources)
    
    @property
    def attributes(self):
        ret = Types.NoteAttributes()
        ret.sourceURL = self.recipe.detail_url
        
        return ret
    
    @property
    def tag_names(self):
        ret = set(self.__class__.default_tag_names)
        ret.add(self.recipe.program_name)
        if self.recipe.program_date:
            ret.add("{:%Y.%m}".format(self.recipe.program_date))
            ret.add("{:%Y}".format(self.recipe.program_date))
        if self.site_config.get("tag_names"):
            ret.update(self.site_config["tag_names"])
        return ret

    @staticmethod
    def _get_create_evernote_resource_dict(source_urls):
        ret = dict()
        for source_url in source_urls:
            resource = EvernoteTranslator._get_create_evernote_resource(source_url)
            if resource:
                ret[source_url] = resource
        
        return ret

    @staticmethod
    def _get_create_evernote_resource(source_url):
        logger.debug("get: {}".format(source_url))
        res = requests.get(source_url)
        if res.ok:
            attachment_filename = pathlib.Path(urllib.parse.urlparse(source_url).path).name
            return EvernoteTranslator._create_evernote_resource(
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
    
