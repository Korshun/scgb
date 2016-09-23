@echo off
:refresh
py scgb.py >> updates.log
timeout 120
goto refresh
