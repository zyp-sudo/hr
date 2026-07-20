import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#060b16',
        panel: '#0b1220',
        panel2: '#101a2d',
        line: '#1d2b44',
        cyanGlow: '#22d3ee',
        brand: '#3b82f6'
      },
      boxShadow: {
        glow: '0 0 28px rgba(34, 211, 238, 0.16)'
      }
    }
  },
  plugins: []
} satisfies Config;
