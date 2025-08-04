<script lang="ts">
  import { cn } from '$lib/utils';
  
  let { 
    variant = 'default',
    class: className = '',
    children,
    ...props
  } = $props();

  const variants = {
    default: 'border-transparent bg-primary text-primary-foreground hover:bg-primary/80',
    secondary: 'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
    destructive: 'border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80',
    outline: 'text-foreground',
    success: 'border-transparent bg-crypto-green text-white',
    warning: 'border-transparent bg-crypto-orange text-white',
    error: 'border-transparent bg-crypto-red text-white',
    info: 'border-transparent bg-crypto-blue text-white',
  };
</script>

<div
  class={cn(
    'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
    variants[variant],
    className
  )}
  {...props}
>
  {@render children()}
</div>