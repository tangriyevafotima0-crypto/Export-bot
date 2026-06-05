import { ipcMain, dialog, shell, BrowserWindow } from 'electron';
import { PythonBridge } from './python-bridge';

export function registerIPCHandlers(bridge: PythonBridge, getMainWindow: () => BrowserWindow | null): void {
  ipcMain.handle('python:call', async (_event, method: string, params: Record<string, unknown>) => {
    return await bridge.call(method, params);
  });

  bridge.on('event', (eventName: string, data: unknown) => {
    const win = getMainWindow();
    if (win) {
      win.webContents.send('python:event', eventName, data);
    }
  });

  ipcMain.handle('dialog:selectDirectory', async () => {
    const win = getMainWindow();
    if (!win) return null;
    const result = await dialog.showOpenDialog(win, {
      properties: ['openDirectory', 'createDirectory'],
    });
    return result.canceled ? null : result.filePaths[0];
  });

  ipcMain.handle('dialog:openFile', async (_event, filePath: string) => {
    await shell.openPath(filePath);
  });

  ipcMain.handle('app:getVersion', () => {
    const { app } = require('electron');
    return app.getVersion();
  });

  ipcMain.on('window:minimize', () => {
    const win = getMainWindow();
    win?.minimize();
  });

  ipcMain.on('window:maximize', () => {
    const win = getMainWindow();
    if (win?.isMaximized()) {
      win.unmaximize();
    } else {
      win?.maximize();
    }
  });

  ipcMain.on('window:close', () => {
    const win = getMainWindow();
    win?.close();
  });
}
