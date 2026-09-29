@echo off
rem Build the Yumeria CDI tool (static, no DLL dependency).
gcc -O2 -Wall -Wextra -static -static-libgcc -s -o cdi.exe cdi.c container.c util.c
