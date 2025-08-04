<script lang="ts">
  import { cn } from '$lib/utils';
  
  let { 
    value = 0,
    max = 100,
    class: className = '',
    ...props
  } = $props();

  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);
</script>

<div
  class={cn(
    'relative h-4 w-full overflow-hidden rounded-full bg-secondary',
    className
  )}
  {...props}
>
  <div
    class="h-full w-full flex-1 bg-gradient-to-r from-crypto-blue to-crypto-green transition-all duration-300 ease-in-out"
    style="transform: translateX(-{100 - percentage}%)"
  ></div>
</div>