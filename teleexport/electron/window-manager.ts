import { BrowserWindow, screen } from 'electron';

interface WindowState {
  width: number;
  height: number;
  x?: number;
  y?: number;
  isMaximized: boolean;
}

const DEFAULT_STATE: WindowState = {
  width: 1200,
  height: 800,
  isMaximized: false,
};

export function getWindowState(): WindowState {
  return { ...DEFAULT_STATE };
}

export function ensureVisibleOnDisplay(state: WindowState): WindowState {
  const displays = screen.getAllDisplays();
  const visible = displays.some((display) => {
    const { x, y, width, height } = display.bounds;
    return (
      (state.x ?? 0) >= x &&
      (state.y ?? 0) >= y &&
      (state.x ?? 0) + state.width <= x + width &&
      (state.y ?? 0) + state.height <= y + height
    );
  });

  if (!visible) {
    return { ...DEFAULT_STATE };
  }
  return state;
}

export function saveWindowState(win: BrowserWindow): WindowState {
  const bounds = win.getBounds();
  return {
    width: bounds.width,
    height: bounds.height,
    x: bounds.x,
    y: bounds.y,
    isMaximized: win.isMaximized(),
  };
}
