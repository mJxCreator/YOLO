@echo off
REM 打包 YOLO26 缺陷检测应用
cd /d "%~dp0"
call uv run pyinstaller build.spec --noconfirm
echo.
echo 打包完成，输出目录: dist\YOLO26DefectDetector\
pause
