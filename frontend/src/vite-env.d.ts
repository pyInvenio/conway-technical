/// <reference types="svelte" />
/// <reference types="vite/client" />

declare namespace svelteHTML {
  interface HTMLAttributes<T> {
    onclick?: (event: MouseEvent) => void;
    onkeydown?: (event: KeyboardEvent) => void;
  }
}
