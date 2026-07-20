import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        night: '#090d12',
        panel: '#101720',
        line: '#263241',
        cyanx: '#35d5ff',
        mint: '#34d399',
        amberg: '#f5b84b',
        rosex: '#fb7185',
        violetx: '#a78bfa'
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(53, 213, 255, 0.12), 0 18px 55px rgba(0, 0, 0, 0.35)'
      }
    }
  },
  plugins: []
} satisfies Config;
