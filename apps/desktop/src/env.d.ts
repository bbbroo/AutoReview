interface Window {
  autoreview?: {
    selectDirectory: () => Promise<string | null>;
    selectFiles: () => Promise<string[]>;
    openPath: (targetPath: string) => Promise<string>;
    backendUrl: () => Promise<string>;
  };
}
