@echo off
:refresh
py scgb.py >> updates.log
timeout 60
goto refresh
