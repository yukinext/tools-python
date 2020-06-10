#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 10 07:08:21 2020

@author: yuki_next
"""

import recipe_crawler.models
import jinja2
import logging
import evernote.edam.type.ttypes as Types
import pytz
import datetime
import base64

logger = logging.getLogger(__name__)

def bin_to_base64(b_data):
    return base64.b64encode(b_data).decode('utf-8')

class EvernoteLocalEnexTranslator(object):
    _template = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export3.dtd">
<note><title>{{ note.title }}</title><content><![CDATA[{{ note.content }}]]></content>
<created>{{ note.created }} </created><updated>{{ note.updated }}</updated>
{%- for tag in note.tagNames %}
<tag>{{ tag }}</tag>
{%- endfor %}
{%- if attributes %}
<note-attributes>
{%- if note.attributes.sourceURL %}
<source-url>{{ note.attributes.sourceURL }}</source-url>
{%- endif %}
</note-attributes>
{%- endif %}
{%- for resource in note.resources %}
<resource><data encoding="base64">{{ bin_to_base64(resource.data.body) }}
</data><mime>{{ resource.mime }}</mime><width>{{ resource.width }}</width><height>{{ resource.height }}</height>
<resource-attributes>
{%- if resource.attributes.sourceURL %}
<source-url>{{ resource.attributes.sourceURL }}</source-url>
{%- endif %}
<timestamp>19700101T000000Z</timestamp>
<reco-type>unknown</reco-type>
{%- if resource.attributes.fileName %}
<file-name>{{ resource.attributes.fileName }}</file-name>
{%- endif %}
</resource-attributes>
</resource>
{%- endfor %}
</node>
"""
    def __init__(self, recipe, site_config):
        assert isinstance(recipe, recipe_crawler.models.Recipe)
        self.recipe = recipe
        self.site_config = site_config

    @property
    def enex(self):
        trans = recipe_crawler.translators.EvernoteTranslator(self.recipe, self.site_config)
        note_title = trans.title

        logger.info("create note: {}".format(note_title))
        resources, body = trans.body_resources
        attributes = trans.attributes
        
        note = Types.Note(title=note_title, content=body, resources=resources.values(), attributes=attributes)
        note.tagNames = trans.tag_names
        note.created = datetime.datetime.now().astimezone(pytz.timezone("UTC")).strftime("%Y%m%dT%H%M%SZ")
        note.updated = note.created
        
        tmpl = jinja2.Template(self.__class__._template)
        
        tmpl.globals['bin_to_base64'] = bin_to_base64
        return note.title, tmpl.render(note=note)
