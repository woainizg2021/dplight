import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useConfigStore = defineStore('config', () => {
  const showUSD = ref(false);
  const exchangeRates = ref<Record<string, number>>({});

  function toggleUSD() {
    showUSD.value = !showUSD.value;
    localStorage.setItem('showUSD', String(showUSD.value));
  }

  function setExchangeRates(rates: Record<string, number>) {
    exchangeRates.value = rates;
  }

  function init() {
    const saved = localStorage.getItem('showUSD');
    if (saved) {
      showUSD.value = saved === 'true';
    }
  }

  return {
    showUSD,
    exchangeRates,
    toggleUSD,
    setExchangeRates,
    init
  };
});
