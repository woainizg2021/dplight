import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(null);
  const user = ref<string | null>(null);
  const roles = ref<string[]>([]);
  const allowedCompanies = ref<string[]>([]);
  const isSuperuser = ref(false);

  function login(accessToken: string, username: string, userRoles: string[], companies: string[], superuser: boolean = false) {
    token.value = accessToken;
    user.value = username;
    roles.value = userRoles;
    allowedCompanies.value = companies;
    isSuperuser.value = superuser;
    localStorage.setItem('token', accessToken);
  }

  function logout() {
    token.value = null;
    user.value = null;
    roles.value = [];
    allowedCompanies.value = [];
    localStorage.removeItem('token');
  }

  function init() {
    const savedToken = localStorage.getItem('token');
    if (savedToken) {
      token.value = savedToken;
      // Fetch user profile to get roles and companies?
    }
  }

  return {
    token,
    user,
    roles,
    allowedCompanies,
    isSuperuser,
    login,
    logout,
    init
  };
});
