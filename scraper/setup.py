#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

from setuptools import setup, find_packages

# Requirements.
setup_requirements = ['pytest-runner'] if {'pytest', 'test', 'ptr'}.intersection(sys.argv) else []
test_requirements = ['pytest', 'pytest-pep8', 'pytest-flakes']

# Fetch readme content.
with open('docs/README.rst', 'r') as readme_file:
    readme = readme_file.read()


def main():
    setup(name='recipe_cralwer',
          packages=find_packages(),
          version='0.0.1',
          description='Recipe Site Crawler',
          long_description=readme,
          author='Yuki',
          author_email='yuki_next@mac.com',
          url='https://github.com/yukinext/tools-python/tree/master/scraper',
          download_url='https://github.com/yukinext/tools-python/',
          license="MIT",
          setup_requires=setup_requirements,
          install_requires=[],
          tests_require=test_requirements,
          extras_require={
              'test': test_requirements
          },
          include_package_data=True,
          keywords='Python, Python3, web scraping, crawler, cooking recipe',
          classifiers=['Development Status :: 5 - Production/Stable',
                       'Intended Audience :: Developers',
                       'Natural Language :: Japanese',
                       'License :: OSI Approved :: MIT License',
                       'Programming Language :: Python',
                       'Programming Language :: Python :: 3.7',
                       'Topic :: Utilities'],
          entry_points={
              'console_scripts': [
                  'crawl-recipe = recipe.main',
              ]
          })


if __name__ == '__main__':
    main()