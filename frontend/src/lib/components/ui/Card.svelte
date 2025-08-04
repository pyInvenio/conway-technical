<script lang="ts">
  import { cn } from '$lib/utils';
  
  let { 
    class: className = '',
    children,
    ...props
  } = $props();
</script>

<div
  class={cn(
    'rounded-lg border bg-card text-card-foreground shadow-sm backdrop-blur-sm',
    className
  )}
  {...props}
>
  {@render children()}
</div>