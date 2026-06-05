import { app, BrowserWindow, Menu } from 'electron';
import path from 'path';
import { PythonBridge } from './python-bridge';
import { registerIPCHandlers } from './ipc-handlers';
import { buildMenu } from './menu';
import { getWindowState, ensureVisibleOnDisplay } from './window-manager';

let mainWindow: BrowserWindow | null = null;
let pythonBridge: PythonBridge | null = null;

function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}

function createWindow(): void {
  const state = ensureVisibleOnDisplay(getWindowState());

  mainWindow = new BrowserWindow({
    width: state.width,
    height: state.height,
    x: state.x,
    y: state.y,
    frame: false,
    backgroundColor: '#0f172a',
    titleBarStyle: 'hidden',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (state.isMaximized) {
    mainWindow.maximize();
  }

  const isDev = process.env.NODE_ENV === 'development';
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function initPythonBridge(): void {
  pythonBridge = new PythonBridge();
  pythonBridge.start();
  registerIPCHandlers(pythonBridge, getMainWindow);
}

app.whenReady().then(() => {
  initPythonBridge();
  createWindow();

  const menu = buildMenu(getMainWindow);
  Menu.setApplicationMenu(menu);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  pythonBridge?.stop();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  pythonBridge?.stop();
});
