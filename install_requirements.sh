#!/bin/bash

CYTHON_VER=0.29.6
KIVY_VER=1.10.1

# install Cython first
pip install Cython==${CYTHON_VER}

# install Kivy
pip install Kivy==${KIVY_VER}

# install rest of requirements
pip install -r requirements.txt
