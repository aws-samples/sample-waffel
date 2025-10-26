#!/bin/bash

echo "Running pylint..."
pylint waffel/ --output-format=text

echo -e "\nRunning bandit..."
bandit -r waffel/ -f txt
