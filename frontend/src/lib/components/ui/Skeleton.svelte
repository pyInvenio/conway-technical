<script lang="ts">
  let { 
    class: className = '',
    ...props
  } = $props();
</script>

<div
  class="animate-pulse rounded-md bg-gray-700 {className}"
  aria-label="Loading..."
  {...props}
></div>