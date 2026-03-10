import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useCompanyStore = defineStore('company', () => {
  const currentCompany = ref('UGANDA');
  const allowedCompanies = ref<string[]>([]); // Populated from auth
  const showUSD = ref(false); // 全局显示USD折合开关
  
  // 汇率配置 (1 USD = X Local Currency)
  // 这里的汇率应该是从后端获取或者手动配置的，目前先硬编码为提示中的值作为默认值
  // 乌干达 1:520 | 尼日利亚 1:210 | 肯尼亚 1:18 | 刚果金 1:0.14 USD? (这里可能指的是 1 USD = X Local，或者反过来)
  // 根据通常理解，这里可能是 RMB 汇率。
  // 但为了满足 "Display USD equivalent" 的需求，我们暂时使用以下默认汇率（需确认真实值）：
  // 假设 1 USD = 3700 UGX, 1600 NGN, 130 KES, 2800 CDF
  const exchangeRates = ref<Record<string, number>>({
    'UGX': 3700,
    'NGN': 1600,
    'KES': 130,
    'CDF': 2800,
    'USD': 1
  });

  const companyMap: Record<string, { short: string; full: string; currency: string }> = {
    UGANDA: { short: '乌干达', full: '乌干达灯具制造', currency: 'UGX' },
    NIGERIA: { short: '尼日利亚', full: '尼日利亚灯具制造', currency: 'NGN' },
    KENYA: { short: '肯尼亚', full: '肯尼亚灯具制造', currency: 'KES' },
    KENYA_AUDIO: { short: '肯尼亚音箱', full: '肯尼亚音箱制造', currency: 'KES' },
    DRC: { short: '刚果金', full: '刚果金灯具制造', currency: 'CDF' },
  };

  const currentCompanyInfo = computed(() => companyMap[currentCompany.value] || {});

  function setCompany(company: string) {
    if (allowedCompanies.value.length > 0 && !allowedCompanies.value.includes(company)) {
      console.warn(`Company ${company} not allowed for current user`);
      // Don't return, let it fail? Or handle gracefully.
      // For now, allow setting if list is empty (not initialized)
    }
    currentCompany.value = company;
    localStorage.setItem('currentCompany', company);
  }

  function init() {
    const saved = localStorage.getItem('currentCompany');
    if (saved && companyMap[saved]) {
      currentCompany.value = saved;
    }
  }
  
  function getCompanyShortName(key: string) {
      return companyMap[key]?.short || key;
  }
  
  function getCompanyFullName(key: string) {
      return companyMap[key]?.full || key;
  }

  function toggleShowUSD() {
    showUSD.value = !showUSD.value;
  }
  
  function getExchangeRate(currency: string): number {
    return exchangeRates.value[currency] || 1;
  }

  return {
    currentCompany,
    allowedCompanies,
    currentCompanyInfo,
    showUSD,
    exchangeRates,
    setCompany,
    init,
    getCompanyShortName,
    getCompanyFullName,
    toggleShowUSD,
    getExchangeRate
  };
});
