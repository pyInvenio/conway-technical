/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        border: 'hsl(214 32% 91%)',
        input: 'hsl(214 32% 91%)',
        ring: 'hsl(222 84% 4.9%)',
        background: 'hsl(222 84% 4.9%)',
        foreground: 'hsl(210 40% 98%)',
        primary: {
          DEFAULT: 'hsl(210 40% 98%)',
          foreground: 'hsl(222 84% 4.9%)',
        },
        secondary: {
          DEFAULT: 'hsl(217 32% 17%)',
          foreground: 'hsl(210 40% 98%)',
        },
        destructive: {
          DEFAULT: 'hsl(0 62% 30%)',
          foreground: 'hsl(210 40% 98%)',
        },
        muted: {
          DEFAULT: 'hsl(217 32% 17%)',
          foreground: 'hsl(215 20% 65%)',
        },
        accent: {
          DEFAULT: 'hsl(217 32% 17%)',
          foreground: 'hsl(210 40% 98%)',
        },
        popover: {
          DEFAULT: 'hsl(222 84% 4.9%)',
          foreground: 'hsl(210 40% 98%)',
        },
        card: {
          DEFAULT: 'hsl(222 84% 4.9%)',
          foreground: 'hsl(210 40% 98%)',
        },
        // Crypto-inspired colors
        crypto: {
          green: '#00D4AA',
          red: '#FF4747',
          orange: '#FF8C00',
          blue: '#0088CC',
          purple: '#8B5CF6',
          gold: '#FFD700',
        },
        // Terminal-like colors
        terminal: {
          bg: '#0C0C0C',
          surface: '#1A1A1A',
          border: '#333333',
          text: '#E5E5E5',
          green: '#39FF14',
          amber: '#FFBF00',
        }
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'scan': 'scan 2s linear infinite',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgb(0, 212, 170)' },
          '100%': { boxShadow: '0 0 20px rgb(0, 212, 170), 0 0 30px rgb(0, 212, 170)' },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        }
      }
    },
  },
  plugins: [],
}