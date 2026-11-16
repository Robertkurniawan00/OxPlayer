#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <shlwapi.h>
#include <stdio.h>
#include <stdlib.h>

#pragma comment(lib, "shlwapi.lib")
#pragma comment(lib, "shell32.lib")

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR pCmdLine, int nCmdShow) {
    (void)hInstance;
    (void)hPrevInstance;
    (void)pCmdLine;
    (void)nCmdShow;

    WCHAR selfPath[MAX_PATH];
    if (GetModuleFileNameW(NULL, selfPath, MAX_PATH) == 0) {
        return 1;
    }

    // Get launcher directory
    WCHAR dir[MAX_PATH];
    wcscpy_s(dir, MAX_PATH, selfPath);
    PathRemoveFileSpecW(dir);

    // Candidates to run:
    // 1. main.py in same directory (developer / source mode)
    // 2. OXPlayer.exe in same directory or dist
    WCHAR mainPyPath[MAX_PATH];
    WCHAR oxPlayerExePath[MAX_PATH];

    swprintf_s(mainPyPath, MAX_PATH, L"%s\\main.py", dir);
    swprintf_s(oxPlayerExePath, MAX_PATH, L"%s\\dist\\OXPlayer\\OXPlayer.exe", dir);

    WCHAR targetCmd[32768];
    targetCmd[0] = L'\0';

    if (PathFileExistsW(mainPyPath)) {
        // Run with pythonw if available, else python
        swprintf_s(targetCmd, 32768, L"pythonw.exe \"%s\"", mainPyPath);
    } else if (PathFileExistsW(oxPlayerExePath)) {
        swprintf_s(targetCmd, 32768, L"\"%s\"", oxPlayerExePath);
    } else {
        // Fallback: try python main.py in dir
        swprintf_s(targetCmd, 32768, L"python.exe \"%s\\main.py\"", dir);
    }

    // Append all passed arguments
    int argc = 0;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv && argc > 1) {
        for (int i = 1; i < argc; i++) {
            wcscat_s(targetCmd, 32768, L" \"");
            wcscat_s(targetCmd, 32768, argv[i]);
            wcscat_s(targetCmd, 32768, L"\"");
        }
        LocalFree(argv);
    }

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_SHOW;
    ZeroMemory(&pi, sizeof(pi));

    // Create process in launcher directory
    BOOL success = CreateProcessW(
        NULL,
        targetCmd,
        NULL,
        NULL,
        FALSE,
        CREATE_NO_WINDOW,
        NULL,
        dir,
        &si,
        &pi
    );

    if (success) {
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return 0;
    }

    return (int)GetLastError();
}
