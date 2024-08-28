#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='importconsole',
      version='1.0',
      description='CM Import Utility',
      author='Ericsson',
      packages=find_packages(),
      platforms='any',
      install_requires=['requests>=2.6.0'],
      scripts=['importconsole.sh'],
      data_files=[('', ['importconsole.conf', 'README.txt'])]
      )
