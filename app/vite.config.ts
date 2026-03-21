import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react-swc';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // docker-compose передаёт в process.env; .env — через loadEnv
  const proxyTarget =
    process.env.VITE_DEV_PROXY_TARGET ||
    env.VITE_DEV_PROXY_TARGET ||
    'http://127.0.0.1:80';

  return {
    plugins: [react()],
    define: { global: 'window' },
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': { target: proxyTarget, changeOrigin: true },
        '/telegram-downloads': { target: proxyTarget, changeOrigin: true },
        '/telegram': { target: proxyTarget, changeOrigin: true },
      },
    },
  };
});
