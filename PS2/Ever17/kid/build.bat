@echo off
cd /d "%~dp0"
dotnet publish Kid/Kid.csproj -c Release -r win-x64 -o publish -p:PublishSingleFile=true -p:SelfContained=false
echo.
echo Done: publish\kid.exe
pause
