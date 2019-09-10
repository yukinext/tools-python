#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 21:15:51 2019

@author: yuki_next
"""

import datetime
import pprint

class Recipe(object):
    def __init__(self):
        self.id = None
        self.detail_url = None
        self.image_urls = list() # original image source urls
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