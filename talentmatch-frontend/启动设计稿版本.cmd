@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动人岗匹配智能评估系统（设计稿版本）...
if not exist node_modules call npm.cmd ci
call npm.cmd run dev
