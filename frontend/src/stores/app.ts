import { defineStore } from 'pinia';

export interface AppState {
  theme: 'light' | 'dark';
  colorWeak: boolean;
  navbar: boolean;
  menu: boolean;
  topMenu: boolean;
  hideMenu: boolean;
  menuCollapse: boolean;
  footer: boolean;
  themeColor: string;
  menuWidth: number;
  globalSettings: boolean;
  device: string;
  tabBar: boolean;
  menuFromServer: boolean;
  serverMenu: any[];
  tenant: string;
  showUSD: boolean;
}

export const useAppStore = defineStore('app', {
  state: (): AppState => ({
    theme: 'light',
    colorWeak: false,
    navbar: true,
    menu: true,
    topMenu: false,
    hideMenu: false,
    menuCollapse: false,
    footer: true,
    themeColor: '#165DFF',
    menuWidth: 220,
    globalSettings: false,
    device: 'desktop',
    tabBar: false,
    menuFromServer: false,
    serverMenu: [],
    tenant: 'UGANDA',
    showUSD: false,
  }),

  getters: {
    appCurrentSetting(state: AppState): AppState {
      return { ...state };
    },
    appDevice(state: AppState) {
      return state.device;
    },
    appAsyncMenus(state: AppState) {
      return state.serverMenu;
    },
  },

  actions: {
    updateSettings(partial: Partial<AppState>) {
      this.$patch(partial);
    },
    toggleTheme(dark: boolean) {
      if (dark) {
        this.theme = 'dark';
        document.body.setAttribute('arco-theme', 'dark');
      } else {
        this.theme = 'light';
        document.body.removeAttribute('arco-theme');
      }
    },
    toggleMenu(value: boolean) {
      this.hideMenu = value;
    },
    toggleMenuCollapse(value: boolean) {
        this.menuCollapse = value;
    },
    setTenant(tenant: string) {
        this.tenant = tenant;
    },
    toggleUSD() {
        this.showUSD = !this.showUSD;
    }
  },
});
