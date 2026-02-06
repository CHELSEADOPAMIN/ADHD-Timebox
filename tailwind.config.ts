import type { Config } from "tailwindcss";

const config: Config = {
    darkMode: "class",
    content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
  	extend: {
  		fontFamily: {
  			sans: [
  				'var(--font-inter)',
  				'-apple-system',
  				'BlinkMacSystemFont',
  				'Segoe UI',
  				'sans-serif'
  			]
  		},
  		colors: {
  			calm: {
  				'50': '#F0F9FF',
  				'100': '#E0F2FE',
  				'200': '#BAE6FD',
  				'300': '#7DD3FC',
  				'400': '#38BDF8',
  				'500': '#0EA5E9',
  				'600': '#0284C7',
  				'700': '#0369A1',
  				'800': '#075985',
  				'900': '#0C4A6E'
  			},
  			health: {
  				'50': '#F0FDF4',
  				'100': '#DCFCE7',
  				'200': '#BBF7D0',
  				'300': '#86EFAC',
  				'400': '#4ADE80',
  				'500': '#22C55E',
  				'600': '#16A34A',
  				'700': '#15803D',
  				'800': '#166534',
  				'900': '#14532D'
  			},
  			surface: {
  				light: '#FFFFFF',
  				soft: '#F8FAFC',
  				elevated: '#FFFFFF'
  			},
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			}
  		},
  		spacing: {
  			'18': '4.5rem',
  			'22': '5.5rem',
  			'26': '6.5rem',
  			'30': '7.5rem'
  		},
  		fontSize: {
  			'2xs': [
  				'0.75rem',
  				{
  					lineHeight: '1.25rem'
  				}
  			],
  			xs: [
  				'0.875rem',
  				{
  					lineHeight: '1.5rem'
  				}
  			],
  			sm: [
  				'0.9375rem',
  				{
  					lineHeight: '1.625rem'
  				}
  			],
  			base: [
  				'1rem',
  				{
  					lineHeight: '1.75rem'
  				}
  			],
  			lg: [
  				'1.125rem',
  				{
  					lineHeight: '1.875rem'
  				}
  			],
  			xl: [
  				'1.5rem',
  				{
  					lineHeight: '2.25rem'
  				}
  			],
  			'2xl': [
  				'2rem',
  				{
  					lineHeight: '2.5rem'
  				}
  			],
  			'3xl': [
  				'2.5rem',
  				{
  					lineHeight: '3rem'
  				}
  			],
  			'4xl': [
  				'3rem',
  				{
  					lineHeight: '3.5rem'
  				}
  			]
  		},
  		boxShadow: {
  			soft: '0 2px 8px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.06)',
  			'soft-md': '0 4px 12px rgba(0, 0, 0, 0.05), 0 2px 4px rgba(0, 0, 0, 0.06)',
  			'soft-lg': '0 8px 24px rgba(0, 0, 0, 0.06), 0 4px 8px rgba(0, 0, 0, 0.08)',
  			'soft-xl': '0 12px 32px rgba(0, 0, 0, 0.08), 0 6px 12px rgba(0, 0, 0, 0.1)',
  			'inner-soft': 'inset 0 2px 4px rgba(0, 0, 0, 0.06)'
  		},
  		borderRadius: {
  			xl: '1rem',
  			'2xl': '1.25rem',
  			'3xl': '1.5rem',
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		transitionDuration: {
  			'150': '150ms',
  			'200': '200ms',
  			'300': '300ms'
  		},
  		transitionTimingFunction: {
  			'ease-out': 'cubic-bezier(0, 0, 0.2, 1)',
  			'ease-in-out': 'cubic-bezier(0.4, 0, 0.2, 1)'
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
