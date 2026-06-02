/// <reference types="vite/client" />

declare const __APP_VERSION__: string;

declare module '*.svg' {
  const content: string;
  export default content;
}

declare module 'react-simple-maps';
