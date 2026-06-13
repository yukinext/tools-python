#!/usr/bin/env python3
"""
Created on Fri Aug 30 21:15:51 2019

@author: yuki_next
"""

import datetime
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecipeText:  # レシピ内の各ステップに対応するテキストと画像URLを格納するクラス
    text: str  # ステップのテキスト
    image_urls: list[str] = field(default_factory=list)  # ステップに紐づく画像のURLリスト
    important_points: list[str] = field(default_factory=list)  # ステップの重要なポイントのリスト


@dataclass
class Recipe:
    id: Any | None  # レシピID. 形式はサイトごとに異なるが、基本的にはURLの一部を使用することが多い
    detail_url: str | None  # レシピの詳細ページURL
    cooking_name: str | None  # 料理名
    cooking_name_sub: str | None  # 料理名のサブタイトル（あれば）
    program_name: str | None  # 番組名
    image_urls: list[str] = field(default_factory=list)  # レシピ全体に紐づく画像のURLリスト
    program_date: datetime.date = datetime.date.today()  # 番組日付
    materials: list[RecipeText] = field(default_factory=list)  # 材料. value: RecipeText
    recipe_steps: list[RecipeText] = field(default_factory=list)  # 作り方: RecipeText
    important_points: list[RecipeText] = field(default_factory=list)  # 重要なポイント: RecipeText
