<script lang="ts">
  import Icon from './Icon.svelte';
  
  let { show = false, title = '', onclose, children } = $props();
</script>

{#if show}
  <div 
    class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
    onclick={onclose}
    role="button"
    tabindex="0"
    onkeydown={(e) => e.key === 'Escape' && onclose()}
  >
    <div 
      class="max-w-4xl w-full bg-gray-800 border border-gray-600 shadow-xl rounded-lg max-h-[90vh] overflow-hidden"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
      role="dialog"
      aria-modal="true"
      tabindex="-1"
    >
      <!-- Header -->
      <div class="p-6 border-b border-gray-600 flex items-center justify-between">
        <h2 class="text-xl font-bold text-gray-100 font-mono">{title}</h2>
        <button 
          onclick={onclose}
          class="text-gray-400 hover:text-gray-100 transition-colors"
        >
          <Icon name="x" class="h-6 w-6" />
        </button>
      </div>
      
      <!-- Content -->
      <div class="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
        {@render children()}
      </div>
    </div>
  </div>
{/if}